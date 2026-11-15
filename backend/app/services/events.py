from __future__ import annotations

import math

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.models import Event, EventParticipation, EventWaste, Facility, now
from .common import get_cfg, road_km

STREAMS = ["wet", "dry_recyclable", "reject", "special", "reusable"]
RECOVERED_STREAMS = {"wet", "dry_recyclable", "reusable"}


def plan_event(db: Session, ev: Event) -> dict:
    cfg = get_cfg(db)
    kpp = cfg["event_waste_kg_per_person"].get(ev.food, 0.3)
    dur_f = max(0.5, min(3.0, ev.duration_h / 4))
    total = ev.expected_attendance * kpp * dur_f
    split = cfg["event_stream_split"]
    est = {s: round(total * split.get(s, 0), 1) for s in STREAMS}
    per_cp = cfg["event_people_per_collection_point"]
    cps = max(2, math.ceil(ev.expected_attendance / per_cp))
    zones = [("Main entrance / registration", 1), ("Food & beverage area", max(1, math.ceil(cps * (0.5 if ev.food in ("catered", "stalls") else 0.25)))),
             ("Stage / audience area", max(1, math.ceil(cps * 0.25))), ("Exits & parking", 1)]
    volunteers = math.ceil(ev.expected_attendance / cfg["event_people_per_volunteer"] * (1.2 if ev.food in ("catered", "stalls") else 1.0))
    partners = []
    for ftype, why in [("compost", "organic / food waste"), ("recycler", "clean dry recyclables"), ("mrf", "mixed dry sorting"), ("ngo", "reusable items"), ("special_care", "special-care items")]:
        fs = db.scalars(select(Facility).where(Facility.type == ftype, Facility.authorised == True)).all()  # noqa: E712
        if fs:
            f = min(fs, key=lambda x: road_km(ev.lat or x.lat, ev.lng or x.lng, x.lat, x.lng))
            partners.append({"facility_id": f.id, "name": f.name, "type": f.type, "for": why,
                             "distance_km": round(road_km(ev.lat or f.lat, ev.lng or f.lng, f.lat, f.lng), 1), "status": "suggested — not confirmed", "data_class": f.data_class})
    checklist = [
        "Place paired wet / dry-recyclable / reject bins at every collection point with clear pictorial signage",
        f"Brief {volunteers} volunteers on the segregation plan and PPE (gloves, closed footwear)",
        "Agree pickup times with the collection partner before the event; confirm drop-off receipts",
        "Provide a separate special-care container (batteries, sharps) at the registration desk",
        "Set up a reusable cutlery / water refill station to prevent single-use waste",
        "Weigh or estimate each stream after the event and log it in VYARTHX (partner-confirmed weights count as verified)",
    ]
    if ev.food in ("catered", "stalls"):
        checklist.insert(2, "Arrange surplus-food donation and keep food waste free from packaging")
    return {"estimated_total_kg": round(total, 1), "estimated_by_stream_kg": est, "collection_points": cps,
            "placement": [{"zone": z, "points": n} for z, n in zones], "volunteers_required": volunteers,
            "partners": partners, "checklist": checklist,
            "assumptions": {"kg_per_person": kpp, "duration_factor": round(dur_f, 2), "stream_split": split, "people_per_collection_point": per_cp},
            "data_class": "estimate", "note": "Model estimate from configurable assumptions — not measured event data."}


def event_totals(db: Session, ev_id: int) -> dict:
    rows = db.scalars(select(EventWaste).where(EventWaste.event_id == ev_id)).all()
    by = {s: {"reported_kg": 0.0, "verified_kg": 0.0} for s in STREAMS}
    for r in rows:
        d = by.setdefault(r.stream, {"reported_kg": 0.0, "verified_kg": 0.0})
        d["reported_kg"] += r.kg
        if r.verified:
            d["verified_kg"] += r.kg
    total = sum(r.kg for r in rows)
    verified = sum(r.kg for r in rows if r.verified)
    rec = sum(r.kg for r in rows if r.recovered and r.stream in RECOVERED_STREAMS)
    rec_v = sum(r.kg for r in rows if r.recovered and r.verified and r.stream in RECOVERED_STREAMS)
    reject = sum(r.kg for r in rows if r.stream == "reject")
    return {"by_stream": {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in by.items()}, "total_kg": round(total, 1), "verified_kg": round(verified, 1),
            "recovered_kg_reported": round(rec, 1), "recovered_kg_verified": round(rec_v, 1), "reject_kg": round(reject, 1),
            "diversion_reported": round(rec / total, 3) if total else 0, "diversion_verified": round(rec_v / total, 3) if total else 0,
            "segregation_quality": round(1 - reject / total, 3) if total else 0, "entries": len(rows)}


def build_report(db: Session, ev: Event) -> dict:
    t = event_totals(db, ev.id)
    parts = db.execute(select(EventParticipation.role, func.count(), func.coalesce(func.sum(EventParticipation.contribution_inr), 0),
                              func.coalesce(func.sum(EventParticipation.hours), 0)).where(EventParticipation.event_id == ev.id).group_by(EventParticipation.role)).all()
    roles = {r: {"count": c, "contribution_inr": float(i), "hours": float(h)} for r, c, i, h in parts}
    est = (ev.plan or {}).get("estimated_total_kg") or 0
    cert_ok = bool(ev.status == "completed" and t["entries"] >= 3 and est and t["total_kg"] >= 0.5 * est
                   and t["total_kg"] and t["verified_kg"] / t["total_kg"] >= 0.8 and t["diversion_verified"] >= 0.7)
    reasons = []
    if ev.status != "completed":
        reasons.append("Event is not marked completed")
    if t["entries"] < 3:
        reasons.append("Fewer than 3 waste records logged")
    if est and t["total_kg"] < 0.5 * est:
        reasons.append("Logged quantity is under 50% of the planned estimate")
    if t["total_kg"] and t["verified_kg"] / t["total_kg"] < 0.8:
        reasons.append("Less than 80% of logged weight is partner-verified (organiser-reported figures do not count)")
    if t["diversion_verified"] < 0.7:
        reasons.append("Verified diversion from disposal is below 70%")
    return {"totals": t, "participation": roles, "estimated_total_kg": est,
            "attendance": {"expected": ev.expected_attendance, "actual": ev.actual_attendance},
            "certificate_eligible": cert_ok, "certificate_blockers": [] if cert_ok else reasons,
            "generated_at": now().isoformat(), "data_class": ev.data_class}
