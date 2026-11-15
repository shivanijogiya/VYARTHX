"""AI Waste Doctor classification pipeline.

Layers (all deterministic apart from the optional LLM description):
 1. Pretrained MobileNetV2 (ImageNet-1k, ONNX Model Zoo, Apache-2.0) via onnxruntime. It is NOT trained on waste
    images and VYARTHX has not fine-tuned it; its ImageNet labels are mapped to waste categories with a rule table.
 2. Text / filename matching against the curated knowledge base (the user's description).
 3. Safety rules: hazardous items always resolve to special-care + human review; low confidence asks for clarification.
 4. Optional external vision description (ANTHROPIC_API_KEY + VYARTHX_LLM_VISION=true) feeding the same KB matcher.
The LLM never decides disposal rules: those come from the knowledge base.
"""
from __future__ import annotations

import base64
import io
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from ..config import ML_DIR, settings
from .common import get_cfg, kb_by_id, kb_items  # noqa: F401

MODEL_PATH = ML_DIR / "models" / "mobilenetv2-12.onnx"
LABELS_PATH = ML_DIR / "models" / "imagenet_classes.txt"

# ImageNet label (lowercase) -> (knowledge-base id, weight). Hand-written mapping, not learned.
IMAGENET_MAP: dict[str, tuple[str, float]] = {
    "water bottle": ("pet_bottle", 1.0), "pop bottle": ("pet_bottle", 1.0), "water jug": ("hdpe_container", 0.8),
    "bottlecap": ("pet_bottle", 0.5), "beer bottle": ("glass_bottle", 0.9), "wine bottle": ("glass_bottle", 0.9),
    "red wine": ("glass_bottle", 0.6), "pill bottle": ("medicine", 0.8), "medicine chest": ("medicine", 0.5),
    "carton": ("cardboard", 1.0), "crate": ("cardboard", 0.5), "packet": ("plastic_wrapper", 0.6),
    "plastic bag": ("plastic_wrapper", 1.0), "envelope": ("paper", 0.8), "paper towel": ("paper", 0.4),
    "notebook": ("ewaste_device", 0.2), "binder": ("paper", 0.6), "book jacket": ("books", 0.9), "comic book": ("books", 0.9),
    "menu": ("paper", 0.6), "laptop": ("ewaste_device", 1.0), "cellular telephone": ("ewaste_device", 1.0),
    "hand-held computer": ("ewaste_device", 0.9), "monitor": ("ewaste_device", 1.0), "desktop computer": ("ewaste_device", 1.0),
    "screen": ("ewaste_device", 0.9), "television": ("ewaste_device", 1.0), "remote control": ("ewaste_device", 1.0),
    "mouse": ("ewaste_device", 0.8), "computer keyboard": ("ewaste_device", 1.0), "ipod": ("ewaste_device", 1.0),
    "modem": ("ewaste_device", 1.0), "printer": ("ewaste_device", 1.0), "joystick": ("ewaste_device", 0.9),
    "dial telephone": ("ewaste_device", 1.0), "pay-phone": ("ewaste_device", 0.8), "radio": ("ewaste_device", 0.9),
    "loudspeaker": ("ewaste_device", 0.9), "polaroid camera": ("ewaste_device", 0.8), "reflex camera": ("ewaste_device", 0.9),
    "digital watch": ("ewaste_device", 0.7), "power drill": ("ewaste_device", 0.5), "electric fan": ("ewaste_device", 0.7),
    "washer": ("ewaste_device", 0.6), "microwave": ("ewaste_device", 0.9), "refrigerator": ("ewaste_device", 0.9),
    "iron": ("ewaste_device", 0.5), "hair dryer": ("ewaste_device", 0.7), "space heater": ("ewaste_device", 0.8),
    "banana": ("food_waste", 1.0), "orange": ("food_waste", 1.0), "lemon": ("food_waste", 1.0), "strawberry": ("food_waste", 1.0),
    "pineapple": ("food_waste", 1.0), "pomegranate": ("food_waste", 1.0), "fig": ("food_waste", 1.0), "granny smith": ("food_waste", 1.0),
    "custard apple": ("food_waste", 1.0), "jackfruit": ("food_waste", 1.0), "broccoli": ("food_waste", 1.0), "cauliflower": ("food_waste", 1.0),
    "cucumber": ("food_waste", 1.0), "zucchini": ("food_waste", 1.0), "mushroom": ("food_waste", 0.9), "head cabbage": ("food_waste", 1.0),
    "bell pepper": ("food_waste", 1.0), "corn": ("food_waste", 0.9), "artichoke": ("food_waste", 0.9), "acorn squash": ("food_waste", 1.0),
    "butternut squash": ("food_waste", 1.0), "spaghetti squash": ("food_waste", 1.0), "mashed potato": ("food_waste", 0.9),
    "pizza": ("food_waste", 0.7), "bagel": ("food_waste", 0.9), "pretzel": ("food_waste", 0.9), "cheeseburger": ("food_waste", 0.9),
    "hotdog": ("food_waste", 0.9), "burrito": ("food_waste", 0.9), "meat loaf": ("food_waste", 0.9), "plate": ("food_waste", 0.4),
    "consomme": ("food_waste", 0.8), "trifle": ("food_waste", 0.8), "ice cream": ("food_waste", 0.8), "french loaf": ("food_waste", 1.0),
    "jersey": ("textile", 0.9), "sweatshirt": ("textile", 0.9), "jean": ("textile", 0.9), "cardigan": ("textile", 0.9),
    "sock": ("textile", 0.9), "running shoe": ("textile", 0.9), "loafer": ("textile", 0.9), "sandal": ("textile", 0.9),
    "cowboy boot": ("textile", 0.9), "sarong": ("textile", 1.0), "kimono": ("textile", 0.9), "bath towel": ("textile", 0.8),
    "rocking chair": ("furniture", 1.0), "folding chair": ("furniture", 1.0), "barber chair": ("furniture", 1.0),
    "throne": ("furniture", 0.8), "studio couch": ("furniture", 1.0), "dining table": ("furniture", 1.0), "park bench": ("furniture", 1.0),
    "wardrobe": ("furniture", 1.0), "four-poster": ("furniture", 1.0), "bookcase": ("furniture", 1.0), "desk": ("furniture", 1.0),
    "chiffonier": ("furniture", 1.0), "crib": ("furniture", 0.9), "mosquito net": ("textile", 0.3),
    "milk can": ("metal_can", 1.0), "frying pan": ("metal_can", 0.5), "wok": ("metal_can", 0.5), "caldron": ("metal_can", 0.6),
    "band aid": ("sanitary", 0.7), "diaper": ("sanitary", 1.0), "syringe": ("sharps", 1.0), "thermometer": ("mercury_thermometer", 0.5),
    "brick": ("construction", 1.0), "flowerpot": ("garden_waste", 0.4), "daisy": ("garden_waste", 0.6), "pot": ("garden_waste", 0.2),
}


