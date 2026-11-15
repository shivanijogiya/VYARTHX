from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import workflows  # noqa: F401
from ..agents.runtime import run_workflow
from ..config import settings
from ..core.security import current_user, require_roles
from ..database.db import get_db
from ..models.models import (Batch, CollectionRequest, Facility, Notification, PassportEvent, Redemption, RewardCatalog, RewardTransaction, Submission, User, Ward, Worker, now)
from ..services import analytics, community, passport as pp, rewards
from ..services.common import get_cfg, kb_items, set_cfg
from .util import read_image, to_dict

router = APIRouter()


# ---------------------------------------------------------------- Waste Doctor
@router.post("/waste/classify")
async def classify(image: UploadFile | None = File(None), text: str = Form(""), user: User = Depends(current_user), db: Session = Depends(get_db)):
    data, fname = await read_image(image)
    if not data and not text.strip():
        raise HTTPException(400, "Provide a photo or a description")
    res = run_workflow(db, "identify", {"image_bytes": data, "filename": fname, "text": text}, user, title="AI Waste Doctor: identify item")
    st = res["data"] or {}
    cls = st.get("classification", {})
    return {"run_id": res["run_id"], "run_status": res["status"], "classification": cls, "guidance": st.get("guidance", []), "destinations": st.get("destinations", []),
            "needs_clarification": bool(cls.get("needs_clarification")), "summary": res["summary"]}


@router.get("/waste/examples")
def examples():
    return [{"id": k["id"], "name": k["name"], "sample_text": k["keywords"][0]} for k in kb_items()]


@router.post("/submissions")
async def create_submission(image: UploadFile | None = File(None), text: str = Form(""), est_weight_kg: float = Form(0.5), client_ts: str = Form(""),
                            user: User = Depends(require_roles("citizen", "organiser")), db: Session = Depends(get_db)):
    data, fname = await read_image(image)
    if not data and not text.strip():
        raise HTTPException(400, "Provide a photo or a description")
    if not (0 < est_weight_kg <= 100):
        raise HTTPException(400, "Estimated weight must be between 0 and 100 kg")
    res = run_workflow(db, "waste_submission", {"image_bytes": data, "filename": fname, "text": text, "est_weight_kg": est_weight_kg, "client_ts": client_ts}, user, title="Citizen waste submission")
    st = res["data"] or {}
    return {"run_id": res["run_id"], "run_status": res["status"], "summary": res["summary"], "submission_id": st.get("submission_id"), "classification": st.get("classification"),
            "verification": st.get("verification"), "reward": st.get("reward"), "collection_options": st.get("collection_options"), "reason": res["reason"]}


@router.get("/submissions")
def my_submissions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Submission).order_by(Submission.id.desc()).limit(100)
    if user.role not in ("municipal",):
        q = q.where(Submission.user_id == user.id)
    out = []
    for s in db.scalars(q).all():
        d = to_dict(s, exclude=("sha256", "phash", "classification", "verification"))
        d["flags"] = (s.verification or {}).get("flags", [])
        d["reward_eligible"] = (s.classification or {}).get("reward_eligible")
        col = db.scalars(select(CollectionRequest).where(CollectionRequest.submission_id == s.id).order_by(CollectionRequest.id.desc())).first()
        d["collection_id"] = col.id if col else None
        d["collection_status"] = col.status if col else None
        d["batch_id"] = col.batch_id if col else None
        out.append(d)
    return out


class ScheduleIn(BaseModel):
    slot: str | None = None
    notes: str = ""


@router.post("/submissions/{sid}/schedule")
def schedule(sid: int, body: ScheduleIn, user: User = Depends(require_roles("citizen", "organiser")), db: Session = Depends(get_db)):
    s = db.get(Submission, sid)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Submission not found")
    res = run_workflow(db, "schedule_pickup", {"submission_id": sid, "slot": body.slot, "notes": body.notes}, user, title=f"Schedule pickup for submission #{sid}")
    return {"run_id": res["run_id"], "run_status": res["status"], "summary": res["summary"], "schedule": (res["data"] or {}).get("schedule"), "collection_id": (res["data"] or {}).get("collection_id"), "reason": res["reason"]}


# ---------------------------------------------------------------- Collections
def _col_out(db: Session, c: CollectionRequest) -> dict:
    d = to_dict(c)
    ward = db.get(Ward, c.ward_id) if c.ward_id else None
    d["ward"] = ward.name if ward else None
    if c.worker_id:
        w = db.get(Worker, c.worker_id)
        d["worker_code"] = w.worker_code if w else None
    if c.facility_id:
        f = db.get(Facility, c.facility_id)
        d["facility"] = f.name if f else None
    if c.batch_id:
        b = db.get(Batch, c.batch_id)
        d["passport"] = b.code if b else None
    if c.submission_id:
        s = db.get(Submission, c.submission_id)
        if s:
            d["detected_object"], d["contamination"], d["material"] = s.detected_object, s.contamination, s.material
    return d


