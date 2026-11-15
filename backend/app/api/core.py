from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agents.graph import GRAPH_ENGINE
from ..config import DATA_DIR, settings
from ..core.security import current_user, hash_password, make_token, verify_password
from ..database.db import get_db
from ..models.models import Facility, Household, User, Ward, Worker
from ..services import vision
from ..services.common import DATA_CLASS_LABELS, audit
from .util import to_dict

router = APIRouter()


def user_out(db: Session, u: User) -> dict:
    d = to_dict(u, exclude=("password_hash",))
    w = db.get(Ward, u.ward_id) if u.ward_id else None
    d["ward"] = w.name if w else None
    hh = db.scalars(select(Household).where(Household.user_id == u.id)).first()
    d["household_code"] = hh.code if hh else None
    wk = db.scalars(select(Worker).where(Worker.user_id == u.id)).first()
    d["worker_code"] = wk.worker_code if wk else None
    if u.facility_id:
        f = db.get(Facility, u.facility_id)
        d["facility"] = f.name if f else None
    return d


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=160)
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=100)
    role: str = "citizen"
    ward_id: int | None = None


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if body.role not in ("citizen", "organiser", "worker"):
        raise HTTPException(400, "Self-registration is limited to citizen, worker and organiser roles; other roles are provisioned by an administrator.")
    if db.scalars(select(User).where(User.email == body.email.lower())).first():
        raise HTTPException(409, "Email already registered")
    ward = db.get(Ward, body.ward_id) if body.ward_id else db.scalars(select(Ward)).first()
    u = User(email=body.email.lower(), name=body.name, role=body.role, password_hash=hash_password(body.password), ward_id=ward.id if ward else None,
             data_class=settings.record_class, prefs={"notifications": {"enabled": True, "max_per_day": 6}})
    db.add(u)
    db.flush()
    if body.role == "citizen" and ward:
        n = (db.scalar(select(func.count()).select_from(Household)) or 0) + 1
        db.add(Household(user_id=u.id, code=f"VX-HH-{n:04d}", address="(add your address)", ward_id=ward.id, lat=ward.lat, lng=ward.lng, data_class=settings.record_class))
    if body.role == "worker" and ward:
        n = (db.scalar(select(func.count()).select_from(Worker)) or 0) + 1
        db.add(Worker(user_id=u.id, worker_code=f"WRK-{n:03d}", ward_id=ward.id, lat=ward.lat, lng=ward.lng, training=["safe_handling"], data_class=settings.record_class))
    audit(db, u.id, "register", "user", u.id)
    db.commit()
    return {"token": make_token(u), "user": user_out(db, u)}


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalars(select(User).where(User.email == body.email.lower())).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    audit(db, u.id, "login", "user", u.id)
    db.commit()
    return {"token": make_token(u), "user": user_out(db, u)}


@router.get("/auth/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_out(db, user)


class PrefsIn(BaseModel):
    language: str | None = None
    notifications: dict | None = None
    goals: dict | None = None
    ward_id: int | None = None
    name: str | None = None
    privacy: dict | None = None
    community_id: int | None = None


@router.put("/auth/me")
def update_me(body: PrefsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    prefs = dict(user.prefs or {})
    if body.language:
        user.language = body.language if body.language in ("en", "ta", "hi") else "en"
    if body.notifications is not None:
        prefs["notifications"] = {**prefs.get("notifications", {}), **body.notifications}
    if body.goals is not None:
        prefs["goals"] = {**prefs.get("goals", {}), **body.goals}
    if body.privacy is not None:
        prefs["privacy"] = {**prefs.get("privacy", {}), **body.privacy}
    if body.ward_id and db.get(Ward, body.ward_id):
        user.ward_id = body.ward_id
    if body.community_id is not None:
        user.community_id = body.community_id or None
    if body.name:
        user.name = body.name
    user.prefs = prefs
    db.commit()
    return user_out(db, user)


@router.get("/auth/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    if not settings.DEMO_MODE:
        return []
    from ..database.seed import DEMO_PASSWORD

    desc = {"citizen": "Citizen — Waste Doctor, wallet, passport, community", "worker": "Waste worker — pickups, QR confirmation, earnings", "municipal": "Municipal officer — Command Centre, Digital Twin, approvals",
            "facility": "Facility operator — receive & process batches", "recycler": "Recycler / buyer — marketplace demand", "organiser": "Event organiser — zero-waste events"}
    users = db.scalars(select(User).where(User.email.like("%@vyarthx.demo"), ~User.email.like("household%"), ~User.email.like("collector%")).order_by(User.id)).all()
    return [{"email": u.email, "role": u.role, "name": u.name, "password": DEMO_PASSWORD, "description": desc.get(u.role, "")} for u in users]


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    wards = db.scalars(select(Ward).order_by(Ward.name)).all()
    return {"app": settings.APP_NAME, "tagline": settings.TAGLINE, "demo_mode": settings.DEMO_MODE, "pilot": settings.PILOT,
            "wards": [{"id": w.id, "name": w.name, "lat": w.lat, "lng": w.lng, "zone": w.zone} for w in wards],
            "data_classes": DATA_CLASS_LABELS, "record_class": settings.record_class}


@router.get("/health")
def health(db: Session = Depends(get_db)):
    ok = True
    try:
        db.execute(select(1))
    except Exception:
        ok = False
    return {"status": "ok" if ok else "degraded", "app": "VYARTHX", "database": "ok" if ok else "error"}


@router.get("/system/status")
def system_status(db: Session = Depends(get_db)):
    ms = vision.model_status()
    return {"app": "VYARTHX", "demo_mode": settings.DEMO_MODE, "database": settings.DATABASE_URL.split(":")[0], "graph_engine": GRAPH_ENGINE,
            "agent_mode": "llm_assisted (narration & phrasing only)" if settings.llm_enabled else "deterministic local demo mode (no API key)",
            "llm_configured": settings.llm_enabled, "models": ms, "routing": "OR-Tools VRP" + (" + OSRM road distances" if settings.OSRM_URL else " with haversine×1.3 distances"),
            "forecasting": "scikit-learn GradientBoosting trained on SIMULATED ward history", "digital_twin": "Python/numpy simplified pilot-zone simulation",
            "integrations": {"municipal_systems": False, "vehicle_gps": False, "weighing_devices": False, "irctc_or_railways": False, "recycler_confirmation_apis": False,
                             "note": "None of these real-world integrations are connected. Related records are simulated and labelled."}}


@router.get("/system/datasources")
def datasources():
    f = DATA_DIR / "sources" / "registry.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"sources": []}
