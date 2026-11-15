from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.models import CollectionRequest, MarketListing, MarketMatch, User, now
from .common import haversine_km, nearest_ward, rec_class

MATERIALS = ["cardboard", "paper", "pet", "hdpe", "plastic_film", "metal", "glass", "ewaste", "textile", "furniture", "organic", "compost", "tetrapak", "construction", "reusable"]
COMPAT = {
    "cardboard": {"cardboard": 1.0, "paper": 0.5}, "paper": {"paper": 1.0, "cardboard": 0.6}, "pet": {"pet": 1.0, "hdpe": 0.5},
    "hdpe": {"hdpe": 1.0, "pet": 0.5, "plastic_film": 0.3}, "plastic_film": {"plastic_film": 1.0, "hdpe": 0.3}, "metal": {"metal": 1.0},
    "glass": {"glass": 1.0}, "ewaste": {"ewaste": 1.0}, "textile": {"textile": 1.0}, "furniture": {"furniture": 1.0, "reusable": 0.7},
    "organic": {"organic": 1.0}, "compost": {"compost": 1.0}, "tetrapak": {"tetrapak": 1.0, "paper": 0.4}, "construction": {"construction": 1.0},
    "reusable": {"reusable": 1.0, "furniture": 0.7},
}
CONT_F = {"none": 1.0, "possible": 0.8, "detected": 0.5}


def score_pair(sup: MarketListing, dem: MarketListing) -> dict | None:
    compat = COMPAT.get(sup.material_key, {}).get(dem.material_key, 0.0)
    if compat <= 0:
        return None
    d = haversine_km(sup.lat, sup.lng, dem.lat, dem.lng) * 1.3
    if d > 40:
        return None
    q = min(sup.remaining_kg or sup.quantity_kg, dem.remaining_kg or dem.quantity_kg)
    if q <= 0:
        return None
    cover = q / max(dem.remaining_kg or dem.quantity_kg, 1)
    qty_f = 0.5 + 0.5 * min(1.0, cover / 0.5)
    dist_f = math.exp(-d / 15)
    cond_f = CONT_F.get(sup.contamination, 0.8)
    s = compat * qty_f * dist_f * cond_f
    return {"score": round(s, 3), "distance_km": round(d, 1), "qty_kg": round(q, 1),
            "rationale": {"material_compatibility": compat, "quantity_fit": round(qty_f, 2), "distance_factor": round(dist_f, 2),
                          "condition_factor": cond_f, "demand_covered_pct": round(100 * cover, 1),
                          "pickup_window_supply": sup.pickup_window, "price_note": "Indicative price only; negotiate directly. No live market rate is used."}}


def recommend(db: Session, demand_id: int | None = None, supply_id: int | None = None, min_score: float = 0.12) -> list[MarketMatch]:
    dq = select(MarketListing).where(MarketListing.kind == "demand", MarketListing.status == "open")
    if demand_id:
        dq = dq.where(MarketListing.id == demand_id)
    demands = db.scalars(dq).all()
    supplies = db.scalars(select(MarketListing).where(MarketListing.kind == "supply", MarketListing.status == "open")).all()
    if supply_id:
        supplies = [s for s in supplies if s.id == supply_id]
    out: list[MarketMatch] = []
    for dem in demands:
        scored = []
        for sup in supplies:
            if sup.user_id == dem.user_id:
                continue
            sc = score_pair(sup, dem)
            if sc and sc["score"] >= min_score:
                scored.append((sup, sc))
        scored.sort(key=lambda x: -x[1]["score"])
        need = dem.remaining_kg or dem.quantity_kg
        for sup, sc in scored:
            if need <= 0:
                break
            q = min(sc["qty_kg"], need)
            need -= q
            m = db.scalars(select(MarketMatch).where(MarketMatch.supply_id == sup.id, MarketMatch.demand_id == dem.id)).first()
            if m:
                if m.status == "recommended":
                    m.score, m.distance_km, m.qty_kg, m.rationale = sc["score"], sc["distance_km"], q, sc["rationale"]
                    m.updated_at = now()
                out.append(m)
                continue
            m = MarketMatch(supply_id=sup.id, demand_id=dem.id, qty_kg=q, score=sc["score"], distance_km=sc["distance_km"],
                            rationale=sc["rationale"], status="recommended", data_class=rec_class())
            db.add(m)
            db.flush()
            out.append(m)
    return out


def create_pickup_from_match(db: Session, m: MarketMatch) -> CollectionRequest:
    sup = db.get(MarketListing, m.supply_id)
    ward = nearest_ward(db, sup.lat, sup.lng)
    stream = "wet" if sup.material_key in ("organic",) else ("special" if sup.material_key == "ewaste" else "dry")
    c = CollectionRequest(user_id=sup.user_id, ward_id=ward.id if ward else sup.ward_id, kind="marketplace", stream=stream, material_key=sup.material_key,
                          status="requested", priority=2, est_weight_kg=m.qty_kg, lat=sup.lat, lng=sup.lng,
                          notes=f"Marketplace match #{m.id} — pickup for buyer listing #{m.demand_id}", evidence={"match_id": m.id},
                          data_class=rec_class())
    db.add(c)
    db.flush()
    m.collection_id = c.id
    return c


def complete_match(db: Session, m: MarketMatch, qty_kg: float | None = None) -> None:
    sup, dem = db.get(MarketListing, m.supply_id), db.get(MarketListing, m.demand_id)
    q = qty_kg or m.qty_kg
    sup.remaining_kg = max(0.0, (sup.remaining_kg or sup.quantity_kg) - q)
    dem.remaining_kg = max(0.0, (dem.remaining_kg or dem.quantity_kg) - q)
    if sup.remaining_kg <= 0:
        sup.status = "closed"
    if dem.remaining_kg <= 0:
        dem.status = "closed"
    m.status = "completed"
    m.updated_at = now()
