"""The ten specialised VYARTHX agents. Each function is a graph node: (ctx, data) -> data.
Agents *recommend and orchestrate*; deterministic services enforce balances, weights, capacities and rules."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from ..config import UPLOAD_DIR
from ..models.models import (Batch, CollectionRequest, Complaint, Event, Facility, Household, MarketListing, MarketMatch, ProcessingRecord,
                             ReuseListing, RoutePlan, SimulationRun, Submission, User, Vehicle, Ward, Worker, WorkerPayment, now)
from ..services import analytics, circular, community, complaints as cmp, events as evs, logistics as lg, marketplace as mk
from ..services import passport as pp, rewards, verification as V, vision
from ..services.common import (get_cfg, haversine_km, kb_by_id, nearest_ward, notify, policy_snippets, rec_class)
from ..services.imagehash import dhash, exif_datetime, sha256_bytes
from ..simulation import twin
from .runtime import Ctx, Halt

A_SEG, A_VER, A_REW, A_LOG, A_MUN = "Segregation Agent", "Verification Agent", "Reward Agent", "Logistics Agent", "Municipal Intelligence Agent"
A_REP, A_MKT, A_BEH, A_EVT, A_CMP = "Citizen Reporting Agent", "Marketplace Matching Agent", "Behavioural Intelligence Agent", "Event Planning Agent", "Compost & Processing Agent"
S_PASS = "Waste Passport Service"


# ---------------------------------------------------------------- helpers
def user_loc(db, user: User) -> tuple[float, float, int | None]:
    hh = db.scalars(select(Household).where(Household.user_id == user.id)).first()
    if hh:
        return hh.lat, hh.lng, hh.ward_id
    w = db.get(Ward, user.ward_id) if user.ward_id else db.scalars(select(Ward)).first()
    return (w.lat, w.lng, w.id) if w else (13.0, 80.2, None)


def retrieve_policy(query: str, k: int = 3) -> list[dict]:
    toks = set(re.findall(r"[a-z]+", query.lower()))
    scored = []
    for s in policy_snippets():
        sc = sum(2 for t in s["tags"] if t in toks) + sum(1 for t in toks if len(t) > 3 and t in s["text"].lower())
        if sc:
            scored.append((sc, s))
    scored.sort(key=lambda x: -x[0])
    return [{"title": s["title"], "text": s["text"]} for _, s in scored[:k]]


def store_evidence(img: bytes, filename: str | None) -> dict:
    sha = sha256_bytes(img)
    from PIL import Image
    import io

    fmt = (Image.open(io.BytesIO(img)).format or "JPEG").lower()
    ext = {"jpeg": "jpg"}.get(fmt, fmt)
    path = UPLOAD_DIR / f"{sha[:24]}.{ext}"
    if not path.exists():
        path.write_bytes(img)
    ex = exif_datetime(img)
    return {"sha256": sha, "phash": dhash(img), "path": path.name, "bytes": len(img), "exif_time": ex.isoformat() if ex else None, "filename": filename or ""}


def _dt(s):
    try:
        return datetime.fromisoformat(s) if s else None
    except Exception:
        return None


def _worker_of(db, user: User) -> Worker | None:
    return db.scalars(select(Worker).where(Worker.user_id == user.id)).first()


# ---------------------------------------------------------------- 1. Segregation Agent
def segregation_agent(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    cfg = get_cfg(db)
    img = d.get("image_bytes")
    cls = ctx.step(A_SEG, "Classify the item (image model + knowledge base)", lambda: vision.classify(img, d.get("text", ""), d.get("filename", ""), cfg),
                   tool="vision_classify · MobileNetV2-ONNX + KB rules", inp={"has_image": bool(img), "text": d.get("text", "")[:120]})
    d["classification"] = cls
    if cls["needs_clarification"]:
        ctx.step(A_SEG, "Confidence below threshold — requesting clarification instead of guessing",
                 lambda: {"_status": "escalated", "confidence": cls["confidence"], "candidates": cls["candidates"]}, tool="confidence_gate", retry=False)
        raise Halt("escalated", "Not enough certainty to classify — clarification requested.")
    guidance = ctx.step(A_SEG, f"Retrieve local guidance for {cls['stream']} / {cls['material']}",
                        lambda: retrieve_policy(f"{cls['stream']} {cls['material']} {cls['detected_object']} {cls['contamination']}"),
                        tool="policy_retrieve · keyword RAG over approved snippets")
    d["guidance"] = guidance
    lat, lng, _ = user_loc(db, user) if user else (13.0, 80.2, None)
    dests = ctx.step(A_SEG, "Find authorised destinations near the household", lambda: lg.rank_facilities(db, cls["destination_types"], lat, lng, 0)[:3] if cls["destination_types"] else [],
                     tool="facility_lookup")
    d["destinations"] = dests
    if cls["hazard"]:
        ctx.step(A_SEG, "Hazardous / special-care item: human-authorised handling required (agent cannot declare it safe)",
                 lambda: {"_status": "escalated", "human_review_required": True, "rule": "hazardous items are never declared safe by VYARTHX"}, tool="safety_rule", retry=False)
    return d


# ---------------------------------------------------------------- 2. Verification Agent (submission)
def verification_submission(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    cls = d["classification"]
    img = d.get("image_bytes")
    ev = {}
    if img:
        ev = ctx.step(A_VER, "Store evidence and compute SHA-256 + perceptual hash", lambda: store_evidence(img, d.get("filename")), tool="evidence_store", inp={"bytes": len(img)})
    dup = ctx.step(A_VER, "Duplicate-image check (exact + perceptual)", lambda: V.check_duplicate_image(db, ev.get("sha256", ""), ev.get("phash", ""), user.id), tool="perceptual_hash_compare")
    client_ts = _dt(d.get("client_ts"))
    ts = ctx.step(A_VER, "Timestamp validation (device time + EXIF)", lambda: V.check_timestamp(client_ts, _dt(ev.get("exif_time"))), tool="timestamp_validator")
    vel = ctx.step(A_VER, "Submission velocity / suspicious-pattern check", lambda: V.check_velocity(db, user.id), tool="rule_engine")
    flags = list(ts["flags"]) + list(vel["flags"])
    if dup["exact"]:
        flags.append({"code": "duplicate_image", "severity": "high", "detail": "Identical image already submitted" + (" by this account" if dup["same_user"] else "")})
    elif dup["near"]:
        flags.append({"code": "near_duplicate_image", "severity": "high" if dup["same_user"] else "medium", "detail": "Perceptually near-identical image found"})
    risk = V.risk_score(flags)
    passed = not any(f["severity"] == "high" for f in flags) and risk < 0.5
    lat, lng, ward_id = user_loc(db, user)
    hh = db.scalars(select(Household).where(Household.user_id == user.id)).first()

    def create():
        sub = Submission(user_id=user.id, household_id=hh.id if hh else None, ward_id=ward_id, image_path=ev.get("path", ""), sha256=ev.get("sha256", ""),
                         phash=ev.get("phash", ""), description=d.get("text", "")[:500], client_ts=client_ts, detected_object=cls["detected_object"],
                         material=cls["material"], material_key=cls["material_key"], stream=cls["stream"], confidence=cls["confidence"], contamination=cls["contamination"],
                         est_weight_kg=float(d.get("est_weight_kg") or 0.5), status="verified" if passed else "flagged",
                         classification={k: v for k, v in cls.items() if k not in ("image_top5",)}, verification={"flags": flags, "risk": risk, "duplicate": dup, "evidence": ev},
                         run_id=ctx.run.id, data_class=rec_class())
        db.add(sub)
        db.flush()
        return {"submission_id": sub.id, "status": sub.status, "risk": risk, "flags": flags, "estimated_weight_note": "citizen-entered estimate, not a verified weight"}

    out = ctx.step(A_VER, "Validate submission and write evidence record", create, tool="db.submissions.insert")
    d["submission_id"] = out["submission_id"]
    d["verification"] = {"passed": passed, "risk": risk, "flags": flags}
    if not passed:
        notify(db, user.id, "Submission needs review", "Your submission was flagged by automated checks and will not earn points until reviewed.", "info")
        raise Halt("escalated", "Verification flags: " + "; ".join(f["detail"] for f in flags))
    return d


# ---------------------------------------------------------------- 3. Reward Agent (provisional)
def reward_provisional(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    sub = db.get(Submission, d["submission_id"])
    cls = d["classification"]
    ctx.step(A_REW, "Assess provisional-reward eligibility", lambda: {"eligible": cls["reward_eligible"], "confidence": cls["confidence"], "note": cls["reward_note"],
                                                                          "rule": "Agent recommends; backend ledger enforces and computes amounts"}, tool="reward_policy")
    led = ctx.step(A_REW, "Request provisional credit from the backend ledger", lambda: rewards.provisional_award(db, user.id, sub), tool="ledger.provisional_credit · deterministic")
    d["reward"] = led
    if led.get("credited"):
        notify(db, user.id, "Provisional GreenPoints", f"+{led['credited']} provisional points. Confirm handover to unlock verified points.", "reward")
    return d


# ---------------------------------------------------------------- 4. Logistics Agent (options)
def logistics_options(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    sub = db.get(Submission, d["submission_id"])
    cls = d["classification"]
    lat, lng, ward_id = user_loc(db, user)

    def find():
        workers = lg.rank_workers(db, ward_id, lat, lng, sub.est_weight_kg, cls["stream"])[:3]
        facs = lg.rank_facilities(db, cls["destination_types"], lat, lng, sub.est_weight_kg, cls["material_key"])[:3] if cls["destination_types"] else []
        base = now().replace(minute=0, second=0, microsecond=0)
        slots = [(base + timedelta(days=1)).replace(hour=h).isoformat() for h in (9, 17)] + [(base + timedelta(days=2)).replace(hour=9).isoformat()]
        return {"collectors": workers, "facilities": facs, "slots": slots, "special_care_required": cls["stream"] == "special",
                "capacity_check": "worker capacity and facility headroom verified" if (workers and (facs or not cls["destination_types"])) else "limited availability"}

    opts = ctx.step(A_LOG, "Find collectors, capacity and an accepting facility", find, tool="collector_match + facility_capacity_check")
    d["collection_options"] = opts
    return d


# ---------------------------------------------------------------- 4b. Logistics Agent (schedule)
def logistics_schedule(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    sub = db.get(Submission, d["submission_id"]) if d.get("submission_id") else None
    kind = d.get("kind", "household")
    stream = d.get("stream") or (sub.stream if sub else "dry")
    material_key = d.get("material_key") or (sub.material_key if sub else "mixed")
    weight = float(d.get("est_weight_kg") or (sub.est_weight_kg if sub else 1.0))
    lat, lng, ward_id = user_loc(db, user)
    hh = db.scalars(select(Household).where(Household.user_id == user.id)).first()
    if sub and sub.status in ("flagged",):
        raise Halt("escalated", "Flagged submissions cannot be scheduled until reviewed.")
    if sub and sub.status in ("collected", "completed"):
        raise Halt("rejected", "Submission already collected.")
    existing = db.scalars(select(CollectionRequest).where(CollectionRequest.submission_id == sub.id, CollectionRequest.status.notin_(["cancelled", "rejected_by_worker"]))).first() if sub else None
    if existing:
        d["collection_id"] = existing.id
        ctx.step(A_LOG, "Pickup already exists for this submission (duplicate request prevented)", lambda: {"collection_id": existing.id, "status": existing.status}, tool="duplicate_guard")
        return d
    slot = _dt(d.get("slot")) or (now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    cands = ctx.step(A_LOG, "Match collector (distance, capacity, special-care training)", lambda: lg.rank_workers(db, ward_id, lat, lng, weight, stream), tool="collector_match")
    dest = {"collect": ["special_care", "ewaste"] if stream == "special" else (["compost", "biomethanation"] if stream == "wet" else ["mrf", "recycler"])}
    facs = ctx.step(A_LOG, "Check accepting facility and processing capacity", lambda: lg.rank_facilities(db, dest["collect"], lat, lng, weight, material_key), tool="facility_capacity_check")

    def create():
        c = CollectionRequest(submission_id=sub.id if sub else None, user_id=user.id, household_id=hh.id if hh else None, ward_id=ward_id, kind=kind, stream=stream,
                              material_key=material_key, status="requested", priority=1 if stream == "special" else 2, est_weight_kg=weight, lat=lat, lng=lng,
                              scheduled_for=slot, facility_id=facs[0]["facility_id"] if facs else None, data_class=rec_class(),
                              notes=d.get("notes", "")[:280])
        if cands:
            c.suggested_worker_id = cands[0]["worker_id"]
            c.worker_id = cands[0]["worker_id"]
            c.status = "assigned"
        db.add(c)
        if sub:
            sub.status = "scheduled"
        db.flush()
        return {"collection_id": c.id, "status": c.status, "worker": cands[0]["worker_code"] if cands else None, "facility": facs[0]["name"] if facs else None,
                "scheduled_for": slot.isoformat(), "route_note": "Assignment is a recommendation; the collector can accept or reject."}

    out = ctx.step(A_LOG, "Create pickup request and assign collector", create, tool="db.collection_requests.insert")
    d["collection_id"] = out["collection_id"]
    d["schedule"] = out
    c = db.get(CollectionRequest, out["collection_id"])
    if c.worker_id:
        w = db.get(Worker, c.worker_id)
        notify(db, w.user_id, "New pickup request", f"Pickup #{c.id} ({stream}, ~{weight:g} kg) on {slot:%d %b %H:%M}.", "task")
    notify(db, user.id, "Pickup scheduled", f"Pickup #{c.id} requested for {slot:%d %b, %H:%M}.", "pickup")
    if not cands:
        ctx.step(A_LOG, "No suitable collector available (special-care training / capacity) — escalating to municipal service",
                 lambda: {"_status": "escalated", "stream": stream}, tool="escalation", retry=False)
        raise Halt("escalated", "No trained collector available; request is queued for the municipal special-care service.")
    return d


# ---------------------------------------------------------------- 2b. Verification Agent (collection handover)
def verification_collection(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    col = db.get(CollectionRequest, d["collection_id"])
    cfg = get_cfg(db)
    worker = _worker_of(db, user)
    if not worker:
        raise Halt("rejected", "Only registered waste workers can confirm collections.")
    ctx.step("Collector", f"{worker.worker_code} confirms handover at the household", lambda: {"weight_kg": d.get("weight_kg"), "qr": bool(d.get("qr_code")), "weight_source": d.get("weight_source", "manual_entry")},
             actor_type="human", tool="worker_portal.confirm", retry=False)
    if col.status in ("collected", "delivered", "completed"):
        raise Halt("rejected", "Collection already confirmed — duplicate confirmation ignored.")
    if col.worker_id and col.worker_id != worker.id:
        raise Halt("rejected", "This pickup is assigned to a different collector.")
    hh = db.get(Household, col.household_id) if col.household_id else None
    qr = ctx.step(A_VER, "Verify household QR / ID", lambda: V.check_qr(d.get("qr_code"), hh), tool="qr_verify")
    wt = float(d.get("weight_kg") or 0)
    wchk = ctx.step(A_VER, "Weight-record consistency check", lambda: V.check_weight(db, col, wt, cfg, worker.capacity_kg), tool="weight_rules + anomaly z-score")
    flags = list(wchk["flags"])
    if qr["status"] == "mismatch":
        flags.append({"code": "qr_mismatch", "severity": "high", "detail": qr["detail"]})
    elif qr["status"] == "missing":
        flags.append({"code": "qr_missing", "severity": "medium", "detail": "No QR / household code supplied — manual ID recommended"})
    sub = db.get(Submission, col.submission_id) if col.submission_id else None
    if sub and sub.status in ("flagged",):
        flags.append({"code": "submission_flagged", "severity": "high", "detail": "Underlying submission was flagged"})
    risk = V.risk_score(flags)
    passed = not any(f["severity"] == "high" for f in flags) and risk < 0.5
    out = ctx.step(A_VER, "Decide handover validity and record evidence", lambda: {"passed": passed, "risk": risk, "flags": flags, "evidence": {"weight_source": d.get("weight_source", "manual_entry"), "note": d.get("evidence_note", "")[:200]}},
                   tool="rule_engine")
    d["verification"] = out
    if not passed:
        col.evidence = {**(col.evidence or {}), "rejected_confirmation": {"flags": flags, "at": now().isoformat()}}
        raise Halt("escalated", "Handover failed verification: " + "; ".join(f["detail"] for f in flags if f["severity"] == "high"))

    def commit():
        col.verified_weight_kg = wt
        col.weight_source = d.get("weight_source", "manual_entry")
        col.status = "collected"
        col.collected_at = now()
        col.worker_id = worker.id
        col.qr_verified = qr["status"] == "match"
        col.evidence = {**(col.evidence or {}), "weight_note": d.get("evidence_note", "")[:200], "flags": flags, "qr": qr["status"], "photo": d.get("photo_ref", "")}
        if sub:
            sub.status = "collected"
        return {"collection_id": col.id, "status": col.status, "verified_weight_kg": wt}

    ctx.step(A_VER, "Mark collection as confirmed", commit, tool="db.collection_requests.update")
    return d


# ---------------------------------------------------------------- 3b. Reward Agent (verified)
def reward_verified(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    col = db.get(CollectionRequest, d["collection_id"])
    sub = db.get(Submission, col.submission_id) if col.submission_id else None
    cont = sub.contamination if sub else "none"
    ctx.step(A_REW, "Calculate verified points from verified weight × material rate × quality + behaviour bonus", lambda: rewards.compute_points(get_cfg(db), col.material_key, col.verified_weight_kg, cont, col.stream, rewards.streak_days(db, col.user_id) + 1),
             tool="reward_formula · deterministic")
    res = ctx.step(A_REW, "Credit wallet via ledger (idempotent, duplicate-proof)", lambda: rewards.verified_award(db, col, col.verified_weight_kg, cont), tool="ledger.verified_credit")
    d["reward"] = res
    if res.get("credited"):
        notify(db, col.user_id, "GreenPoints verified", f"+{res['credited']} verified points for pickup #{col.id}.", "reward")
    return d


# ---------------------------------------------------------------- Passport Service
def passport_collection(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    col = db.get(CollectionRequest, d["collection_id"])
    sub = db.get(Submission, col.submission_id) if col.submission_id else None
    owner = db.get(User, col.user_id)
    worker = db.get(Worker, col.worker_id)
    wuser = db.get(User, worker.user_id)
    ward = db.get(Ward, col.ward_id) if col.ward_id else None

    def go():
        b = db.get(Batch, col.batch_id) if col.batch_id else None
        if not b:
            b = pp.create_batch(db, col, material=sub.material if sub else col.material_key)
        b.input_kg = col.verified_weight_kg
        b.status = "collected"
        if not b.material:
            b.material = (sub.material if sub else col.material_key) or ""
        loc = f"{ward.name}" if ward else "Pilot ward"
        pp.add_event(db, b, "household", "Segregated waste recorded", owner.name, "citizen", loc, col.est_weight_kg, "recorded",
                     evidence=(sub.image_path if sub else ""), meta={"stream": col.stream, "contamination": sub.contamination if sub else "n/a", "weight_basis": "citizen estimate"}, ts=(sub.created_at if sub else None))
        pp.add_event(db, b, "collector", "Pickup confirmed by collector", worker.worker_code, "worker", loc, col.verified_weight_kg, "verified",
                     evidence=f"QR {col.evidence.get('qr', 'n/a')}; {col.weight_source}", meta={"qr": col.qr_verified, "flags": [f['code'] for f in col.evidence.get('flags', [])]})
        return {"batch_id": b.id, "passport": b.code, "events": 2, "chain": pp.verify_chain(db, b)}

    out = ctx.step(S_PASS, "Create Waste Passport and append household + collector events", go, tool="passport.append (hash-chained)")
    d["passport"] = out
    # simulated worker earnings
    cfg = get_cfg(db)
    fee = max(float(cfg["worker_min_fee_inr"]), col.verified_weight_kg * float(cfg["worker_fee_inr_per_kg"]))

    def pay():
        if not db.scalars(select(WorkerPayment).where(WorkerPayment.worker_id == worker.id, WorkerPayment.collection_id == col.id)).first():
            db.add(WorkerPayment(worker_id=worker.id, collection_id=col.id, amount_inr=round(fee, 2), note="Collection fee (simulated record — no real payment made)"))
        return {"amount_inr": round(fee, 2), "status": "recorded_simulated", "note": "VYARTHX does not transfer real money."}

    ctx.step("Worker Earnings Service", "Record collection fee in earnings ledger (simulated)", pay, actor_type="service", tool="earnings.record")
    return d


# ---------------------------------------------------------------- 7. Marketplace Matching Agent (downstream)
def marketplace_downstream(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    col = db.get(CollectionRequest, d["collection_id"])
    b = db.get(Batch, d["passport"]["batch_id"])
    if col.stream not in ("dry", "special"):
        return d
    sub = db.get(Submission, col.submission_id) if col.submission_id else None

    def find():
        virt = MarketListing(user_id=col.user_id, kind="supply", material_key=col.material_key if col.material_key in mk.COMPAT else "paper", quantity_kg=col.verified_weight_kg, remaining_kg=col.verified_weight_kg,
                             contamination=(sub.contamination if sub else "none"), lat=col.lat, lng=col.lng)
        best = None
        for dem in db.scalars(select(MarketListing).where(MarketListing.kind == "demand", MarketListing.status == "open")).all():
            sc = mk.score_pair(virt, dem)
            if sc and (best is None or sc["score"] > best[1]["score"]):
                best = (dem, sc)
        if best:
            dem, sc = best
            fac = db.get(Facility, dem.facility_id) if dem.facility_id else None
            return {"match": True, "demand_listing_id": dem.id, "recycler": fac.name if fac else f"Recycler #{dem.user_id}", "score": sc["score"], "distance_km": sc["distance_km"],
                    "demand_material": dem.material_key, "status": "suggested — recycler has not confirmed"}
        dest = lg.rank_facilities(db, ["recycler", "mrf"], col.lat, col.lng, 0)[:1]
        return {"match": False, "fallback_facility": dest[0]["name"] if dest else None, "status": "no open recycler demand matched; MRF routing suggested"}

    out = ctx.step(A_MKT, "Find a downstream recycler / processor", find, tool="material_match (compatibility × quantity × distance)")
    d["downstream"] = out
    pp.add_event(db, b, "recycler", "Downstream destination suggested", out.get("recycler") or out.get("fallback_facility") or "—", "agent", "", None, "suggested",
                 meta={"note": "Suggestion only — not a confirmation by the recycler", **out})
    return d


# ---------------------------------------------------------------- 10. Compost & Processing Agent (route suggestion)
def compost_route(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    col = db.get(CollectionRequest, d["collection_id"])
    if col.stream != "wet":
        return d
    b = db.get(Batch, d["passport"]["batch_id"])
    cfg = get_cfg(db)

    def go():
        facs = lg.rank_facilities(db, ["compost", "biomethanation"], col.lat, col.lng, col.verified_weight_kg, "organic")[:2]
        est = round(col.verified_weight_kg * cfg["compost_yield"]["windrow"], 2)
        return {"facilities": facs, "estimated_compost_kg": est, "label": "ESTIMATE — yield is a configurable assumption", "data_class": "estimate"}

    out = ctx.step(A_CMP, "Match organic feedstock to composting / biomethanation capacity", go, tool="feedstock_match + yield_estimator")
    d["compost"] = out
    pp.add_event(db, b, "mrf", "Processing route suggested (wet)", out["facilities"][0]["name"] if out["facilities"] else "—", "agent", "", None, "suggested", meta=out)
    return d


# ---------------------------------------------------------------- 8. Behavioural Intelligence Agent
def behaviour_update(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    col = db.get(CollectionRequest, d["collection_id"])
    owner = db.get(User, col.user_id)

    def go():
        rules = ["verified_submissions"]
        if col.stream == "special":
            rules.append("ewaste")
        if col.stream == "wet":
            rules.append("compost")
        done = []
        for r in rules:
            done += community.on_verified_event(db, owner.id, r)
        prof = community.behaviour_profile(db, owner)
        for c in done:
            notify(db, owner.id, "Challenge completed", f"{c['challenge']}: +{c['points']} points", "reward")
        return {"streak_days": prof["streak_days"], "segregation_score": prof["segregation_score"], "challenges_completed": done, "nudges": [n["title"] for n in prof["nudges"]][:3]}

    d["behaviour"] = ctx.step(A_BEH, "Update streak, challenge progress and personalised nudges", go, tool="behaviour_profile + challenge_hook")
    return d


# ---------------------------------------------------------------- 5. Municipal Intelligence Agent (stats refresh)
def municipal_update(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    cid = d.get("collection_id")
    col = db.get(CollectionRequest, cid) if cid else None
    wid = col.ward_id if col else d.get("ward_id")

    def go():
        w = db.get(Ward, wid) if wid else None
        stats = analytics.platform_stats(db, 30, wid)
        city = analytics.platform_stats(db, 30, None)
        return {"ward": w.name if w else "city", "ward_stats": stats, "city_stats": city, "note": "Platform-recorded activity feeds the Command Centre; city baseline remains simulated."}

    d["municipal"] = ctx.step(A_MUN, "Update ward and city statistics from verified activity", go, tool="analytics.platform_stats")
    return d


# ---------------------------------------------------------------- Facility: receive
def facility_receive(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    b = db.get(Batch, d["batch_id"])
    fac = db.get(Facility, user.facility_id) if user.facility_id else None
    if not b or not fac:
        raise Halt("rejected", "Batch or facility not found for this user.")
    if b.status not in ("collected", "at_household"):
        raise Halt("rejected", f"Batch is '{b.status}' and cannot be received.")
    rec = float(d.get("received_kg") or 0)
    chk = ctx.step(A_VER, "Compare received weight with collector-recorded weight", lambda: {"input_kg": b.input_kg, "received_kg": rec,
                   "deviation_pct": round(100 * (rec - b.input_kg) / b.input_kg, 1) if b.input_kg else None, "flag": abs(rec - b.input_kg) > 0.1 * max(b.input_kg, 0.5)}, tool="weight_consistency")
    cap = ctx.step(A_LOG, "Facility capacity & acceptance check", lambda: {"facility": fac.name, "authorised": fac.authorised, "headroom_t": round(fac.capacity_tpd - fac.load_tpd, 2),
                   "accepts": fac.accepts, "downtime": fac.downtime}, tool="facility_capacity_check")
    if not fac.authorised or fac.downtime:
        raise Halt("escalated", "Facility is not authorised or is under downtime; receipt cannot be recorded.")

    def go():
        b.current_facility_id = fac.id
        b.status = "at_facility"
        b.input_kg = b.input_kg or rec
        stage = "recycler" if fac.type in ("recycler",) else "mrf"
        pp.add_event(db, b, stage, "Batch received at facility", fac.name, "facility", fac.name, rec, "flagged" if chk["flag"] else "verified",
                     evidence=d.get("note", "")[:200], meta={"deviation_pct": chk["deviation_pct"], "facility_type": fac.type})
        for c in db.scalars(select(CollectionRequest).where(CollectionRequest.batch_id == b.id)).all():
            c.status = "delivered"
            c.facility_id = fac.id
        return {"passport": b.code, "status": b.status, "flag": chk["flag"]}

    d["receipt"] = ctx.step(S_PASS, "Append facility receipt event to Waste Passport", go, tool="passport.append")
    return d


# ---------------------------------------------------------------- Facility: process
def facility_process(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    b = db.get(Batch, d["batch_id"])
    fac = db.get(Facility, user.facility_id) if user.facility_id else None
    if not b or not fac:
        raise Halt("rejected", "Batch or facility not found.")
    if b.status not in ("at_facility", "processing"):
        raise Halt("rejected", f"Batch must be received first (current status: {b.status}).")
    rec, rej, loss, oth, resid = (float(d.get(k) or 0) for k in ("recovered_kg", "rejects_kg", "loss_kg", "other_kg", "residual_kg"))
    resid = resid or rej
    if min(rec, rej, loss, oth, resid) < 0:
        raise Halt("rejected", "Quantities cannot be negative.")
    acc = rec + rej + loss + oth
    mb = ctx.step(A_VER, "Mass-balance check: input = recovered + rejects + loss + other", lambda: {"input_kg": b.input_kg, "accounted_kg": round(acc, 3), "discrepancy_kg": round(b.input_kg - acc, 3),
                   "tolerance_kg": round(max(0.02 * b.input_kg, 0.05), 3)}, tool="mass_balance")
    if abs(mb["discrepancy_kg"]) > mb["tolerance_kg"]:
        raise Halt("escalated", f"Mass balance does not close (discrepancy {mb['discrepancy_kg']} kg). Correct the quantities or record the difference as loss/other.")
    if resid > rej + 1e-9:
        raise Halt("rejected", "Residual to disposal cannot exceed recorded rejects.")
    cfg = get_cfg(db)
    est = {}
    if b.stream == "wet" or b.material_key == "organic":
        est = ctx.step(A_CMP, "Estimate compost / biogas output (labelled estimate)", lambda: {"compost_kg_estimate": round(rec * cfg["compost_yield"]["windrow"], 2),
                       "biogas_m3_estimate": round(rec / 1000 * cfg["biogas_m3_per_tonne"], 2), "label": "ESTIMATE until facility output records exist", "data_class": "estimate"}, tool="yield_estimator")

    def go():
        pr = ProcessingRecord(batch_id=b.id, facility_id=fac.id, process=fac.type, input_kg=b.input_kg, recovered_kg=rec, rejects_kg=rej, loss_kg=loss, other_kg=oth, residual_kg=resid,
                              output_estimate=est, confirmed_by=user.id, data_class=rec_class())
        db.add(pr)
        db.flush()
        b.recovered_kg, b.rejects_kg, b.loss_kg, b.other_kg, b.residual_kg = rec, rej, loss, oth, resid
        b.residual_destination = d.get("residual_destination", "") or ""
        b.status = pp.final_status(b)
        stage = "recycler" if fac.type == "recycler" else "mrf"
        pp.add_event(db, b, stage, "Sorting / processing record", fac.name, "facility", fac.name, rec, "verified",
                     meta={"recovered_kg": rec, "rejects_kg": rej, "loss_kg": loss, "other_kg": oth, "output_estimate": est or None})
        if resid > 0:
            pp.add_event(db, b, "residual", "Residual handling recorded", fac.name, "facility", b.residual_destination or "destination not specified", resid, "recorded",
                         meta={"destination": b.residual_destination})
        mbf = pp.mass_balance(b)
        pp.add_event(db, b, "final", f"Final status: {pp.STATUS_TEXT.get(b.status, b.status)}", fac.name, "facility", "", b.input_kg, "verified",
                     meta={"mass_balance": mbf, "recovery_rate": mbf["recovery_rate"]})
        if b.stream == "special":
            ack = f"ACK-{b.code}-{uuid.uuid4().hex[:5].upper()}"
            pp.add_event(db, b, "final", "Disposal acknowledgement (demo certificate)", fac.name, "facility", fac.name, b.input_kg, "verified", evidence=ack,
                         meta={"note": "Simulated acknowledgement; real certificates require an authorised provider integration."})
        return {"processing_record": pr.id, "batch_status": b.status, "mass_balance": mbf, "statement": f"{rec:g} of {b.input_kg:g} kg recovered ({100*mbf['recovery_rate']:.0f}%) — not the full input."}

    d["processing"] = ctx.step(S_PASS, "Record processing, rejects, residual and final status", go, tool="passport.append + processing_record")
    pr_id = d["processing"]["processing_record"]
    if rec > 0 and b.owner_user_id:
        d["final_reward"] = ctx.step(A_REW, "Credit recovery bonus (facility-confirmed quantity only)", lambda: rewards.final_award(db, b.owner_user_id, b.id, pr_id, b.material_key, rec), tool="ledger.final_credit")
        if d["final_reward"].get("credited"):
            notify(db, b.owner_user_id, "Recovery bonus", f"+{d['final_reward']['credited']} points — {b.code}: {rec:g} kg recovered by {fac.name}.", "reward")
    if rec > 0 and b.material_key not in ("organic", "sanitary", "special", "mixed"):
        def publish():
            lst = MarketListing(user_id=user.id, facility_id=fac.id, kind="supply", material_key=b.material_key if b.material_key in mk.COMPAT else "paper", title=f"Recovered {b.material or b.material_key} from {b.code}",
                                quantity_kg=rec, remaining_kg=rec, condition="sorted", contamination="none", lat=fac.lat, lng=fac.lng, ward_id=fac.ward_id, pickup_window="By arrangement",
                                seller_type="MRF", verification="facility_confirmed", data_class=rec_class())
            db.add(lst)
            db.flush()
            ms = mk.recommend(db, supply_id=lst.id)
            return {"listing_id": lst.id, "recommended_matches": len(ms)}
        d["marketplace"] = ctx.step(A_MKT, "List recovered material and look for recycler demand", publish, tool="marketplace.publish + match")
    d["municipal"] = None
    col = db.scalars(select(CollectionRequest).where(CollectionRequest.batch_id == b.id)).first()
    if col:
        for c in db.scalars(select(CollectionRequest).where(CollectionRequest.batch_id == b.id)).all():
            c.status = "completed"
            if c.submission_id:
                s = db.get(Submission, c.submission_id)
                if s:
                    s.status = "completed"
        d["collection_id"] = col.id
    d = municipal_update(ctx, {**d, "ward_id": b.ward_id})
    return d


# ---------------------------------------------------------------- 6. Citizen Reporting Agent + complaint verification
def reporting_agent(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    img = d.get("image_bytes")
    label = ""
    ev = {}
    if img:
        ev = ctx.step(A_REP, "Fingerprint attached photo", lambda: store_evidence(img, d.get("filename")), tool="evidence_store")
        cl = ctx.step(A_REP, "Identify waste visible in the photo", lambda: vision.classify(img, d.get("description", ""), d.get("filename", "")), tool="vision_classify")
        label = cl.get("detected_object", "") if not cl.get("needs_clarification") else ""
    txt = d.get("description", "")
    cls = ctx.step(A_REP, f"Convert {d.get('source', 'text')} report into a structured complaint", lambda: cmp.classify_text(txt, label), tool="complaint_classifier · keyword rules")
    lat, lng = float(d.get("lat") or 0), float(d.get("lng") or 0)
    if not lat or not lng:
        ulat, ulng, _ = user_loc(db, user)
        lat, lng = ulat, ulng
        loc_src = "reporter's registered ward/household (no GPS supplied)"
    else:
        loc_src = "device-supplied location"
    ward = ctx.step(A_REP, "Identify location and recommend ward assignment", lambda: (lambda w: {"ward_id": w.id, "ward": w.name, "location_source": loc_src, "lat": lat, "lng": lng})(nearest_ward(db, lat, lng)),
                    tool="geo_ward_lookup")
    dup = ctx.step(A_REP, "Detect potential duplicate complaints", lambda: (lambda c: {"duplicate_of": c.id if c else None, "reason": "same category within 150 m in last 7 days" if c else "none"})(cmp.find_duplicate(db, lat, lng, cls["category"], ev.get("phash", ""))),
                   tool="duplicate_detector")

    def create():
        c = Complaint(user_id=user.id, ward_id=ward["ward_id"], category=cls["category"], description=txt[:800], source=d.get("source", "text"), lat=lat, lng=lng,
                      image_path=ev.get("path", ""), phash=ev.get("phash", ""), priority=cls["priority"], classification={**cls, **ward}, data_class=rec_class())
        db.add(c)
        db.flush()
        cmp.push_history(c, "submitted", user.name, "Report submitted")
        cmp.push_history(c, "ai_classified", A_REP, f"Category: {cls['category']} (confidence {cls['confidence']})")
        if dup["duplicate_of"]:
            parent = db.get(Complaint, dup["duplicate_of"])
            parent.repeat_count += 1
            if parent.repeat_count >= 3:
                parent.priority = 1
            c.duplicate_of = parent.id
            cmp.push_history(c, "merged", A_REP, f"Merged into #{parent.id} — repeated report ({parent.repeat_count})")
            cmp.push_history(parent, parent.status, A_REP, f"Repeat report #{c.id} received")
        return {"complaint_id": c.id, "status": c.status, "duplicate_of": c.duplicate_of}

    out = ctx.step(A_REP, "Create structured complaint record", create, tool="db.complaints.insert")
    d.update(complaint_id=out["complaint_id"], complaint=out, ward_id=ward["ward_id"])
    return d


def verification_complaint(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    c = db.get(Complaint, d["complaint_id"])

    def go():
        flags = []
        if not (12.7 <= c.lat <= 13.4 and 79.9 <= c.lng <= 80.4):
            flags.append({"code": "outside_pilot_area", "severity": "medium", "detail": "Location outside the Greater Chennai pilot area"})
        n = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.user_id == user.id, Complaint.created_at >= now() - timedelta(hours=1))) or 0
        if n > 6:
            flags.append({"code": "report_burst", "severity": "high", "detail": f"{n} reports in an hour"})
        dup_img = False
        if c.phash:
            for o in db.scalars(select(Complaint).where(Complaint.id != c.id, Complaint.phash != "").limit(500)).all():
                from ..services.imagehash import hamming
                if hamming(o.phash, c.phash) <= 3 and o.user_id == user.id:
                    dup_img = True
        if dup_img:
            flags.append({"code": "reused_photo", "severity": "medium", "detail": "Same photo used in a previous report by this account"})
        return {"flags": flags, "passed": not any(f["severity"] == "high" for f in flags), "has_photo": bool(c.image_path)}

    out = ctx.step(A_VER, "Validate report (geo sanity, burst, reused photo)", go, tool="rule_engine")
    if out["passed"] and c.status != "merged":
        cmp.push_history(c, "verified", A_VER, "Automated checks passed" + ("" if out["has_photo"] else " (no photo evidence)"))
    d["complaint_verification"] = out
    return d


def municipal_complaint(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    c = db.get(Complaint, d["complaint_id"])

    def go():
        hs = [h for h in cmp.hotspot_clusters(db) if abs(h["lat"] - c.lat) < 0.004 and abs(h["lng"] - c.lng) < 0.004]
        w = db.get(Ward, c.ward_id)
        officers = db.scalars(select(User).where(User.role == "municipal", User.ward_id == c.ward_id)).all() or db.scalars(select(User).where(User.role == "municipal")).all()
        for o in officers[:1]:
            notify(db, o.id, "New complaint in your ward", f"#{c.id} {c.category.replace('_', ' ')} in {w.name}", "task")
        return {"ward": w.name, "queue": "officer review", "repeat_hotspot": bool(hs), "hotspot_reports": hs[0]["count"] if hs else 1, "priority": c.priority,
                "recommendation": "Prioritise inspection — repeated hotspot" if hs else "Standard ward queue"}

    d["municipal"] = ctx.step(A_MUN, "Place in ward queue, check hotspot history, notify officer", go, tool="ward_queue + hotspot_analysis")
    return d


# ---------------------------------------------------------------- Route planning
def municipal_demand(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    ward_ids = d.get("ward_ids") or None

    def go():
        from ..services import forecast as fc

        f = fc.forecast(db, 7)
        rows = []
        for w in db.scalars(select(Ward)).all():
            if ward_ids and w.id not in ward_ids:
                continue
            fs = next((s for s in f.get("series", []) if s["ward_id"] == w.id), None)
            rows.append(lg.ward_demand_estimate(db, w, fs["mean_t_per_day"] if fs else None))
        return {"wards": rows, "forecast_model": f.get("model"), "data_class": "estimate"}

    d["demand"] = ctx.step(A_MUN, "Estimate ward-level collection demand (forecast + pending pickups)", go, tool="forecast + demand_estimator")
    return d


def logistics_plan(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    ward_ids = d.get("ward_ids") or None
    unavailable = d.get("unavailable_vehicle_ids") or None
    plan = ctx.step(A_LOG, "Optimise capacity-aware routes (OR-Tools VRP, priority-weighted)", lambda: lg.plan_routes(db, ward_ids, unavailable), tool="ortools.vrp")
    group = f"PLAN-{uuid.uuid4().hex[:6].upper()}"

    def save():
        ids = []
        for r in plan["routes"]:
            rp = RoutePlan(ward_id=ward_ids[0] if ward_ids and len(ward_ids) == 1 else None, vehicle_id=r["vehicle_id"], facility_id=None,
                           stops=[{k: v for k, v in s.items()} for s in r["stops"]], distance_km=r["distance_km"], load_kg=r["load_kg"], est_fuel_l=r["est_fuel_l"],
                           status="proposed", solver=plan["solver"], distance_basis=plan["distance_basis"], plan_group=group)
            db.add(rp)
            db.flush()
            ids.append(rp.id)
        return {"plan_group": group, "route_plan_ids": ids}

    saved = ctx.step(A_LOG, "Save route proposals (not dispatched)", save, tool="db.route_plans.insert")
    d["plan"] = {k: v for k, v in plan.items()}
    d["plan_group"] = group
    d["route_plan_ids"] = saved["route_plan_ids"]
    if plan["unserved"]:
        d["alternatives"] = ctx.step(A_LOG, f"{len(plan['unserved'])} stop(s) unserved — recommend alternatives", lambda: {"unserved": [{"label": s['label'], "demand_kg": s['demand_kg']} for s in plan["unserved"]],
                                      "suggestions": ["Add a vehicle or second trip in the affected ward", "Borrow spare capacity from the nearest ward", "Defer low-priority pickups to the next round"]}, tool="alternative_routes")
    return d


def approval_gate_route(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    if not d.get("route_plan_ids"):
        return d
    plan = d["plan"]
    a = ctx.request_approval("route_dispatch", f"Approve {len(d['route_plan_ids'])} proposed route(s) — {d['plan_group']}",
                             {"plan_group": d["plan_group"], "routes": len(d["route_plan_ids"]), "km": round(sum(r['distance_km'] for r in plan['routes']), 1), "load_kg": round(sum(r['load_kg'] for r in plan['routes']), 1)})
    ctx.step("Orchestrator", "Human approval required before any vehicle is dispatched", lambda: {"approval_id": a.id, "required_role": "municipal"},
             approval="pending", tool="approval_gate", retry=False, actor_type="orchestrator")
    d["approval_id"] = a.id
    raise Halt("awaiting_approval", "Municipal approval required before dispatch.")


# ---------------------------------------------------------------- Marketplace workflows
def marketplace_recommend(ctx: Ctx, d: dict) -> dict:
    db = ctx.db

    def go():
        ms = mk.recommend(db, demand_id=d.get("demand_id"), supply_id=d.get("supply_id"))
        rows = []
        for m in ms:
            s, dm = db.get(MarketListing, m.supply_id), db.get(MarketListing, m.demand_id)
            rows.append({"match_id": m.id, "supply": s.title or s.material_key, "demand": dm.title or dm.material_key, "qty_kg": m.qty_kg, "score": m.score, "distance_km": m.distance_km, "status": m.status})
        return {"matches": rows, "count": len(rows)}

    d["matches"] = ctx.step(A_MKT, "Match material supply with recycler demand", go, tool="material_match")
    return d


def marketplace_request(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    m = db.get(MarketMatch, d["match_id"])
    sup, dem = db.get(MarketListing, m.supply_id), db.get(MarketListing, m.demand_id)
    if m.status not in ("recommended", "requested"):
        raise Halt("rejected", f"Match is already {m.status}.")
    chk = ctx.step(A_MKT, "Validate quantities, compatibility and availability", lambda: {"supply_remaining_kg": sup.remaining_kg, "demand_remaining_kg": dem.remaining_kg, "qty_kg": m.qty_kg,
                   "ok": sup.status == "open" and dem.status == "open" and m.qty_kg <= (sup.remaining_kg or sup.quantity_kg) + 1e-9}, tool="match_validator")
    if not chk["ok"]:
        raise Halt("rejected", "Listing is no longer open or quantity is no longer available.")
    m.status = "requested"
    m.requested_by = user.id
    owner = db.get(User, dem.user_id)
    a = ctx.request_approval("marketplace_pickup", f"Create pickup for {m.qty_kg:g} kg {sup.material_key} → {dem.title or dem.material_key}", {"match_id": m.id, "owner_user_id": dem.user_id},
                             required_role=owner.role)
    ctx.step("Orchestrator", "Counterparty approval required before a pickup request is created", lambda: {"approval_id": a.id, "approver": owner.name}, approval="pending", tool="approval_gate", retry=False, actor_type="orchestrator")
    notify(db, owner.id, "Marketplace request", f"{user.name} requested a {m.qty_kg:g} kg {sup.material_key} transfer — approve in Agent Activity Centre.", "task")
    d["approval_id"] = a.id
    raise Halt("awaiting_approval", "Awaiting counterparty approval.")


# ---------------------------------------------------------------- Event workflows
def event_plan_node(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    ev = db.get(Event, d["event_id"])
    plan = ctx.step(A_EVT, "Estimate waste by stream, collection points and volunteers", lambda: evs.plan_event(db, ev), tool="event_waste_model · configurable assumptions")
    ev.plan = plan
    d["plan"] = {k: plan[k] for k in ("estimated_total_kg", "collection_points", "volunteers_required")}
    ctx.step(A_LOG, "Suggest authorised collection / processing partners (not confirmed)", lambda: plan["partners"], tool="partner_match")
    ctx.step(A_CMP, "Identify composting destination for event food waste", lambda: {"organic_kg": plan["estimated_by_stream_kg"]["wet"],
             "facility": next((p["name"] for p in plan["partners"] if p["type"] == "compost"), None)}, tool="feedstock_match")
    return d


def event_report_node(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    ev = db.get(Event, d["event_id"])
    rep = ctx.step(A_EVT, "Compile post-event report from logged waste & participation", lambda: evs.build_report(db, ev), tool="event_report")
    ev.report = rep
    t = rep["totals"]

    def cert():
        if rep["certificate_eligible"]:
            ev.certificate = {"id": f"VX-ZW-{ev.id:04d}", "issued_at": now().isoformat(), "level": "Zero-Waste Event — verified diversion",
                              "verified_diversion_pct": round(100 * t["diversion_verified"], 1), "basis": "Partner-verified quantities only", "data_class": ev.data_class}
            return {"issued": True, **ev.certificate}
        return {"issued": False, "blockers": rep["certificate_blockers"], "note": "Organiser-reported figures alone cannot earn a certificate."}

    d["certificate"] = ctx.step(A_EVT, "Decide Zero-Waste certificate (verified evidence required)", cert, tool="certificate_rules")
    d["report"] = rep
    return d


def municipal_event(ctx: Ctx, d: dict) -> dict:
    return municipal_update(ctx, {**d, "ward_id": ctx.db.get(Event, d["event_id"]).ward_id})


# ---------------------------------------------------------------- Digital twin
def twin_node(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user

    def go():
        params = d.get("params") or {}
        res = twin.run_scenario(db, d.get("name", "Custom scenario"), params)
        sr = SimulationRun(user_id=user.id if user else None, name=res["name"], params=params, result=res)
        db.add(sr)
        db.flush()
        k, b = res["scenario"]["kpis"], res["baseline"]["kpis"]
        return {"simulation_id": sr.id, "residual_t": {"baseline": b["residual_t"], "scenario": k["residual_t"]}, "recovered_t": {"baseline": b["recovered_material_t"], "scenario": k["recovered_material_t"]},
                "end_backlog_t": k["end_backlog_t"], "bottlenecks": [x["stage"] for x in res["scenario"]["bottlenecks"]], "label": res["label"]}

    d["simulation"] = ctx.step(A_MUN, "Run Python digital-twin simulation (baseline vs scenario) and attribute drivers", go, tool="twin.simulate + leave-one-out attribution")
    return d


# ---------------------------------------------------------------- Behaviour / reuse / compost
def behaviour_review(ctx: Ctx, d: dict) -> dict:
    prof = ctx.step(A_BEH, "Analyse participation, contamination and goals", lambda: community.behaviour_profile(ctx.db, ctx.user), tool="behaviour_profile")
    d["profile"] = prof
    return d


def reuse_node(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    lst = db.get(ReuseListing, d["listing_id"])
    ai = ctx.step(A_MKT, "Identify category/condition and generate upcycling ideas", lambda: {**circular.classify_reuse(lst.title, lst.description), "ideas": circular.upcycling(lst.category)}, tool="reuse_classifier")
    if lst.category == "household" and ai["category"] != "household":
        lst.category = ai["category"]
    lst.condition = ai["condition"] if lst.condition == "good" else lst.condition
    recips = ctx.step(A_MKT, "Find reuse recipients (NGOs, schools, refurbishers)", lambda: circular.match_recipients(db, lst), tool="recipient_match")
    lst.ai = {"classification": ai, "recipients": recips, "ideas": circular.upcycling(lst.category)}
    d["ai"] = lst.ai
    return d


def compost_plan_node(ctx: Ctx, d: dict) -> dict:
    db = ctx.db
    est = ctx.step(A_CMP, "Estimate feedstock and compost output", lambda: circular.compost_estimate(db, int(d["households"]), float(d["kg_per_household_day"]), int(d["days"]), d.get("method", "windrow"), d.get("lat"), d.get("lng")),
                   tool="feedstock_estimator")
    d["estimate"] = est
    ctx.step(A_LOG, "Check facility capacity and acceptance", lambda: est.get("facilities", []), tool="facility_capacity_check")
    return d


# ---------------------------------------------------------------- Assistant
def assistant_node(ctx: Ctx, d: dict) -> dict:
    db, user = ctx.db, ctx.user
    q = (d.get("message") or "").strip()
    ql = q.lower()
    actions: list[dict] = []
    intent = "help"
    if re.search(r"\b(points|balance|wallet|greenpoints|redeem)\b", ql):
        intent = "wallet"
    elif re.search(r"\b(event|festival|volunteer)\b", ql):
        intent = "events"
    elif re.search(r"\b(pickup|pick up|collect|schedule)\b", ql):
        intent = "pickup"
    elif re.search(r"\b(report|overflow|garbage on|dump|hotspot|complaint)\b", ql):
        intent = "report"
    elif re.search(r"\b(simulate|twin|what.?if|scenario)\b", ql):
        intent = "twin"
    elif re.search(r"\b(sell|recycler|marketplace|buyer)\b", ql):
        intent = "market"
    elif re.search(r"\b(streak|goal|nudge|tip|improve)\b", ql):
        intent = "behaviour"
    elif re.search(r"\b(where|how|can i|can this|should i|dispose|recycl|throw|put|bin|what is|what do i do)\b", ql):
        intent = "waste"
    ctx.step("Orchestrator", f"Understand request → intent '{intent}'", lambda: {"intent": intent, "method": "rule-based intent router" + (" (LLM phrasing enabled)" if ctx.run.mode == "llm_assisted" else "")}, actor_type="orchestrator", tool="intent_router")
    ans = ""
    if intent == "wallet":
        b = ctx.step(A_REW, "Read wallet balances from the ledger", lambda: rewards.balances(db, user.id), tool="ledger.balances")
        ans = f"You have {b['spendable']} spendable points ({b['verified']} verified, {b['final']} finalised) and {b['provisional']} provisional points. Level: {b['level']}."
        actions.append({"label": "Open wallet", "to": "/wallet"})
    elif intent == "waste":
        cls = ctx.step(A_SEG, "Classify the described item", lambda: vision.classify(None, q, "", get_cfg(db)), tool="vision_classify (text mode)")
        if cls["needs_clarification"]:
            ans = "I'm not certain what that item is. Add a few words (for example 'pizza box with food residue') or upload a photo in the Waste Doctor. If it might be hazardous, keep it separate and use special-care collection."
        else:
            ans = f"{cls['detected_object']} → {cls['stream']} waste. {cls['disposal']} {cls['handling']}"
            if cls["hazard"]:
                ans += " (Hazardous: I cannot declare this safe — use authorised handling.)"
        actions.append({"label": "Open Waste Doctor", "to": "/doctor"})
    elif intent == "events":
        evl = ctx.step(A_EVT, "List upcoming zero-waste events", lambda: [{"id": e.id, "name": e.name, "date": e.starts_at.isoformat()} for e in db.scalars(select(Event).where(Event.starts_at >= now()).order_by(Event.starts_at).limit(3)).all()], tool="events.list")
        ans = ("Upcoming events: " + "; ".join(f"{e['name']} ({e['date'][:10]})" for e in evl)) if evl else "There are no upcoming events yet."
        actions.append({"label": "Browse events", "to": "/events"})
    elif intent == "pickup":
        ans = "I can help schedule a pickup. Identify your waste first so the right collector and facility are matched, then confirm the slot — pickups are never created without your confirmation."
        actions += [{"label": "Identify waste", "to": "/doctor"}, {"label": "My pickups", "to": "/collection"}]
    elif intent == "report":
        ans = "Report the problem with a photo or voice note and the Citizen Reporting Agent will classify it, check duplicates and route it to the right ward."
        actions.append({"label": "Report garbage", "to": "/hotspots"})
    elif intent == "twin":
        ans = "The Waste Digital Twin lets municipal users compare baseline vs scenario (segregation, vehicles, festivals, downtime). It is a simulation of a pilot zone, not a live city twin."
        actions.append({"label": "Open Digital Twin", "to": "/twin"})
    elif intent == "market":
        ans = "List your material in the Circular Marketplace; the Matching Agent recommends recyclers by material, quantity and distance. A counterparty must approve before a pickup is created."
        actions.append({"label": "Open marketplace", "to": "/marketplace"})
    elif intent == "behaviour":
        prof = ctx.step(A_BEH, "Analyse behaviour profile", lambda: community.behaviour_profile(db, user), tool="behaviour_profile")
        ans = f"Streak: {prof['streak_days']} day(s); segregation score {prof['segregation_score']}. " + (prof["nudges"][0]["body"] if prof["nudges"] else "Keep submitting clean, segregated waste to build your streak.")
        actions.append({"label": "Community & goals", "to": "/community"})
    else:
        ans = "I can identify waste, check your GreenPoints, find events, help you report garbage, explain the marketplace and the digital twin. What would you like to do?"
    from .runtime import llm_text

    final, used = llm_text(f"User question: {q}\nVerified facts to rephrase (do not add facts): {ans}", ans, 200)
    d["answer"], d["actions"], d["intent"], d["llm_phrased"] = final, actions, intent, used
    return d