@router.get("/collections")
def list_collections(status: str | None = None, ward_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(CollectionRequest).order_by(CollectionRequest.id.desc()).limit(200)
    if user.role in ("citizen", "organiser"):
        q = q.where(CollectionRequest.user_id == user.id)
    elif user.role == "worker":
        wk = db.scalars(select(Worker).where(Worker.user_id == user.id)).first()
        q = q.where((CollectionRequest.worker_id == (wk.id if wk else -1)))
    if status:
        q = q.where(CollectionRequest.status == status)
    if ward_id:
        q = q.where(CollectionRequest.ward_id == ward_id)
    return [_col_out(db, c) for c in db.scalars(q).all()]


@router.post("/collections/{cid}/cancel")
def cancel(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(CollectionRequest, cid)
    if not c or (c.user_id != user.id and user.role != "municipal"):
        raise HTTPException(404, "Not found")
    if c.status not in ("requested", "assigned", "accepted"):
        raise HTTPException(409, f"Cannot cancel a {c.status} pickup")
    c.status = "cancelled"
    if c.submission_id:
        s = db.get(Submission, c.submission_id)
        if s:
            s.status = "verified"
    db.commit()
    return _col_out(db, c)


# ---------------------------------------------------------------- Waste Passport
def _batch_out(db: Session, b: Batch) -> dict:
    d = to_dict(b)
    d["status_text"] = pp.STATUS_TEXT.get(b.status, b.status)
    d["mass_balance"] = pp.mass_balance(b)
    if b.current_facility_id:
        f = db.get(Facility, b.current_facility_id)
        d["facility"] = f.name if f else None
    w = db.get(Ward, b.ward_id) if b.ward_id else None
    d["ward"] = w.name if w else None
    return d


@router.get("/passports")
def list_passports(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Batch).order_by(Batch.id.desc()).limit(150)
    if user.role in ("citizen", "organiser"):
        q = q.where(Batch.owner_user_id == user.id)
    elif user.role == "facility" and user.facility_id:
        q = q.where((Batch.current_facility_id == user.facility_id) | (Batch.status == "collected"))
    return [_batch_out(db, b) for b in db.scalars(q).all()]


@router.get("/passports/{ref}")
def get_passport(ref: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    b = db.scalars(select(Batch).where(Batch.code == ref)).first() or (db.get(Batch, int(ref)) if ref.isdigit() else None)
    if not b:
        raise HTTPException(404, "Passport not found")
    if user.role in ("citizen", "organiser") and b.owner_user_id != user.id:
        raise HTTPException(403, "This passport belongs to another household")
    evs = db.scalars(select(PassportEvent).where(PassportEvent.batch_id == b.id).order_by(PassportEvent.seq)).all()
    owner = db.get(User, b.owner_user_id) if b.owner_user_id else None
    out = _batch_out(db, b)
    out["owner"] = owner.name if (owner and (user.role in ("municipal", "facility") or owner.id == user.id)) else None
    out["events"] = [to_dict(e, exclude=("prev_hash",)) | {"hash": e.hash[:12]} for e in evs]
    out["chain"] = pp.verify_chain(db, b)
    out["stages"] = pp.STAGES
    out["claim_rule"] = "Only quantities recorded by the receiving facility count as recovered. The recovered share is never assumed to equal the input."
    return out


# ---------------------------------------------------------------- Wallet
@router.get("/wallet")
def wallet(user: User = Depends(current_user), db: Session = Depends(get_db)):
    b = rewards.balances(db, user.id)
    tx = db.scalars(select(RewardTransaction).where(RewardTransaction.user_id == user.id).order_by(RewardTransaction.id.desc()).limit(60)).all()
    since7, since30 = now() - timedelta(days=7), now() - timedelta(days=30)

    def earned(since):
        return sum(t.amount for t in tx if t.amount > 0 and t.created_at >= since and t.kind in ("provisional_credit", "verified_credit", "final_credit", "bonus"))

    cfg = get_cfg(db)
    reds = db.scalars(select(Redemption).where(Redemption.user_id == user.id).order_by(Redemption.id.desc()).limit(30)).all()
    impact = analytics.impact_report(db, user.id)
    return {"balances": b, "earned_7d": earned(since7), "earned_30d": earned(since30), "streak_days": rewards.streak_days(db, user.id), "transactions": [to_dict(t) for t in tx],
            "redemptions": [to_dict(r) | {"title": r.catalog.title if r.catalog else ""} for r in reds], "impact": impact,
            "rules": {"provisional": "Small reward for an eligible, verified submission.", "verified": "Credited after collector confirmation and weight verification.", "final": "Recovery bonus only after the receiving facility confirms recovered quantity.",
                      "spendable": "Verified + final points. Provisional points cannot be redeemed."}, "rates_per_kg": cfg["rates_per_kg"]}


@router.get("/rewards/catalog")
def catalog(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [to_dict(c) for c in db.scalars(select(RewardCatalog).where(RewardCatalog.active == True)).all()]  # noqa: E712


class RedeemIn(BaseModel):
    catalog_id: int


@router.post("/rewards/redeem")
def redeem(body: RedeemIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(RewardCatalog, body.catalog_id)
    if not item:
        raise HTTPException(404, "Reward not found")
    try:
        r = rewards.redeem(db, user, item)
    except ValueError as e:
        raise HTTPException(409, str(e))
    db.commit()
    return {"redemption": to_dict(r), "title": item.title, "partner": item.partner, "simulation_only": item.simulation_only,
            "notice": "DEMO VOUCHER — simulation only. No real-world benefit, discount or travel concession has been issued." if item.simulation_only else "",
            "balances": rewards.balances(db, user.id)}


@router.get("/rewards/config")
def get_rewards_config(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return get_cfg(db)


@router.put("/rewards/config")
def put_rewards_config(patch: dict, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    allowed = {"rates_per_kg", "flat_special_handover", "quality_factor", "provisional_flat", "provisional_min_confidence", "behaviour_bonus_per_streak_day", "behaviour_bonus_cap", "recovery_bonus_factor",
               "max_verified_kg_per_household_day", "max_points_per_user_day", "worker_fee_inr_per_kg", "compost_yield"}
    clean = {k: v for k, v in patch.items() if k in allowed}
    if not clean:
        raise HTTPException(400, "No editable keys supplied")
    cfg = set_cfg(db, clean)
    from ..services.common import audit

    audit(db, user.id, "config:update", "rewards", None, keys=list(clean))
    db.commit()
    return cfg


# ---------------------------------------------------------------- Notifications & behaviour
@router.get("/notifications")
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(40)).all()
    return [to_dict(n) for n in rows]


@router.post("/notifications/read")
def mark_read(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read == False)).all():  # noqa: E712
        n.read = True
    db.commit()
    return {"ok": True}


@router.get("/behaviour")
def behaviour(user: User = Depends(current_user), db: Session = Depends(get_db)):
    res = run_workflow(db, "behaviour_review", {}, user, title="Behavioural review")
    return (res["data"] or {}).get("profile", {})


@router.get("/home")
def home(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Citizen dashboard payload."""
    b = rewards.balances(db, user.id)
    subs = db.scalars(select(Submission).where(Submission.user_id == user.id).order_by(Submission.id.desc()).limit(8)).all()
    cols = db.scalars(select(CollectionRequest).where(CollectionRequest.user_id == user.id).order_by(CollectionRequest.id.desc()).limit(200)).all()
    upcoming = next((c for c in sorted([c for c in cols if c.status in ("requested", "assigned", "accepted")], key=lambda c: c.scheduled_for or now())), None)
    collected = [c for c in cols if c.verified_weight_kg]
    verified_kg = round(sum(c.verified_weight_kg for c in collected), 1)
    prof = community.behaviour_profile(db, user)
    batches = db.scalars(select(Batch).where(Batch.owner_user_id == user.id).order_by(Batch.id.desc()).limit(5)).all()
    comm_rows = community.leaderboard(db, None)
    mine = next((r for r in comm_rows if user.community_id == r["id"]), None)
    from ..models.models import Challenge, ChallengeParticipation, Event

    chal = []
    for ch in db.scalars(select(Challenge).where(Challenge.status == "active", Challenge.ends_at >= now())).all():
        if ch.community_id and ch.community_id != user.community_id:
            continue
        p = db.scalars(select(ChallengeParticipation).where(ChallengeParticipation.challenge_id == ch.id, ChallengeParticipation.user_id == user.id)).first()
        chal.append({**to_dict(ch), "joined": bool(p), "progress": p.progress if p else 0, "completed": p.completed if p else False})
    evs = db.scalars(select(Event).where(Event.starts_at >= now()).order_by(Event.starts_at).limit(3)).all()
    return {"balances": b, "streak_days": prof["streak_days"], "segregation_score": prof["segregation_score"], "verified_kg": verified_kg, "collections": len(collected),
            "upcoming_pickup": _col_out(db, upcoming) if upcoming else None, "recent": [{"id": s.id, "object": s.detected_object, "stream": s.stream, "status": s.status, "at": s.created_at.isoformat(), "contamination": s.contamination} for s in subs],
            "passports": [_batch_out(db, x) for x in batches], "my_community": mine, "leaderboard": comm_rows[:5], "challenges": chal[:4],
            "events": [{"id": e.id, "name": e.name, "starts_at": e.starts_at.isoformat(), "venue": e.venue} for e in evs], "nudges": prof["nudges"], "impact": analytics.impact_report(db, user.id)}
