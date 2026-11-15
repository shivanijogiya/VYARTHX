"""Compost-to-Community, Reuse & Upcycling and E-waste helpers."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.models import Facility, ReuseListing
from .common import get_cfg, road_km, upcycle_ideas
from .logistics import rank_facilities

REUSE_CATEGORIES = {
    "furniture": ["chair", "table", "sofa", "bed", "cupboard", "desk", "bench", "shelf", "furniture", "wardrobe"],
    "books": ["book", "novel", "textbook", "notebook", "magazine"],
    "clothes": ["cloth", "shirt", "saree", "jeans", "uniform", "jacket", "shoe"],
    "electronics": ["phone", "laptop", "monitor", "tv", "fan", "mixer", "charger", "computer", "radio", "printer", "appliance"],
    "wooden": ["wood", "plank", "plywood", "pallet", "timber"],
    "containers": ["jar", "bottle", "container", "bucket", "drum", "box", "tin"],
    "construction": ["tile", "brick", "cement", "paint", "pipe", "sand", "construction"],
    "equipment": ["equipment", "machine", "tool", "lab", "sewing", "drill", "cycle", "bicycle"],
}
AFFINITY = {  # reuse category -> receiving facility types
    "furniture": ["ngo", "refurbisher", "school"], "books": ["school", "ngo"], "clothes": ["ngo"], "electronics": ["refurbisher", "school", "ngo"],
    "wooden": ["refurbisher", "ngo"], "containers": ["ngo", "nursery"], "construction": ["ngo", "refurbisher"], "equipment": ["school", "refurbisher", "ngo"],
}
CONDITIONS = {"new": ["new", "unused", "sealed"], "good": ["good", "working", "fine", "like new"], "needs_repair": ["broken", "repair", "damaged", "not working", "faulty"]}


def classify_reuse(title: str, desc: str = "") -> dict:
    t = f"{title} {desc}".lower()
    cat = "household"
    for c, kws in REUSE_CATEGORIES.items():
        if any(k in t for k in kws):
            cat = c
            break
    cond = "good"
    for c, kws in CONDITIONS.items():
        if any(k in t for k in kws):
            cond = c
            break
    return {"category": cat, "condition": cond, "basis": "keyword rules on title/description (no image model for reuse items in this build)"}


def match_recipients(db: Session, listing: ReuseListing) -> list[dict]:
    types = AFFINITY.get(listing.category, ["ngo"])
    out = []
    for f in db.scalars(select(Facility).where(Facility.type.in_(types))).all():
        if not f.authorised:
            continue
        d = road_km(listing.lat or f.lat, listing.lng or f.lng, f.lat, f.lng)
        s = (1.0 - 0.15 * types.index(f.type)) / (1 + d / 10)
        if listing.condition == "needs_repair" and f.type != "refurbisher":
            s *= 0.5
        out.append({"facility_id": f.id, "name": f.name, "type": f.type, "distance_km": round(d, 1), "score": round(s, 3), "status": "suggested — recipient has not confirmed",
                    "data_class": f.data_class})
    return sorted(out, key=lambda x: -x["score"])[:5]


def upcycling(category: str) -> list[str]:
    ideas = upcycle_ideas()
    return ideas.get(category) or ideas.get("household", [])


def compost_estimate(db: Session, households: int, kg_per_hh_day: float, days: int, method: str = "windrow", lat: float | None = None, lng: float | None = None) -> dict:
    cfg = get_cfg(db)
    feed = households * kg_per_hh_day * days
    y = cfg["compost_yield"].get(method, 0.3)
    out = {"inputs": {"households": households, "kg_per_household_day": kg_per_hh_day, "days": days, "method": method},
           "feedstock_kg": round(feed, 1), "formula": f"{households} × {kg_per_hh_day} × {days} = {feed:,.0f} kg",
           "compost_yield_assumption": y, "estimated_compost_kg": round(feed * y, 1),
           "estimated_biogas_m3_if_biomethanation": round(feed / 1000 * cfg["biogas_m3_per_tonne"], 1),
           "label": "ESTIMATE — yield is an adjustable assumption until actual facility records are available.", "yield_note": cfg.get("yield_note", ""),
           "data_class": "estimate"}
    if lat is not None and lng is not None:
        out["facilities"] = rank_facilities(db, ["compost", "biomethanation"], lat, lng, feed / max(days, 1))[:5]
    return out
