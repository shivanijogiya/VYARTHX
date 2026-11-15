"""Waste knowledge base + policy guidance retrieval.

The knowledge base is the single source of truth for disposal rules. Classifiers and LLMs may only
*select* an item from this base; they never invent disposal instructions.

Four-stream framework: Solid Waste Management Rules, 2026 (MoEFCC, notified 27 Jan 2026, in force
1 Apr 2026): wet, dry, sanitary and special-care waste.
Local instructions below are an ILLUSTRATIVE pilot configuration for Chennai and must be confirmed
and edited by the local authority before real use.
"""
from __future__ import annotations

import math
import re
from collections import Counter

STREAMS = {
    "wet": {"label": "Wet waste", "desc": "Kitchen and food waste, peels, garden waste - for composting or biomethanation."},
    "dry": {"label": "Dry waste", "desc": "Paper, plastic, metal, glass, cardboard - routed to Material Recovery Facilities."},
    "sanitary": {"label": "Sanitary waste", "desc": "Diapers, sanitary napkins, bandages - wrap securely and store separately."},
    "special_care": {"label": "Special-care waste", "desc": "Domestic hazardous items - hand over only to authorised agencies or designated collection centres."},
}

# reward_class maps to data/seed/reward_rules.json material_rate_per_kg
ITEMS: dict[str, dict] = {
    "pet_bottle": dict(name="PET plastic bottle", material="PET plastic (#1)", reward_class="pet", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=0.03,
        keywords=["pet bottle", "plastic bottle", "water bottle", "soft drink bottle", "cool drink bottle", "bisleri", "mineral water"],
        imagenet=["water bottle", "pop bottle", "water jug"],
        handling="Empty and rinse. Flatten to save space. Keep the cap on.",
        disposal="Dry waste. Hand over to your dry-waste collector or a PET buyer.",
        destinations=["mrf", "recycler", "scrap_dealer"], contamination_check="Liquid or food residue lowers quality."),
    "glass_bottle": dict(name="Glass bottle / jar", material="Glass", reward_class="glass", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=0.35,
        keywords=["glass bottle", "glass jar", "beer bottle", "wine bottle", "pickle jar", "jam jar"],
        imagenet=["beer bottle", "wine bottle", "red wine", "whiskey jug"],
        handling="Rinse. Do not break. Keep separate from other dry waste if your collector asks.",
        disposal="Dry waste (glass). Intact bottles can be reused or sold to kabadiwalas.",
        destinations=["mrf", "recycler", "scrap_dealer"], contamination_check="Broken glass must be wrapped and labelled for worker safety."),
    "broken_glass": dict(name="Broken glass / ceramic", material="Glass / ceramic", reward_class="mixed", stream="dry",
        recyclable=False, hazard=True, est_weight_kg=0.4,
        keywords=["broken glass", "glass pieces", "shards", "broken cup", "broken plate", "ceramic"],
        imagenet=["beer glass", "goblet"],
        handling="Wrap in thick paper or cardboard, label 'SHARP - broken glass' so the worker is not injured.",
        disposal="Hand over separately to the dry-waste collector, clearly labelled. Do not mix loose shards with other waste.",
        destinations=["mrf"], contamination_check="Safety first: wrap and label."),
    "cardboard": dict(name="Cardboard packaging", material="Corrugated cardboard / paperboard", reward_class="cardboard", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=0.4,
        keywords=["cardboard", "carton", "corrugated", "box", "delivery box", "amazon box", "shoe box", "packaging box"],
        imagenet=["carton", "crate", "packet"],
        handling="Keep dry. Remove tape and plastic. Flatten boxes.",
        disposal="Dry waste. Highly recyclable when clean and dry.",
        destinations=["mrf", "recycler", "scrap_dealer"], contamination_check="Wet or oily cardboard has low recycling value."),
    "pizza_box_soiled": dict(name="Food-soiled pizza box", material="Paperboard with food/oil contamination", reward_class="cardboard", stream="dry",
        recyclable=False, hazard=False, est_weight_kg=0.25,
        keywords=["pizza box", "oily box", "greasy box", "food box", "soiled cardboard", "pizza"],
        imagenet=["pizza"],
        handling="Tear off clean portions (lid) for dry recycling. Food-soaked portions with oil cannot go to normal paper recycling.",
        disposal="Clean parts: dry waste. Heavily oily parts: follow local instructions - often wet/compost if the local facility accepts soiled paper, otherwise residual dry waste.",
        destinations=["mrf", "compost"], contamination_check="Oil and food residue detected - contamination is HIGH."),
    "paper": dict(name="Paper / newspaper", material="Paper", reward_class="paper", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=0.5,
        keywords=["newspaper", "paper", "magazine", "notebook pages", "office paper", "books old", "envelope", "receipt"],
        imagenet=["envelope", "comic book", "book jacket", "menu", "crossword puzzle"],
        handling="Keep dry and bundled. Remove plastic covers.",
        disposal="Dry waste. Sell to kabadiwala or hand over to the dry-waste collector.",
        destinations=["mrf", "recycler", "scrap_dealer"], contamination_check="Wet or food-stained paper loses value."),
    "plastic_wrapper": dict(name="Multi-layer plastic wrapper", material="Multi-layer plastic (MLP) / laminated film", reward_class="plastic_film", stream="dry",
        recyclable=False, hazard=False, est_weight_kg=0.01,
        keywords=["wrapper", "chips packet", "biscuit packet", "chocolate wrapper", "snack packet", "multilayer", "mlp", "sachet"],
        imagenet=["packet"],
        handling="Shake out food crumbs. Collect several wrappers together in one bag.",
        disposal="Dry waste. Usually low-value / non-recyclable MLP - routed to co-processing or energy recovery where available, NOT ordinary recycling.",
        destinations=["mrf"], contamination_check="Food residue increases contamination."),
    "plastic_bag": dict(name="Plastic carry bag / film", material="LDPE film", reward_class="plastic_film", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=0.02,
        keywords=["plastic bag", "carry bag", "polythene", "polybag", "plastic cover", "film"],
        imagenet=["plastic bag"],
        handling="Clean and dry. Bundle several bags together.",
        disposal="Dry waste. Clean film can be recycled by film recyclers; dirty film is residual.",
        destinations=["mrf", "recycler"], contamination_check="Wet or oily film is rejected."),
    "plastic_container": dict(name="Rigid plastic container", material="Rigid plastic (HDPE/PP)", reward_class="plastic_rigid", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=0.08,
        keywords=["plastic container", "shampoo bottle", "detergent bottle", "plastic tub", "curd cup", "plastic box", "bucket", "milk packet"],
        imagenet=["bucket", "lotion", "soap dispenser", "sunscreen", "hair spray", "plastic container"],
        handling="Empty, rinse and dry.",
        disposal="Dry waste. HDPE/PP containers are commonly recycled.",
        destinations=["mrf", "recycler", "scrap_dealer"], contamination_check="Product residue lowers quality."),
    "food_container_soiled": dict(name="Food-soiled takeaway container", material="Plastic / foil container with food residue", reward_class="plastic_rigid", stream="dry",
        recyclable=False, hazard=False, est_weight_kg=0.05,
        keywords=["takeaway container", "food container", "parcel box", "curry container", "foil container", "dirty container"],
        imagenet=["plate", "tray", "mixing bowl"],
        handling="Scrape food into wet waste, rinse the container, then place it in dry waste.",
        disposal="Rinsed container: dry waste. Unrinsed: contamination reduces recovery.",
        destinations=["mrf"], contamination_check="Visible food residue - rinse before handover."),
    "food_waste": dict(name="Food / kitchen waste", material="Organic (food)", reward_class="organic", stream="wet",
        recyclable=True, hazard=False, est_weight_kg=1.0,
        keywords=["food waste", "leftover", "cooked food", "rice", "vegetable", "kitchen waste", "curry", "egg shell", "tea leaves", "coffee grounds"],
        imagenet=["mashed potato", "carbonara", "potpie", "burrito", "meat loaf", "hotdog", "cheeseburger", "bagel", "French loaf", "pretzel", "trifle", "guacamole", "consomme", "hot pot", "dough", "plate"],
        handling="Drain liquids. Do not add plastic. Use a lidded bin.",
        disposal="Wet waste - home composting, community composting or biomethanation.",
        destinations=["compost", "biomethanation"], contamination_check="Plastic or foil mixed in is contamination."),
    "fruit_veg_peel": dict(name="Fruit and vegetable peels", material="Organic (raw)", reward_class="organic", stream="wet",
        recyclable=True, hazard=False, est_weight_kg=0.6,
        keywords=["peel", "banana peel", "vegetable peel", "fruit", "onion skin", "coconut", "flowers", "pooja flowers"],
        imagenet=["banana", "orange", "lemon", "pineapple", "Granny Smith", "strawberry", "pomegranate", "fig", "custard apple", "jackfruit", "corn", "ear", "broccoli", "cauliflower", "cucumber", "zucchini", "head cabbage", "bell pepper", "mushroom", "acorn squash", "butternut squash", "spaghetti squash", "artichoke", "cardoon"],
        handling="Ideal compost feedstock. Keep free of plastic.",
        disposal="Wet waste - compost or biomethanation.",
        destinations=["compost", "biomethanation"], contamination_check="Rubber bands / stickers are contamination."),
    "garden_waste": dict(name="Garden / leaf waste", material="Organic (garden)", reward_class="organic", stream="wet",
        recyclable=True, hazard=False, est_weight_kg=2.0,
        keywords=["leaves", "garden waste", "grass", "twigs", "branches", "dry leaves"],
        imagenet=["pot", "daisy", "hay"],
        handling="Bundle twigs. Leaves make excellent compost browns.",
        disposal="Wet / green waste - composting.",
        destinations=["compost"], contamination_check="Keep plastic pots separate."),
    "metal_can": dict(name="Metal can / aluminium tin", material="Aluminium / tin-plated steel", reward_class="metal", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=0.03,
        keywords=["can", "tin", "aluminium can", "coke can", "beer can", "food tin", "aluminum"],
        imagenet=["beer can", "milk can", "tin can"],
        handling="Rinse and crush lightly.",
        disposal="Dry waste. Metals have strong recycling value.",
        destinations=["mrf", "recycler", "scrap_dealer"], contamination_check="Paint or chemical cans are special-care, not normal metal."),
    "metal_scrap": dict(name="Household metal scrap", material="Steel / iron / copper / aluminium", reward_class="metal", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=1.0,
        keywords=["metal", "iron", "steel", "utensil", "vessel", "pan", "nails", "wire scrap", "copper"],
        imagenet=["frying pan", "wok", "caldron", "Dutch oven", "screw", "nail", "chain", "padlock", "spatula", "ladle", "strainer"],
        handling="Keep sharp edges covered.",
        disposal="Dry waste or sell directly to a scrap dealer / kabadiwala.",
        destinations=["scrap_dealer", "recycler", "mrf"], contamination_check="Sharp edges - protect the worker."),
    "battery": dict(name="Battery (dry cell / Li-ion)", material="Battery chemicals and metals", reward_class="special_care", stream="special_care",
        recyclable=True, hazard=True, est_weight_kg=0.05,
        keywords=["battery", "batteries", "aa cell", "cell", "lithium", "li-ion", "power bank", "button cell", "inverter battery"],
        imagenet=[],
        handling="Tape the terminals of lithium batteries. Never puncture, crush, burn or open. Store in a dry box.",
        disposal="Special-care waste. Hand over ONLY to an authorised collection point / producer take-back (Battery Waste Management Rules, 2022).",
        destinations=["special_care", "ewaste"], contamination_check="Swollen or leaking batteries: isolate in a non-metal container and report."),
    "cfl_bulb": dict(name="CFL bulb / fluorescent tube", material="Glass with mercury vapour", reward_class="special_care", stream="special_care",
        recyclable=True, hazard=True, est_weight_kg=0.1,
        keywords=["cfl", "bulb", "tube light", "tubelight", "fluorescent", "broken cfl", "lamp"],
        imagenet=["spotlight", "table lamp"],
        handling="Avoid breaking it further. If broken, ventilate the room, do not vacuum, collect pieces with stiff paper into a sealed jar. Keep away from children.",
        disposal="Special-care waste. Take to an authorised special-care / e-waste collection point. Do NOT put in ordinary dry recyclables.",
        destinations=["special_care", "ewaste"], contamination_check="Contains mercury - never crush."),
    "expired_medicine": dict(name="Expired medicine / blister strip", material="Pharmaceuticals + PVC/aluminium blister", reward_class="special_care", stream="special_care",
        recyclable=False, hazard=True, est_weight_kg=0.05,
        keywords=["medicine", "tablet", "expired", "blister", "strip", "syrup", "capsule", "pills", "drugs"],
        imagenet=["pill bottle", "medicine chest"],
        handling="Keep in original packaging. Do not flush or burn. Keep away from children and animals.",
        disposal="Special-care waste. Use a pharmacy / authorised drug take-back point or the designated special-care collection.",
        destinations=["special_care"], contamination_check="Never mix with food or wet waste."),
    "paint_chemical": dict(name="Paint can / household chemicals", material="Solvents, paints, pesticides", reward_class="special_care", stream="special_care",
        recyclable=False, hazard=True, est_weight_kg=0.8,
        keywords=["paint", "thinner", "pesticide", "insecticide", "chemical", "acid", "phenyl", "varnish", "aerosol"],
        imagenet=["paintbrush"],
        handling="Keep lid closed and upright, in original container. Never pour into drains.",
        disposal="Special-care waste - authorised collection only.",
        destinations=["special_care"], contamination_check="Do not mix chemicals."),
    "mercury_thermometer": dict(name="Mercury thermometer", material="Glass + mercury", reward_class="special_care", stream="special_care",
        recyclable=False, hazard=True, est_weight_kg=0.02,
        keywords=["thermometer", "mercury"], imagenet=[],
        handling="If broken, do not touch mercury; ventilate and seal pieces in a jar.",
        disposal="Special-care waste - authorised collection only.",
        destinations=["special_care"], contamination_check="Mercury is toxic."),
    "e_waste_device": dict(name="Electronic device (e-waste)", material="Mixed electronics (PCB, plastics, metals)", reward_class="ewaste", stream="special_care",
        recyclable=True, hazard=True, est_weight_kg=1.2,
        keywords=["phone", "mobile", "laptop", "computer", "keyboard", "mouse", "charger", "cable", "tv", "television", "remote", "router", "electronic", "e-waste", "ewaste", "printer", "earphones", "speaker", "mixer", "iron box", "fan"],
        imagenet=["cellular telephone", "laptop", "notebook", "desktop computer", "monitor", "screen", "computer keyboard", "mouse", "remote control", "iPod", "hand-held computer", "modem", "printer", "television", "radio", "cassette player", "CD player", "hard disc", "joystick", "digital clock", "digital watch", "loudspeaker", "microwave", "toaster", "hand blower", "electric fan", "iron", "dial telephone", "projector", "space heater", "photocopier", "tape player", "Polaroid camera", "reflex camera"],
        handling="Wipe personal data. Do not dismantle - circuit boards and batteries need authorised handling. Remove batteries only if designed to be removable.",
        disposal="E-waste - hand over to an authorised e-waste collection centre / producer take-back (E-Waste (Management) Rules, 2022). Working devices: consider repair or reuse first.",
        destinations=["ewaste", "reuse_ngo"], contamination_check="Swollen batteries inside devices are hazardous."),
    "sanitary_waste": dict(name="Sanitary waste (diaper / napkin)", material="Absorbent polymer + bodily waste", reward_class="sanitary", stream="sanitary",
        recyclable=False, hazard=False, est_weight_kg=0.2,
        keywords=["diaper", "sanitary napkin", "pad", "nappy", "tampon", "bandage", "cotton swab", "condom", "mask"],
        imagenet=["diaper", "Band Aid", "toilet tissue"],
        handling="Wrap securely in paper / the provided pouch and mark it. Store separately.",
        disposal="Sanitary waste stream - hand over separately to the collector as per SWM Rules, 2026.",
        destinations=["mrf"], contamination_check="Never mix with dry recyclables - it contaminates them."),
    "textile": dict(name="Clothes / textiles", material="Cotton / synthetic textile", reward_class="textile", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=0.5,
        keywords=["clothes", "shirt", "saree", "textile", "fabric", "jeans", "old clothes", "bedsheet", "shoes"],
        imagenet=["jersey", "T-shirt", "jean", "sweatshirt", "cardigan", "sock", "wool", "apron", "pajama", "trench coat", "miniskirt", "suit", "running shoe", "sandal", "Loafer", "cowboy boot", "kimono", "abaya"],
        handling="Wash and fold usable clothes.",
        disposal="Usable: donate via Reuse Exchange. Worn-out: textile recycler / dry waste.",
        destinations=["reuse_ngo", "recycler"], contamination_check="Wet textiles develop mould."),
    "furniture_wood": dict(name="Furniture / wooden item", material="Wood / board", reward_class="wood", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=8.0,
        keywords=["chair", "table", "furniture", "wood", "plank", "shelf", "cupboard", "bench", "sofa"],
        imagenet=["folding chair", "rocking chair", "dining table", "desk", "wardrobe", "chiffonier", "bookcase", "park bench", "studio couch", "china cabinet", "entertainment center"],
        handling="If usable or repairable, list it on the Reuse Exchange first.",
        disposal="Bulky waste - reuse / repair first; otherwise request a bulky-waste pickup.",
        destinations=["reuse_ngo", "scrap_dealer"], contamination_check="Termite-infested wood should not be reused indoors."),
    "tetra_pak": dict(name="Tetra Pak / beverage carton", material="Paperboard + PE + aluminium layers", reward_class="paper", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=0.03,
        keywords=["tetra pak", "juice carton", "milk carton", "frooti", "beverage carton"], imagenet=[],
        handling="Empty, rinse, flatten.",
        disposal="Dry waste - accepted by carton recyclers through MRFs where available.",
        destinations=["mrf", "recycler"], contamination_check="Milk residue causes odour."),
    "construction_debris": dict(name="Construction & demolition debris", material="Concrete / bricks / tiles", reward_class="mixed", stream="dry",
        recyclable=True, hazard=False, est_weight_kg=25.0,
        keywords=["debris", "bricks", "concrete", "tiles", "rubble", "cement", "sand", "construction"],
        imagenet=["brick"],
        handling="Do not dump on roads or in drains.",
        disposal="C&D waste - request a dedicated C&D pickup from the local authority; not household waste.",
        destinations=["recycler"], contamination_check="Keep separate from household waste."),
}

