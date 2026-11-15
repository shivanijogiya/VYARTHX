from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agents import workflows  # noqa: F401
from ..agents.runtime import run_workflow
from ..config import settings
from ..core.security import current_user, require_roles
from ..database.db import get_db
from ..models.models import (Challenge, ChallengeParticipation, Community, Event, EventParticipation, EventWaste, Facility, MarketListing, MarketMatch, ReuseListing, User, Ward, now)
from ..services import circular, community as cm, events as ev_svc, marketplace as mk
from ..services.common import audit, kb_items, notify
from ..services.logistics import rank_facilities
from .util import to_dict

router = APIRouter()


def _ward(db: Session, user: User, ward_id: int | None):
    w = db.get(Ward, ward_id) if ward_id else (db.get(Ward, user.ward_id) if user.ward_id else db.scalars(select(Ward)).first())
    if not w:
        raise HTTPException(400, "Unknown ward")
    return w


# ================================================================ Circular marketplace
class ListingIn(BaseModel):
    kind: str = Field(pattern="^(supply|demand)$")
    material_key: str
    title: str = ""
    quantity_kg: float = Field(gt=0, le=100000)
    condition: str = "clean"
    contamination: str = "none"
    ward_id: int | None = None
    pickup_window: str = ""
    price_inr_per_kg: float | None = None
    seller_type: str = "household"


@router.get("/marketplace/materials")
def materials(user: User = Depends(current_user)):
    return [{"key": k["id"], "name": k["name"]} for k in kb_items() if k.get("stream") in ("dry", "special")]