@lru_cache(maxsize=1)
def _session():
    try:
        import onnxruntime as ort

        if not MODEL_PATH.exists():
            return None
        so = ort.SessionOptions()
        so.intra_op_num_threads = 2
        return ort.InferenceSession(str(MODEL_PATH), sess_options=so, providers=["CPUExecutionProvider"])
    except Exception:
        return None


@lru_cache(maxsize=1)
def _labels() -> list[str]:
    try:
        return [l.strip().lower() for l in LABELS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def model_status() -> dict:
    s = _session()
    return {
        "image_model": "MobileNetV2 (ImageNet-1k) via onnxruntime" if s else "unavailable",
        "image_model_loaded": s is not None,
        "trained_by_vyarthx": False,
        "trained_on": "ImageNet-1k (generic objects) — NOT waste-specific",
        "label_mapping": "hand-written ImageNet→waste rule table",
        "validated_on_indian_waste_images": False,
        "licence": "Apache-2.0 (ONNX Model Zoo)",
        "llm_vision": bool(settings.llm_enabled and settings.LLM_VISION),
    }


def _preprocess(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    scale = 256 / min(w, h)
    img = img.resize((max(224, round(w * scale)), max(224, round(h * scale))), Image.BILINEAR)
    w, h = img.size
    l, t = (w - 224) // 2, (h - 224) // 2
    img = img.crop((l, t, l + 224, t + 224))
    a = np.asarray(img, dtype=np.float32) / 255.0
    a = (a - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225], dtype=np.float32)
    return a.transpose(2, 0, 1)[None].astype(np.float32)


def image_model_scores(image_bytes: bytes) -> dict:
    """Run the pretrained model. Returns top-5 ImageNet labels and the aggregated mapped KB scores."""
    sess = _session()
    labels = _labels()
    if sess is None or not labels:
        return {"available": False, "top5": [], "mapped": {}}
    x = _preprocess(image_bytes)
    logits = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
    e = np.exp(logits - logits.max())
    p = e / e.sum()
    idx = np.argsort(-p)[:8]
    top = [{"label": labels[i], "p": round(float(p[i]), 4)} for i in idx[:5]]
    mapped: dict[str, float] = {}
    for i in idx:
        m = IMAGENET_MAP.get(labels[i])
        if m:
            mapped[m[0]] = mapped.get(m[0], 0.0) + float(p[i]) * m[1]
    return {"available": True, "top5": top, "mapped": mapped}


def heuristic_guess(image_bytes: bytes) -> dict:
    """Very weak colour heuristic used only when no model is available."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((64, 64))
    a = np.asarray(img, dtype=np.float32)
    r, g, b = a[..., 0].mean(), a[..., 1].mean(), a[..., 2].mean()
    if r > g > b and r - b > 25:
        return {"kb": "cardboard", "p": 0.25, "note": f"brownish average colour ({r:.0f},{g:.0f},{b:.0f})"}
    if g > r and g > b:
        return {"kb": "food_waste", "p": 0.2, "note": "green-dominant average colour"}
    return {"kb": None, "p": 0.0, "note": "no usable colour cue"}


_WEAK = {"box", "can", "tin", "metal", "cell", "food", "jar", "packet", "glass", "paper", "lamp", "pet", "fruit", "table", "bed",
         "iron", "sand", "foil", "book", "pad", "blood", "drug", "acid", "tablet", "mobile", "cable", "desk", "rice", "bread"}
_CONT_WORDS = ["food", "oil", "oily", "grease", "greasy", "residue", "stain", "stained", "dirty", "soiled", "leftover", "sauce", "curry", "mouldy", "moldy", "wet", "sticky"]


def _norm(t: str) -> str:
    return " " + re.sub(r"[^a-z0-9 ]+", " ", t.lower().replace("_", " ").replace("-", " ")) + " "


def text_scores(text: str) -> dict[str, dict]:
    t = _norm(text)
    out: dict[str, dict] = {}
    if not t.strip():
        return out
    for item in kb_items():
        best, kwhit = 0.0, ""
        for kw in item["keywords"]:
            k = _norm(kw)
            if k in t or (len(k.strip()) > 4 and k.strip().rstrip("s") != "" and (" " + k.strip().rstrip("s") + "s ") in t):
                words = len(kw.split())
                sc = 0.55 + 0.1 * min(words, 3) + 0.004 * len(kw)
                if kw in _WEAK:
                    sc = min(sc, 0.62)
                sc = min(sc, 0.96)
                if sc > best:
                    best, kwhit = sc, kw
        if best:
            out[item["id"]] = {"score": best, "keyword": kwhit}
    return out


def llm_describe(image_bytes: bytes) -> str:
    """Optional external vision description. Used only to produce words for the KB matcher."""
    if not (settings.llm_enabled and settings.LLM_VISION):
        return ""
    try:
        import httpx

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((768, 768))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode()
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": settings.LLM_MODEL,
                "max_tokens": 120,
                "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": "In under 25 words, name the single main household waste item in this photo and any visible food/oil contamination. No advice."},
                ]}],
            },
            timeout=25,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except Exception:
        return ""


def classify(image_bytes: bytes | None, text: str = "", filename: str = "", cfg: dict | None = None) -> dict:
    reasoning: list[str] = []
    mode_parts: list[str] = []
    fname_text = Path(filename).stem if filename else ""
    llm_desc = llm_describe(image_bytes) if image_bytes else ""
    if llm_desc:
        mode_parts.append("llm_vision_description")
        reasoning.append(f"External vision description: “{llm_desc}”")
    all_text = " ".join(x for x in [text, fname_text, llm_desc] if x)
    ts = text_scores(all_text)
    img = {"available": False, "top5": [], "mapped": {}}
    heur = None
    if image_bytes:
        try:
            img = image_model_scores(image_bytes)
        except Exception as e:  # corrupt image etc.
            reasoning.append(f"Image could not be analysed ({type(e).__name__}).")
        if img["available"]:
            mode_parts.append("onnx_mobilenetv2_imagenet_mapped")
            if img["top5"]:
                reasoning.append("Image model top guesses (generic ImageNet labels): " + ", ".join(f"{t['label']} {t['p']:.0%}" for t in img["top5"][:3]))
        else:
            heur = heuristic_guess(image_bytes)
            mode_parts.append("colour_heuristic_fallback")
    if ts:
        mode_parts.append("knowledge_base_text_match")

    cand: dict[str, float] = {}
    for k, v in ts.items():
        cand[k] = v["score"]
    img_scores = {k: min(0.9, v * 1.15) for k, v in img["mapped"].items() if v >= 0.08}
    for k, v in img_scores.items():
        cand[k] = max(cand.get(k, 0), 0) if k in ts else v
    if heur and heur["kb"] and not ts:
        cand[heur["kb"]] = heur["p"]
        reasoning.append(f"Fallback colour cue only: {heur['note']} (very low confidence).")

    conflict = False
    best_id, conf = None, 0.0
    if cand:
        # safety first: a matched hazardous item beats a non-hazardous one when scores are close
        ranked = sorted(cand.items(), key=lambda kv: -kv[1])
        best_id, conf = ranked[0]
        for k, v in ranked:
            kb = kb_by_id(k)
            if kb and kb["hazard"] and v >= ranked[0][1] - 0.25 and v >= 0.5:
                best_id, conf = k, v
                if k != ranked[0][0]:
                    reasoning.append("Safety-first rule: a possible hazardous item was detected, so it takes precedence.")
                break
        in_text, in_img = best_id in ts, best_id in img_scores
        if in_text and in_img:
            conf = min(0.98, ts[best_id]["score"] + 0.1 * img_scores[best_id])
            reasoning.append(f"Description (“{ts[best_id]['keyword']}”) and the image model agree.")
        elif in_text and img_scores:
            top_img = max(img_scores.items(), key=lambda kv: kv[1])
            if top_img[0] != best_id and top_img[1] > 0.35:
                conflict = True
                conf = round(ts[best_id]["score"] * 0.75, 3)
                reasoning.append(f"Description suggests “{kb_by_id(best_id)['name']}” but the image model suggests “{kb_by_id(top_img[0])['name']}”; please confirm.")
        elif in_text:
            reasoning.append(f"Matched your description keyword “{ts[best_id]['keyword']}”.")
        elif in_img:
            reasoning.append("Identified from the image model's mapped labels only.")

    cont_hit = [w for w in _CONT_WORDS if f" {w} " in _norm(all_text)]
    result: dict = {
        "candidates": [{"id": k, "name": (kb_by_id(k) or {}).get("name", k), "score": round(v, 3)} for k, v in sorted(cand.items(), key=lambda kv: -kv[1])[:4]],
        "reasoning": reasoning,
        "image_top5": img["top5"],
        "mode": "+".join(mode_parts) or "none",
        "model_info": model_status(),
        "conflict": conflict,
    }
    min_conf = 0.55
    if not best_id or conf < min_conf or conflict:
        result.update(
            detected_object=kb_by_id(best_id)["object"] if best_id else "Unrecognised item",
            material="Undetermined", material_key="mixed", stream="undetermined", confidence=round(conf, 3),
            contamination="possible" if cont_hit else "none", needs_clarification=True, hazard=False,
            human_review_required=False, recyclable=False, reward_eligible=False,
            contamination_warning="Visual contamination cannot be assessed reliably — describe the item to improve accuracy.",
            handling="Not enough certainty. Please add a short description (for example 'pizza box with food residue') or choose from the suggestions. If the item may be hazardous (battery, bulb, medicine, chemical), keep it separate and use special-care collection.",
            disposal="No disposal route is recommended until the item is confirmed.",
            destination_types=[], reward_note="Not eligible until the item is confirmed.",
            suggestions=[c["name"] for c in result["candidates"]],
        )
        if not reasoning:
            reasoning.append("No reliable match from the image model or the description.")
        return result

    item = kb_by_id(best_id)
    cont = item["inherent_contamination"]
    if cont_hit and cont == "none" and item["stream"] != "wet":
        cont = "detected" if any(w in cont_hit for w in ("greasy", "grease", "oily", "oil", "residue", "stained", "soiled", "food", "leftover", "sauce", "curry")) else "possible"
    cfg = cfg or {}
    warn = {
        "none": "No contamination indicated. Visual contamination detection is limited in this build — rinse and keep dry.",
        "possible": "Possible contamination or mixed materials — clean and separate where practical.",
        "detected": "Contamination detected or indicated — contaminated material may be rejected by recyclers.",
    }[cont]
    if item["hazard"]:
        warn = "HAZARDOUS / special-care item. VYARTHX cannot declare it safe — use authorised handling."
    prov_min = cfg.get("provisional_min_confidence", 0.6)
    if item["reward_eligible"] and conf >= prov_min:
        rnote = "Eligible for a small provisional reward after verification; the larger reward follows collector confirmation."
        eligible = True
    elif not item["reward_eligible"]:
        rnote = "No GreenPoints for this stream/item (safety or non-recoverable)."
        eligible = False
    else:
        rnote = "Confidence is below the provisional-reward threshold."
        eligible = False
    result.update(
        item_id=item["id"], detected_object=item["object"], material=item["material"], material_key=item["material_key"],
        stream=item["stream"], confidence=round(float(conf), 3), contamination=cont, contamination_warning=warn,
        handling=item["handling"], disposal=item["disposal"], destination_types=item["destination_types"],
        hazard=item["hazard"], human_review_required=bool(item["hazard"]), recyclable=item["recyclable"],
        needs_clarification=False, reward_eligible=eligible, reward_note=rnote,
        suggestions=[],
    )
    return result