# ---------------------------------------------------------------------------------------------
# Policy and local guidance documents used for retrieval (RAG-lite, TF-IDF over approved snippets)
# ---------------------------------------------------------------------------------------------
POLICY_DOCS = [
    dict(id="swm2026-streams", source="Solid Waste Management Rules, 2026 (MoEFCC, notified 27 Jan 2026, effective 1 Apr 2026)",
         url="https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2219676", label="official",
         text="Four-stream segregation at source is mandatory: wet waste, dry waste, sanitary waste and special care waste. "
              "Wet waste is to be composted or bio-methanated; dry waste routed to material recovery facilities; sanitary waste securely "
              "wrapped and stored separately; special care waste handed over only to authorised agencies or designated collection centres."),
    dict(id="swm2026-landfill", source="Solid Waste Management Rules, 2026 - landfill restriction (summary)",
         url="https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2219676", label="official",
         text="Only non-recyclable, non-energy-recoverable waste and inert material should go to landfill. Recyclable and biodegradable "
              "material should not be landfilled as a default route."),
    dict(id="ewaste2022", source="E-Waste (Management) Rules, 2022", url="https://cpcb.nic.in/e-waste/", label="official",
         text="Electrical and electronic equipment at end of life must be channelised to registered producers' take-back systems or "
              "authorised recyclers and refurbishers. Households should not dismantle e-waste."),
    dict(id="battery2022", source="Battery Waste Management Rules, 2022", url="https://cpcb.nic.in/", label="official",
         text="Waste batteries must be returned through collection systems of producers or handed to registered recyclers. Batteries must "
              "not be disposed of with municipal solid waste or incinerated."),
    dict(id="pwm-mlp", source="Plastic Waste Management Rules (as amended)", url="https://cpcb.nic.in/plastic-waste/", label="official",
         text="Multi-layered plastic that is non-recyclable is to be used for energy recovery or co-processing. Clean plastics should be "
              "segregated so they can be recycled."),
    dict(id="tn-ewaste-rrc", source="Tamil Nadu Directorate of Municipal Administration - Solid Waste Management page",
         url="https://www.tnurbantree.tn.gov.in/sanitation-solid-waste/", label="official",
         text="E-waste is collected once in a month and stored in Resource Recovery Centres before disposing to TNPCB authorised vendors."),
    dict(id="chn-pilot-wet", source="VYARTHX Chennai pilot configuration (illustrative - to be confirmed by GCC)",
         url="", label="simulated",
         text="Wet waste is collected daily in the morning. Keep wet waste in a lidded container without plastic liners. Societies above "
              "the bulk-generator threshold should process wet waste on site where feasible."),
    dict(id="chn-pilot-dry", source="VYARTHX Chennai pilot configuration (illustrative - to be confirmed by GCC)",
         url="", label="simulated",
         text="Dry waste is collected on scheduled days and taken to Resource Recovery Centres / MRFs. Clean, dry and flattened cardboard, "
              "PET bottles, metal and glass earn higher quality grades."),
    dict(id="chn-pilot-special", source="VYARTHX Chennai pilot configuration (illustrative - to be confirmed by GCC)",
         url="", label="simulated",
         text="Special-care items such as batteries, CFL bulbs, expired medicines and paint are accepted at designated special-care "
              "collection days or authorised collection points only. Never place them in dry recyclables."),
    dict(id="chn-pilot-sanitary", source="VYARTHX Chennai pilot configuration (illustrative - to be confirmed by GCC)",
         url="", label="simulated",
         text="Sanitary waste must be wrapped in paper or a marked pouch and handed over separately to protect waste workers."),
]

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class _TfIdf:
    def __init__(self, docs: list[dict]):
        self.docs = docs
        self.tfs = [Counter(_tokens(d["text"] + " " + d["source"])) for d in docs]
        df = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(docs)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}

    def search(self, query: str, k: int = 3) -> list[dict]:
        q = Counter(_tokens(query))
        scored = []
        for doc, tf in zip(self.docs, self.tfs):
            s = sum(q[t] * tf.get(t, 0) * self.idf.get(t, 0) ** 2 for t in q)
            norm = math.sqrt(sum((c * self.idf.get(t, 0)) ** 2 for t, c in tf.items())) or 1
            if s > 0:
                scored.append((s / norm, doc))
        scored.sort(key=lambda x: -x[0])
        return [dict(doc, score=round(s, 3)) for s, doc in scored[:k]]