@router.get("/marketplace/listings")
def listings(kind: str | None = None, material: str | None = None, status: str | None = None, mine: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(MarketListing).order_by(MarketListing.id.desc()).limit(200)
    if kind:
        q = q.where(MarketListing.kind == kind)
    if material:
        q = q.where(MarketListing.material_key == material)
    if status:
        q = q.where(MarketListing.status == status)
    if mine:
        q = q.where(MarketListing.user_id == user.id)
    out = []
    for l in db.scalars(q).all():
        d = to_dict(l)
        w = db.get(Ward, l.ward_id) if l.ward_id else None
        d["ward"] = w.name if w else None
        d["facility"] = db.get(Facility, l.facility_id).name if l.facility_id else None
        out.append(d)
    return out


@router.post("/marketplace/listings")
def create_listing(body: ListingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.kind == "demand" and user.role not in ("recycler", "facility", "municipal"):
        raise HTTPException(403, "Only recyclers/facilities can post demand")
    w = _ward(db, user, body.ward_id)
    fac = db.get(Facility, user.facility_id) if user.facility_id else None
    l = MarketListing(user_id=user.id, facility_id=fac.id if fac else None, kind=body.kind, material_key=body.material_key, title=body.title or body.material_key, quantity_kg=body.quantity_kg,
                      remaining_kg=body.quantity_kg, condition=body.condition, contamination=body.contamination, lat=fac.lat if fac else w.lat, lng=fac.lng if fac else w.lng, ward_id=w.id,
                      pickup_window=body.pickup_window, price_inr_per_kg=body.price_inr_per_kg, seller_type=body.seller_type if user.role != "recycler" else "recycler",
                      data_class=settings.record_class, verification="verified_facility" if fac else "unverified")
    db.add(l)
    audit(db, user.id, "marketplace:list", "listing", None, kind=body.kind)
    db.commit()
    res = run_workflow(db, "marketplace_match", {"supply_id": l.id} if l.kind == "supply" else {"demand_id": l.id}, user, title=f"Match new {l.kind} listing #{l.id}")
    return {"listing": to_dict(l), "run_id": res["run_id"], "matches": (res["data"] or {}).get("matches", {})}


def _match_out(db: Session, m: MarketMatch) -> dict:
    s, d = db.get(MarketListing, m.supply_id), db.get(MarketListing, m.demand_id)
    out = to_dict(m)
    out["supply"] = {"id": s.id, "title": s.title, "material": s.material_key, "kg": s.remaining_kg, "condition": s.condition, "contamination": s.contamination, "seller_type": s.seller_type}
    out["demand"] = {"id": d.id, "title": d.title, "material": d.material_key, "kg": d.remaining_kg, "buyer": db.get(Facility, d.facility_id).name if d.facility_id else "Buyer", "price_inr_per_kg": d.price_inr_per_kg}
    return out


@router.get("/marketplace/matches")
def matches(status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(MarketMatch).order_by(MarketMatch.score.desc()).limit(120)
    if status:
        q = q.where(MarketMatch.status == status)
    rows = db.scalars(q).all()
    if user.role in ("citizen", "organiser", "worker"):
        rows = [m for m in rows if db.get(MarketListing, m.supply_id).user_id == user.id]
    elif user.role in ("recycler", "facility"):
        rows = [m for m in rows if db.get(MarketListing, m.demand_id).user_id == user.id or (user.facility_id and db.get(MarketListing, m.demand_id).facility_id == user.facility_id)]
    return [_match_out(db, m) for m in rows]


@router.post("/marketplace/recommend")
def recommend(user: User = Depends(require_roles("municipal", "recycler", "facility")), db: Session = Depends(get_db)):
    res = run_workflow(db, "marketplace_match", {}, user, title="Marketplace matching sweep")
    return {"run_id": res["run_id"], "summary": res["summary"], "matches": (res["data"] or {}).get("matches")}


@router.post("/marketplace/matches/{mid}/request")
def request_match(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(MarketMatch, mid)
    if not m or m.status != "recommended":
        raise HTTPException(409, "Match is not available for request")
    res = run_workflow(db, "marketplace_request", {"match_id": mid}, user, title=f"Marketplace transfer request #{mid}")
    return {"run_id": res["run_id"], "run_status": res["status"], "summary": res["summary"], "approval_id": (res["data"] or {}).get("approval_id"),
            "note": "A municipal approver must authorise the transfer. VYARTHX agents do not move material or money."}


# ================================================================ Reuse & upcycling exchange
class ReuseIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = ""
    category: str | None = None
    mode: str = Field(default="giveaway", pattern="^(sell|donate|exchange|giveaway|repair)$")
    condition: str | None = None
    quantity: int = Field(default=1, ge=1, le=1000)
    price_inr: float | None = None
    ward_id: int | None = None


@router.get("/reuse/listings")
def reuse_list(category: str | None = None, mode: str | None = None, mine: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(ReuseListing).order_by(ReuseListing.id.desc()).limit(150)
    if category:
        q = q.where(ReuseListing.category == category)
    if mode:
        q = q.where(ReuseListing.mode == mode)
    if mine:
        q = q.where(ReuseListing.user_id == user.id)
    out = []
    for r in db.scalars(q).all():
        d = to_dict(r)
        w = db.get(Ward, r.ward_id) if r.ward_id else None
        d["ward"] = w.name if w else None
        d["owner"] = db.get(User, r.user_id).name
        out.append(d)
    return out


@router.post("/reuse/listings")
def reuse_create(body: ReuseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = _ward(db, user, body.ward_id)
    guess = circular.classify_reuse(body.title, body.description)
    l = ReuseListing(user_id=user.id, title=body.title, category=body.category or guess["category"], mode=body.mode, condition=body.condition or guess.get("condition", "good"), quantity=body.quantity,
                     ward_id=w.id, lat=w.lat, lng=w.lng, description=body.description, price_inr=body.price_inr if body.mode == "sell" else None, data_class=settings.record_class)
    db.add(l)
    db.commit()
    res = run_workflow(db, "reuse_listing", {"listing_id": l.id}, user, title=f"Reuse listing match: {l.title}")
    db.refresh(l)
    return {"listing": to_dict(l), "run_id": res["run_id"], "ai": l.ai}


class TransferIn(BaseModel):
    recipient: str
    quantity: int = 1


@router.post("/reuse/listings/{lid}/transfer")
def reuse_transfer(lid: int, body: TransferIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    l = db.get(ReuseListing, lid)
    if not l or l.user_id != user.id:
        raise HTTPException(404, "Listing not found")
    if l.status == "transferred":
        raise HTTPException(409, "Already transferred")
    l.recipient, l.transferred_qty, l.status = body.recipient[:160], min(body.quantity, l.quantity), "transferred"
    audit(db, user.id, "reuse:transfer", "reuse", l.id)
    db.commit()
    return to_dict(l)


@router.get("/reuse/upcycling")
def upcycling(category: str = "other", user: User = Depends(current_user)):
    return {"category": category, "ideas": circular.upcycling(category), "label": "Curated starter ideas (not user-verified). Safety: never reuse hazardous containers for food."}


# ================================================================ Compost-to-community
class CompostIn(BaseModel):
    households: int = Field(default=50, ge=1, le=100000)
    kg_per_household_day: float = Field(default=0.5, gt=0, le=10)
    days: int = Field(default=30, ge=1, le=365)
    method: str = "windrow"
    ward_id: int | None = None


@router.post("/compost/plan")
def compost_plan(body: CompostIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = _ward(db, user, body.ward_id)
    res = run_workflow(db, "compost_plan", {**body.model_dump(), "lat": w.lat, "lng": w.lng}, user, title="Compost-to-Community plan")
    return {"run_id": res["run_id"], "estimate": (res["data"] or {}).get("estimate"), "reason": res["reason"]}


@router.get("/compost/facilities")
def compost_facilities(ward_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = _ward(db, user, ward_id)
    return rank_facilities(db, ["compost", "biomethanation"], w.lat, w.lng, 1.0)[:8]


# ================================================================ E-waste & special-care
@router.get("/special/guide")
def special_guide(user: User = Depends(current_user)):
    return {"items": [k for k in kb_items() if k.get("stream") == "special"],
            "rules": ["Never put batteries, CFLs, e-waste, sanitary or biomedical items into dry or wet bins.",
                      "VYARTHX does not declare any hazardous item safe. When unsure, use authorised channels only.",
                      "Special-care handovers need a trained collector and an authorised facility. No standard points are paid for hazardous items — only a flat handover credit after verification."]}


@router.get("/special/facilities")
def special_facilities(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Facility).where(Facility.type.in_(["ewaste", "hazardous", "biomedical"]))
    return [to_dict(f) for f in db.scalars(q).all()]


# ================================================================ Events
class EventIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    venue: str = ""
    category: str = "college"
    starts_at: datetime
    duration_h: float = Field(default=4, gt=0, le=240)
    expected_attendance: int = Field(default=100, ge=1, le=500000)
    food: str = Field(default="none", pattern="^(none|packaged|catered|stalls)$")
    volunteers_available: int = Field(default=0, ge=0)
    sponsor_requirements: str = ""
    ward_id: int | None = None


def _event_out(db: Session, e: Event, user: User | None = None) -> dict:
    d = to_dict(e)
    d["organiser"] = db.get(User, e.organiser_id).name
    w = db.get(Ward, e.ward_id) if e.ward_id else None
    d["ward"] = w.name if w else None
    d["participants"] = db.scalar(select(func.count()).select_from(EventParticipation).where(EventParticipation.event_id == e.id)) or 0
    d["totals"] = ev_svc.event_totals(db, e.id)
    d["mine"] = bool(user and e.organiser_id == user.id)
    return d


@router.get("/events")
def events(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [_event_out(db, e, user) for e in db.scalars(select(Event).order_by(Event.starts_at.desc()).limit(80)).all()]


@router.get("/events/{eid}")
def event_get(eid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(Event, eid)
    if not e:
        raise HTTPException(404, "Event not found")
    out = _event_out(db, e, user)
    parts = db.scalars(select(EventParticipation).where(EventParticipation.event_id == eid)).all()
    out["participation"] = [to_dict(p) | {"name": db.get(User, p.user_id).name} for p in parts]
    out["waste_log"] = [to_dict(w) for w in db.scalars(select(EventWaste).where(EventWaste.event_id == eid).order_by(EventWaste.id)).all()]
    return out


@router.post("/events")
def event_create(body: EventIn, user: User = Depends(require_roles("organiser", "municipal", "citizen")), db: Session = Depends(get_db)):
    w = _ward(db, user, body.ward_id)
    e = Event(organiser_id=user.id, name=body.name, venue=body.venue, lat=w.lat, lng=w.lng, ward_id=w.id, category=body.category, starts_at=body.starts_at, duration_h=body.duration_h,
              expected_attendance=body.expected_attendance, food=body.food, volunteers_available=body.volunteers_available, sponsor_requirements=body.sponsor_requirements, data_class=settings.record_class)
    db.add(e)
    db.commit()
    res = run_workflow(db, "event_plan", {"event_id": e.id}, user, title=f"Event plan: {e.name}")
    db.refresh(e)
    return {"event": _event_out(db, e, user), "run_id": res["run_id"], "plan": e.plan}


class JoinIn(BaseModel):
    role: str = Field(pattern="^(volunteer|sponsor|collection_partner|recycler|attendee|audience)$")
    org_name: str = ""
    contribution_inr: float = Field(default=0, ge=0)


@router.post("/events/{eid}/join")
def event_join(eid: int, body: JoinIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(Event, eid)
    if not e:
        raise HTTPException(404, "Event not found")
    if db.scalars(select(EventParticipation).where(EventParticipation.event_id == eid, EventParticipation.user_id == user.id, EventParticipation.role == body.role)).first():
        raise HTTPException(409, "You have already joined in this role")
    p = EventParticipation(event_id=eid, user_id=user.id, role=body.role, org_name=body.org_name, contribution_inr=body.contribution_inr if body.role == "sponsor" else 0,
                           status="pending" if body.role in ("sponsor", "collection_partner", "recycler") else "registered")
    db.add(p)
    notify(db, e.organiser_id, "New event participant", f"{user.name} joined '{e.name}' as {body.role}.", "event")
    db.commit()
    return to_dict(p)


class WasteIn(BaseModel):
    stream: str = Field(pattern="^(wet|dry_recyclable|reject|special|reusable)$")
    kg: float = Field(gt=0, le=100000)
    destination: str = ""
    recovered: bool = False


@router.post("/events/{eid}/waste")
def event_waste(eid: int, body: WasteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(Event, eid)
    if not e:
        raise HTTPException(404, "Event not found")
    partner = db.scalars(select(EventParticipation).where(EventParticipation.event_id == eid, EventParticipation.user_id == user.id, EventParticipation.role.in_(["collection_partner", "recycler"]))).first()
    if e.organiser_id != user.id and not partner and user.role not in ("municipal", "facility"):
        raise HTTPException(403, "Only the organiser or a partner can log waste")
    w = EventWaste(event_id=eid, stream=body.stream, kg=body.kg, destination=body.destination, recovered=body.recovered, logged_by=user.id, verified=bool(partner or user.role in ("municipal", "facility")))
    db.add(w)
    if e.status == "planned":
        e.status = "live"
    db.commit()
    return to_dict(w) | {"note": "Organiser-logged entries stay unverified until a partner or facility logs/confirms them."}


@router.post("/events/{eid}/complete")
def event_complete(eid: int, actual_attendance: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(Event, eid)
    if not e or (e.organiser_id != user.id and user.role != "municipal"):
        raise HTTPException(404, "Event not found")
    if actual_attendance:
        e.actual_attendance = actual_attendance
    e.status = "completed"
    db.commit()
    res = run_workflow(db, "event_report", {"event_id": eid}, user, title=f"Event report: {e.name}")
    db.refresh(e)
    return {"run_id": res["run_id"], "report": e.report, "certificate": e.certificate, "run_status": res["status"]}


# ================================================================ Community / league / behaviour
@router.get("/league")
def league(ctype: str | None = None, days: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"rows": cm.leaderboard(db, ctype, days),
            "ranking_rule": "Ranked by a quality score: segregation accuracy, participation, low contamination and verified handover — NOT by total kg. Larger communities get no volume advantage.",
            "data_class": "simulated" if settings.DEMO_MODE else "pilot"}


@router.get("/communities")
def communities(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [to_dict(c) for c in db.scalars(select(Community).order_by(Community.name)).all()]


@router.get("/challenges")
def challenges(user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for ch in db.scalars(select(Challenge).order_by(Challenge.ends_at.desc()).limit(40)).all():
        p = db.scalars(select(ChallengeParticipation).where(ChallengeParticipation.challenge_id == ch.id, ChallengeParticipation.user_id == user.id)).first()
        n = db.scalar(select(func.count()).select_from(ChallengeParticipation).where(ChallengeParticipation.challenge_id == ch.id)) or 0
        out.append(to_dict(ch) | {"joined": bool(p), "progress": p.progress if p else 0, "completed": p.completed if p else False, "participants": n})
    return out


@router.post("/challenges/{cid}/join")
def join_challenge(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ch = db.get(Challenge, cid)
    if not ch or ch.status != "active":
        raise HTTPException(404, "Challenge not available")
    if db.scalars(select(ChallengeParticipation).where(ChallengeParticipation.challenge_id == cid, ChallengeParticipation.user_id == user.id)).first():
        raise HTTPException(409, "Already joined")
    db.add(ChallengeParticipation(challenge_id=cid, user_id=user.id))
    db.commit()
    return {"joined": True}


class ChallengeIn(BaseModel):
    title: str
    description: str = ""
    rule: str = "verified_submissions"
    target: int = Field(default=5, ge=1, le=100)
    points_reward: int = Field(default=25, ge=0, le=100)
    days: int = Field(default=7, ge=1, le=60)
    community_id: int | None = None


@router.post("/challenges")
def create_challenge(body: ChallengeIn, user: User = Depends(require_roles("municipal", "organiser")), db: Session = Depends(get_db)):
    ch = Challenge(title=body.title, description=body.description, rule=body.rule, target=body.target, points_reward=body.points_reward, created_by=user.id, community_id=body.community_id,
                   starts_at=now(), ends_at=now() + timedelta(days=body.days), cadence="weekly" if body.days <= 7 else "monthly", data_class=settings.record_class)
    db.add(ch)
    db.commit()
    return to_dict(ch)
