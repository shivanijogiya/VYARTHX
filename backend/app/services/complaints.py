from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.models import Complaint, now
from .common import haversine_km
from .imagehash import hamming

CATS = {
    "special_care_unattended": ["syringe", "needle", "battery", "chemical", "medical", "hazard", "biomedical", "paint", "tube light", "sharps"],
    "illegal_dumping": ["dump", "debris", "construction", "rubble", "illegal", "truckload", "dumped"],
    "overflowing_bin": ["overflow", "bin is full", "bin full", "bins full", "spilling", "overflowing"],
    "missed_collection": ["not collected", "missed", "no pickup", "not picked", "didn't come", "did not come", "skipped"],
    "mixed_waste": ["mixed", "unsegregated", "not segregated", "all together"],
    "public_littering": ["litter", "littering", "park", "beach", "footpath", "plastic on road", "street litter"],
    "garbage_accumulation": ["garbage", "pile", "heap", "accumulat", "stink", "smell", "rotting", "rubbish", "trash"],
}


def classify_text(text: str, image_label: str = "") -> dict:
    t = (text + " " + image_label).lower()
    scores = {c: sum(1 for k in kws if k in t) for c, kws in CATS.items()}
    best = max(scores.items(), key=lambda kv: kv[1])
    cat = best[0] if best[1] > 0 else "garbage_accumulation"
    conf = min(0.95, 0.5 + 0.15 * best[1]) if best[1] > 0 else 0.4
    pr = 1 if cat in ("special_care_unattended",) or "sharps" in t or "syringe" in t else 2
    return {"category": cat, "confidence": round(conf, 2), "priority": pr, "matched": best[1],
            "needs_review": conf < 0.55 or cat == "special_care_unattended"}


def find_duplicate(db: Session, lat: float, lng: float, category: str, phash: str = "", exclude_id: int | None = None) -> Complaint | None:
    since = now() - timedelta(days=7)
    q = select(Complaint).where(Complaint.created_at >= since, Complaint.status.notin_(["closed", "merged"]), Complaint.duplicate_of.is_(None))
    for c in db.scalars(q).all():
        if exclude_id and c.id == exclude_id:
            continue
        d_m = haversine_km(lat, lng, c.lat, c.lng) * 1000
        if d_m <= 150 and c.category == category:
            return c
        if phash and c.phash and hamming(phash, c.phash) <= 5 and d_m <= 1000:
            return c
    return None


def hotspot_clusters(db: Session, days: int = 30, min_repeat: int = 3) -> list[dict]:
    since = now() - timedelta(days=days)
    cells: dict[tuple, list[Complaint]] = defaultdict(list)
    for c in db.scalars(select(Complaint).where(Complaint.created_at >= since)).all():
        cells[(round(c.lat / 0.002), round(c.lng / 0.002))].append(c)
    out = []
    for key, cs in cells.items():
        if len(cs) >= min_repeat:
            out.append({"lat": sum(c.lat for c in cs) / len(cs), "lng": sum(c.lng for c in cs) / len(cs), "count": len(cs),
                        "ward_id": cs[0].ward_id, "categories": sorted({c.category for c in cs}),
                        "open": sum(1 for c in cs if c.status not in ("closed", "merged"))})
    return sorted(out, key=lambda x: -x["count"])


def push_history(c: Complaint, status: str, by: str, note: str = "", evidence: str = "") -> None:
    h = list(c.history or [])
    h.append({"status": status, "by": by, "note": note, "evidence": evidence, "at": now().isoformat()})
    c.history = h
    c.status = status
    c.updated_at = now()