_index = _TfIdf(POLICY_DOCS)


def retrieve_guidance(query: str, k: int = 3) -> list[dict]:
    return _index.search(query, k)


def item(key: str) -> dict:
    d = dict(ITEMS[key])
    d["key"] = key
    d["stream_label"] = STREAMS[d["stream"]]["label"]
    return d


def match_text(text: str) -> list[tuple[str, float]]:
    """Keyword matcher used for text descriptions. Returns [(item_key, score 0..1)] best first."""
    t = " " + text.lower() + " "
    scores: dict[str, float] = {}
    for key, it in ITEMS.items():
        best = 0.0
        for kw in it["keywords"]:
            if re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", t):
                best = max(best, 0.55 + min(len(kw), 20) / 50)  # longer phrase -> more specific
        if best:
            scores[key] = best
    # context rules
    if "pizza" in t and "box" in t:
        scores["pizza_box_soiled"] = max(scores.get("pizza_box_soiled", 0), 0.95)
    if "broken" in t and ("cfl" in t or "bulb" in t or "tube" in t):
        scores["cfl_bulb"] = 0.97
    if ("medicine" in t or "tablet" in t) and ("strip" in t or "expired" in t):
        scores["expired_medicine"] = 0.96
    if any(w in t for w in ("oily", "greasy", "food stained", "soiled", "dirty")) and "container" in t:
        scores["food_container_soiled"] = max(scores.get("food_container_soiled", 0), 0.9)
    return sorted(scores.items(), key=lambda kv: -kv[1])


CONTAMINATION_WORDS = {
    "high": ["oily", "greasy", "food stained", "food-stained", "soiled", "dirty", "wet", "leftover food", "mixed", "rotten"],
    "medium": ["stain", "residue", "sticky", "damp", "crumbs"],
}


def contamination_from_text(text: str) -> str:
    t = text.lower()
    if any(w in t for w in CONTAMINATION_WORDS["high"]):
        return "high"
    if any(w in t for w in CONTAMINATION_WORDS["medium"]):
        return "medium"
    return "none"
