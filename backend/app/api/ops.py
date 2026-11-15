from __future__ import annotations

import csv
import io
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agents import workflows  # noqa: F401
from ..agents.runtime import run_workflow
from ..core.security import current_user, require_roles
from ..database.db import get_db
from ..models.models import (Approval, Batch, CollectionRequest, Complaint, Facility, MarketListing, RoutePlan, SimulationRun, User, Vehicle, Ward, Worker, WorkerPayment, now)
from ..services import analytics, complaints as cmp, forecast as fc, logistics as lg, passport as pp
from ..services.common import notify, audit, haversine_km, road_km
from ..simulation import twin
from .citizen import _batch_out, _col_out
from .util import read_image, to_dict

router = APIRouter()


# ================================================================ Workers
def _worker(db: Session, user: User) -> Worker:
    w = db.scalars(select(Worker).where(Worker.user_id == user.id)).first()
    if not w:
        raise HTTPException(403, "No worker profile for this account")
    return w


SAFETY = [
    {"title": "Protect yourself", "body": "Wear gloves and closed footwear. Never push hands into mixed bags — tip them out or use a hook."},
    {"title": "Sharps & medical waste", "body": "Do not pick up syringes, needles or blood-soiled items. Mark the location and escalate through the app."},
    {"title": "Batteries, CFLs & chemicals", "body": "Keep them separate from dry recyclables. Do not crush or open. Only special-care-trained workers collect them."},
    {"title": "Lifting & loads", "body": "Do not exceed your registered carrying capacity. Ask for a second collector for heavy or bulky loads."},
    {"title": "Weighing", "body": "Weigh with a scale if available and write the reading. Never round up — verified weights decide rewards and your fee."},
    {"title": "Emergency", "body": "For injury or exposure, stop work, wash with clean water and seek medical help. This app does not provide medical advice."},
]


@router.get("/workers/me")
def worker_me(user: User = Depends(require_roles("worker")), db: Session = Depends(get_db)):
    w = _worker(db, user)
    ward = db.get(Ward, w.ward_id)
    done = db.scalar(select(func.count()).select_from(CollectionRequest).where(CollectionRequest.worker_id == w.id, CollectionRequest.collected_at.is_not(None))) or 0
    kg = db.scalar(select(func.coalesce(func.sum(CollectionRequest.verified_weight_kg), 0)).where(CollectionRequest.worker_id == w.id)) or 0
    earn = db.scalar(select(func.coalesce(func.sum(WorkerPayment.amount_inr), 0)).where(WorkerPayment.worker_id == w.id)) or 0
    badges = []
    for th, name in [(1, "First verified pickup"), (10, "10 verified pickups"), (25, "25 verified pickups"), (50, "50 verified pickups")]:
        if done >= th:
            badges.append(name)
    if "special_care" in (w.training or []):
        badges.append("Special-care trained")
    return {"id": w.id, "worker_code": w.worker_code, "name": user.name, "ward": ward.name if ward else None, "identity_status": w.identity_status, "onboarding_partner": w.onboarding_partner,
            "languages": w.languages, "training": w.training, "capacity_kg": w.capacity_kg, "available": w.available, "pickups_completed": done, "verified_kg": round(float(kg), 1),
            "earnings_inr": round(float(earn), 2), "badges": badges, "digital_id": {"code": w.worker_code, "qr_payload": f"VYARTHX-WORKER:{w.worker_code}", "note": "Digital work identity. Identity verification is optional and does not gate access."},
            "inclusion_note": "VYARTHX supports assisted onboarding via NGOs/cooperatives. No smartphone is required for a worker ID to be used by a partner on the worker's behalf."}


@router.put("/workers/me/availability")
def worker_availability(available: bool, user: User = Depends(require_roles("worker")), db: Session = Depends(get_db)):
    w = _worker(db, user)
    w.available = available
    db.commit()
    return {"available": w.available}


@router.get("/workers/tasks")
def worker_tasks(user: User = Depends(require_roles("worker")), db: Session = Depends(get_db)):
    w = _worker(db, user)
    mine = db.scalars(select(CollectionRequest).where(CollectionRequest.worker_id == w.id, CollectionRequest.status.in_(["assigned", "accepted"])).order_by(CollectionRequest.scheduled_for)).all()
    trained = "special_care" in (w.training or [])
    open_ = []
    for c in db.scalars(select(CollectionRequest).where(CollectionRequest.worker_id.is_(None), CollectionRequest.status == "requested")).all():
        if c.stream == "special" and not trained:
            continue
        if c.est_weight_kg > w.capacity_kg:
            continue
        d = haversine_km(w.lat, w.lng, c.lat, c.lng)
        if d <= 15:
            open_.append((d, c))
    open_.sort(key=lambda x: x[0])
    return {"assigned": [_col_out(db, c) | {"distance_km": round(haversine_km(w.lat, w.lng, c.lat, c.lng), 1)} for c in mine],
            "nearby": [_col_out(db, c) | {"distance_km": round(d, 1)} for d, c in open_[:10]]}


@router.post("/collections/{cid}/accept")
def accept(cid: int, user: User = Depends(require_roles("worker")), db: Session = Depends(get_db)):
    w = _worker(db, user)
    c = db.get(CollectionRequest, cid)
    if not c or c.status not in ("requested", "assigned"):
        raise HTTPException(409, "Request is not available")
    if c.worker_id and c.worker_id != w.id:
        raise HTTPException(409, "Assigned to another collector")
    if c.stream == "special" and "special_care" not in (w.training or []):
        raise HTTPException(403, "Special-care pickups require special-care training")
    c.worker_id, c.status, c.accepted_at = w.id, "accepted", now()
    notify(db, c.user_id, "Collector on the way", f"Collector {w.worker_code} accepted pickup #{c.id}.", "pickup")
    db.commit()
    return _col_out(db, c)


@router.post("/collections/{cid}/reject")
def reject(cid: int, user: User = Depends(require_roles("worker")), db: Session = Depends(get_db)):
    w = _worker(db, user)
    c = db.get(CollectionRequest, cid)
    if not c or c.worker_id != w.id or c.status not in ("assigned", "accepted"):
        raise HTTPException(409, "Cannot reject this request")
    cands = [x for x in lg.rank_workers(db, c.ward_id, c.lat, c.lng, c.est_weight_kg, c.stream, exclude={w.id})]
    if cands:
        c.worker_id = c.suggested_worker_id = cands[0]["worker_id"]
        c.status = "assigned"
        nw = db.get(Worker, c.worker_id)
        notify(db, nw.user_id, "New pickup request", f"Pickup #{c.id} reassigned to you.", "task")
    else:
        c.worker_id, c.status = None, "requested"
    db.commit()
    return _col_out(db, c)


@router.post("/collections/{cid}/confirm")
async def confirm(cid: int, qr_code: str = Form(""), weight_kg: float = Form(...), weight_source: str = Form("manual_entry"), evidence_note: str = Form(""), photo: UploadFile | None = File(None),
                  user: User = Depends(require_roles("worker")), db: Session = Depends(get_db)):
    c = db.get(CollectionRequest, cid)
    if not c:
        raise HTTPException(404, "Not found")
    photo_ref = ""
    data, fname = await read_image(photo)
    if data:
        from ..agents.specialists import store_evidence

        photo_ref = store_evidence(data, fname)["path"]
    res = run_workflow(db, "collection_confirm", {"collection_id": cid, "qr_code": qr_code, "weight_kg": weight_kg, "weight_source": weight_source, "evidence_note": evidence_note, "photo_ref": photo_ref}, user,
                       title=f"Collector confirms pickup #{cid}")
    st = res["data"] or {}
    return {"run_id": res["run_id"], "run_status": res["status"], "summary": res["summary"], "reason": res["reason"], "verification": st.get("verification"), "reward": st.get("reward"),
            "passport": st.get("passport"), "downstream": st.get("downstream"), "compost": st.get("compost"), "behaviour": st.get("behaviour")}


class DeliverIn(BaseModel):
    facility_id: int


@router.post("/collections/{cid}/deliver")
def deliver(cid: int, body: DeliverIn, user: User = Depends(require_roles("worker")), db: Session = Depends(get_db)):
    w = _worker(db, user)
    c = db.get(CollectionRequest, cid)
    f = db.get(Facility, body.facility_id)
    if not c or c.worker_id != w.id or c.status != "collected" or not c.batch_id:
        raise HTTPException(409, "Only your confirmed pickups can be transferred")
    if not f or not f.authorised:
        raise HTTPException(409, "Facility is not authorised")
    b = db.get(Batch, c.batch_id)
    b.current_facility_id = f.id
    pp.add_event(db, b, "collector", "Handed to facility (in transit)", w.worker_code, "worker", f.name, b.input_kg, "recorded", meta={"facility_id": f.id})
    notify(db, user.id, "Transfer recorded", f"Batch {b.code} marked as heading to {f.name}. The facility must confirm receipt.", "task")
    db.commit()
    return _batch_out(db, b)


@router.get("/workers/earnings")
def earnings(user: User = Depends(require_roles("worker")), db: Session = Depends(get_db)):
    w = _worker(db, user)
    rows = db.scalars(select(WorkerPayment).where(WorkerPayment.worker_id == w.id).order_by(WorkerPayment.id.desc()).limit(80)).all()
    wk = now() - timedelta(days=7)
    return {"total_inr": round(sum(r.amount_inr for r in rows), 2), "last_7d_inr": round(sum(r.amount_inr for r in rows if r.created_at >= wk), 2), "records": [to_dict(r) for r in rows],
            "notice": "Earnings are transparent ledger records created by VYARTHX in demo mode. No real payment is made by this build."}


@router.get("/workers/history")
def history(user: User = Depends(require_roles("worker")), db: Session = Depends(get_db)):
    w = _worker(db, user)
    rows = db.scalars(select(CollectionRequest).where(CollectionRequest.worker_id == w.id, CollectionRequest.collected_at.is_not(None)).order_by(CollectionRequest.collected_at.desc()).limit(60)).all()
    return [_col_out(db, c) for c in rows]


@router.get("/workers/connections")
def connections(user: User = Depends(require_roles("worker")), db: Session = Depends(get_db)):
    w = _worker(db, user)
    out = []
    for l in db.scalars(select(MarketListing).where(MarketListing.kind == "demand", MarketListing.status == "open")).all():
        fac = db.get(Facility, l.facility_id) if l.facility_id else None
        out.append({"listing_id": l.id, "buyer": fac.name if fac else "Buyer", "material": l.material_key, "wanted_kg": l.remaining_kg, "distance_km": round(road_km(w.lat, w.lng, l.lat, l.lng), 1),
                    "price_inr_per_kg": l.price_inr_per_kg, "price_note": "Indicative reference only — updated by listing owner; no live market rate is used.", "data_class": l.data_class})
    return sorted(out, key=lambda x: x["distance_km"])


@router.get("/workers/safety")
def safety(user: User = Depends(require_roles("worker"))):
    return SAFETY


# ================================================================ Facilities
@router.get("/facilities")
def facilities(type: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Facility).order_by(Facility.type, Facility.name)
    if type:
        q = q.where(Facility.type == type)
    out = []
    for f in db.scalars(q).all():
        d = to_dict(f)
        d["utilisation"] = round(f.load_tpd / f.capacity_tpd, 2) if f.capacity_tpd else None
        out.append(d)
    return out


class CapacityIn(BaseModel):
    capacity_tpd: float | None = None
    load_tpd: float | None = None
    downtime: bool | None = None


@router.patch("/facilities/{fid}/capacity")
def capacity(fid: int, body: CapacityIn, user: User = Depends(require_roles("facility", "municipal")), db: Session = Depends(get_db)):
    f = db.get(Facility, fid)
    if not f or (user.role == "facility" and user.facility_id != fid):
        raise HTTPException(404, "Facility not found")
    for k in ("capacity_tpd", "load_tpd", "downtime"):
        v = getattr(body, k)
        if v is not None:
            setattr(f, k, v)
    audit(db, user.id, "facility:capacity", "facility", fid)
    db.commit()
    return to_dict(f)


class FacilityReg(BaseModel):
    name: str
    type: str
    ward_id: int
    capacity_tpd: float = 1.0
    accepts: list[str] = []


@router.post("/facilities/register")
def register_facility(body: FacilityReg, user: User = Depends(require_roles("facility", "recycler")), db: Session = Depends(get_db)):
    w = db.get(Ward, body.ward_id)
    if not w:
        raise HTTPException(400, "Unknown ward")
    f = Facility(name=body.name, type=body.type, ward_id=w.id, lat=w.lat, lng=w.lng, capacity_tpd=body.capacity_tpd, accepts=body.accepts, authorised=False, data_class="simulated",
                 authorisation_note="Pending municipal approval", source_note="Self-registered in VYARTHX; not verified")
    db.add(f)
    db.flush()
    a = Approval(action="facility_authorisation", title=f"Authorise facility: {f.name}", payload={"facility_id": f.id}, required_role="municipal", requested_by=user.id)
    db.add(a)
    db.commit()
    return {"facility": to_dict(f), "approval_id": a.id, "note": "A municipal user must approve before this facility can receive batches. VYARTHX agents never authorise facilities."}


@router.get("/facility/incoming")
def incoming(user: User = Depends(require_roles("facility", "recycler")), db: Session = Depends(get_db)):
    fid = user.facility_id
    f = db.get(Facility, fid) if fid else None
    rows = db.scalars(select(Batch).where(Batch.status.in_(["collected", "at_facility", "processing"])).order_by(Batch.id.desc()).limit(100)).all()
    out = []
    for b in rows:
        if b.status == "collected" and b.current_facility_id not in (None, fid):
            continue
        if f and f.accepts and b.material_key and b.material_key not in f.accepts and "all" not in f.accepts and b.stream != "special":
            if not (b.stream == "wet" and "organic" in f.accepts):
                continue
        out.append(_batch_out(db, b))
    return {"facility": to_dict(f) if f else None, "batches": out}


class ReceiveIn(BaseModel):
    received_kg: float
    note: str = ""


@router.post("/facility/batches/{bid}/receive")
def receive(bid: int, body: ReceiveIn, user: User = Depends(require_roles("facility", "recycler")), db: Session = Depends(get_db)):
    res = run_workflow(db, "facility_receive", {"batch_id": bid, "received_kg": body.received_kg, "note": body.note}, user, title=f"Facility receipt — batch #{bid}")
    return {"run_id": res["run_id"], "run_status": res["status"], "reason": res["reason"], "summary": res["summary"], "receipt": (res["data"] or {}).get("receipt")}


class ProcessIn(BaseModel):
    recovered_kg: float
    rejects_kg: float = 0
    loss_kg: float = 0
    other_kg: float = 0
    residual_kg: float | None = None
    residual_destination: str = ""
    note: str = ""


@router.post("/facility/batches/{bid}/process")
def process(bid: int, body: ProcessIn, user: User = Depends(require_roles("facility", "recycler")), db: Session = Depends(get_db)):
    res = run_workflow(db, "facility_process", {"batch_id": bid, **body.model_dump()}, user, title=f"Facility processing record — batch #{bid}")
    st = res["data"] or {}
    return {"run_id": res["run_id"], "run_status": res["status"], "reason": res["reason"], "summary": res["summary"], "processing": st.get("processing"), "final_reward": st.get("final_reward"), "marketplace": st.get("marketplace")}


# ================================================================ Complaints & hotspots
def _cmp_out(db: Session, c: Complaint, user: User | None = None) -> dict:
    d = to_dict(c)
    w = db.get(Ward, c.ward_id) if c.ward_id else None
    d["ward"] = w.name if w else None
    d["is_repeat_hotspot"] = c.repeat_count >= 3
    return d


@router.post("/complaints")
async def create_complaint(description: str = Form(""), source: str = Form("text"), lat: float = Form(0), lng: float = Form(0), image: UploadFile | None = File(None),
                           user: User = Depends(current_user), db: Session = Depends(get_db)):
    data, fname = await read_image(image)
    if not description.strip() and not data:
        raise HTTPException(400, "Describe the problem or attach a photo")
    if source not in ("text", "image", "voice"):
        source = "text"
    res = run_workflow(db, "complaint_report", {"description": description, "source": "image" if data and source == "text" else source, "lat": lat, "lng": lng, "image_bytes": data, "filename": fname}, user,
                       title="Citizen garbage report")
    st = res["data"] or {}
    c = db.get(Complaint, st.get("complaint_id")) if st.get("complaint_id") else None
    return {"run_id": res["run_id"], "run_status": res["status"], "summary": res["summary"], "complaint": _cmp_out(db, c) if c else None, "municipal": st.get("municipal")}


@router.get("/complaints")
def complaints(status: str | None = None, ward_id: int | None = None, category: str | None = None, mine: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Complaint).order_by(Complaint.id.desc()).limit(300)
    if mine or user.role not in ("municipal",):
        q = q.where(Complaint.user_id == user.id)
    if status:
        q = q.where(Complaint.status == status)
    if ward_id:
        q = q.where(Complaint.ward_id == ward_id)
    if category:
        q = q.where(Complaint.category == category)
    return [_cmp_out(db, c) for c in db.scalars(q).all()]


@router.get("/complaints/{cid}")
def complaint(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Complaint, cid)
    if not c or (user.role != "municipal" and c.user_id != user.id):
        raise HTTPException(404, "Not found")
    return _cmp_out(db, c)


class CmpAction(BaseModel):
    action: str  # assign|start|resolve|close|confirm|reopen
    note: str = ""
    evidence: str = ""
    assignee: str = ""


SERIOUS = ("special_care_unattended", "illegal_dumping")


@router.post("/complaints/{cid}/action")
def complaint_action(cid: int, body: CmpAction, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Complaint, cid)
    if not c:
        raise HTTPException(404, "Not found")
    a = body.action
    if user.role == "municipal":
        if a == "assign":
            cmp.push_history(c, "assigned", user.name, body.note or f"Assigned to {body.assignee or 'ward sanitation team'}")
            c.assigned_to = user.id
        elif a == "start":
            cmp.push_history(c, "in_progress", user.name, body.note or "Work started")
        elif a == "resolve":
            if len(body.note.strip()) < 10 or len(body.evidence.strip()) < 3:
                raise HTTPException(422, "Resolution requires a note (≥10 characters) and an evidence reference. Uploading a photo alone does not resolve a complaint.")
            c.resolution_note, c.resolution_evidence = body.note, body.evidence
            cmp.push_history(c, "resolution_submitted", user.name, body.note, evidence=body.evidence)
            notify(db, c.user_id, "Complaint update", f"Complaint #{c.id}: resolution submitted. Please confirm or reopen.", "info")
        elif a == "close":
            if c.status != "resolution_submitted":
                raise HTTPException(409, "A resolution with evidence must be submitted first")
            if c.category in SERIOUS or c.priority == 1:
                ap = Approval(action="complaint_closure", title=f"Approve closure of serious complaint #{c.id}", payload={"complaint_id": c.id}, required_role="municipal", requested_by=user.id)
                db.add(ap)
                db.commit()
                return {"status": c.status, "approval_id": ap.id, "note": "Serious complaints need approval before closure without citizen confirmation."}
            cmp.push_history(c, "closed", user.name, body.note or "Closed after evidence review")
        else:
            raise HTTPException(400, "Unknown action for officer")
    elif c.user_id == user.id:
        if a == "confirm" and c.status == "resolution_submitted":
            cmp.push_history(c, "closed", user.name, "Citizen confirmed the resolution")
        elif a == "reopen" and c.status in ("resolution_submitted", "closed"):
            cmp.push_history(c, "reopened", user.name, body.note or "Problem persists")
            c.repeat_count += 1
        else:
            raise HTTPException(409, "Action not allowed in this state")
    else:
        raise HTTPException(403, "Not allowed")
    audit(db, user.id, f"complaint:{a}", "complaint", c.id)
    db.commit()
    return _cmp_out(db, c)


@router.get("/hotspots")
def hotspots(ward_id: int | None = None, status: str | None = None, category: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Complaint).order_by(Complaint.id.desc()).limit(500)
    if ward_id:
        q = q.where(Complaint.ward_id == ward_id)
    if status:
        q = q.where(Complaint.status == status)
    if category:
        q = q.where(Complaint.category == category)
    items = []
    for c in db.scalars(q).all():
        if c.status == "merged":
            continue
        cls = "new" if c.status in ("submitted", "ai_classified") else "verified" if c.status in ("verified",) else "pending" if c.status in ("assigned", "in_progress", "reopened", "resolution_submitted") else "resolved"
        w = db.get(Ward, c.ward_id) if c.ward_id else None
        items.append({"id": c.id, "lat": c.lat, "lng": c.lng, "category": c.category, "status": c.status, "map_class": cls, "ward": w.name if w else None, "repeat_count": c.repeat_count, "priority": c.priority,
                      "created_at": c.created_at.isoformat(), "description": c.description[:140], "data_class": c.data_class})
    return {"items": items, "repeat_hotspots": cmp.hotspot_clusters(db), "categories": list(cmp.CATS.keys())}


# ================================================================ Logistics & Command Centre
@router.get("/logistics/demand")
def demand(user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    f = fc.forecast(db, 7)
    rows = []
    for w in db.scalars(select(Ward)).all():
        fs = next((s for s in f.get("series", []) if s["ward_id"] == w.id), None)
        veh = db.scalars(select(Vehicle).where(Vehicle.ward_id == w.id)).all()
        cap = len(veh) * 3.0 * 2.0
        est = fs["mean_t_per_day"] * 0.88 if fs else None
        rows.append({**lg.ward_demand_estimate(db, w, fs["mean_t_per_day"] if fs else None), "vehicles": len(veh), "capacity_t_per_day": cap, "overflow_risk": bool(est and est > 0.95 * cap),
                     "utilisation": round(est / cap, 2) if est and cap else None})
    return {"wards": rows, "forecast": {k: f.get(k) for k in ("model", "holdout_mape", "training_data", "note", "data_class")}}


@router.get("/logistics/alerts")
def alerts(user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    miss = db.scalars(select(CollectionRequest).where(CollectionRequest.status.in_(["requested", "assigned", "accepted"]), CollectionRequest.scheduled_for < now() - timedelta(hours=12))).all()
    over = [r for r in demand(user, db)["wards"] if r["overflow_risk"]]
    return {"missed_pickups": [_col_out(db, c) for c in miss], "overflow_warnings": over,
            "note": "Missed pickups = requests still open 12 h after their scheduled time. Overflow warnings use forecast vs. fleet capacity (simulated fleet)."}


class PlanIn(BaseModel):
    ward_ids: list[int] | None = None
    unavailable_vehicle_ids: list[int] | None = None


@router.post("/logistics/plan")
def plan(body: PlanIn, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    res = run_workflow(db, "route_plan", body.model_dump(), user, title="Dynamic collection plan")
    st = res["data"] or {}
    return {"run_id": res["run_id"], "run_status": res["status"], "summary": res["summary"], "plan": st.get("plan"), "plan_group": st.get("plan_group"), "approval_id": st.get("approval_id"),
            "alternatives": st.get("alternatives"), "demand": st.get("demand")}


@router.get("/logistics/routes")
def routes(status: str | None = None, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    q = select(RoutePlan).order_by(RoutePlan.id.desc()).limit(60)
    if status:
        q = q.where(RoutePlan.status == status)
    out = []
    for r in db.scalars(q).all():
        v = db.get(Vehicle, r.vehicle_id) if r.vehicle_id else None
        out.append(to_dict(r) | {"vehicle": v.code if v else None})
    return out


@router.get("/vehicles")
def vehicles(user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    return [to_dict(v) | {"ward": (db.get(Ward, v.ward_id).name if v.ward_id else None)} for v in db.scalars(select(Vehicle).order_by(Vehicle.id)).all()]


@router.patch("/vehicles/{vid}")
def vehicle_status(vid: int, status: str, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    v = db.get(Vehicle, vid)
    if not v or status not in ("available", "on_route", "maintenance"):
        raise HTTPException(400, "Invalid vehicle or status")
    v.status = status
    audit(db, user.id, "vehicle:status", "vehicle", vid, status=status)
    db.commit()
    return to_dict(v)


@router.get("/municipal/overview")
def overview(ward_id: int | None = None, days: int = 30, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    return analytics.city_overview(db, ward_id, max(1, min(days, 90)))


@router.get("/municipal/wards")
def wards(days: int = 30, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    return analytics.ward_table(db, max(1, min(days, 90)))


@router.get("/municipal/recommendations")
def recs(user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    return analytics.recommendations(db)


@router.get("/municipal/forecast")
def forecast(horizon: int = 14, ward_id: int | None = None, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    return fc.forecast(db, max(1, min(horizon, 30)), ward_id)


@router.get("/municipal/timeseries")
def timeseries(ward_id: int | None = None, days: int = 60, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    from ..models.models import WardDaily

    last = db.scalar(select(func.max(WardDaily.day)))
    q = select(WardDaily.day, func.sum(WardDaily.generated_t), func.sum(WardDaily.collected_t), func.sum(WardDaily.recovered_t), func.sum(WardDaily.residual_t), func.sum(WardDaily.segregated_t)).where(
        WardDaily.day > last - timedelta(days=days)).group_by(WardDaily.day).order_by(WardDaily.day)
    if ward_id:
        q = q.where(WardDaily.ward_id == ward_id)
    return {"data_class": "simulated", "unit": "t/day", "rows": [{"day": d.date().isoformat(), "generated": round(float(g), 2), "collected": round(float(c), 2), "recovered": round(float(r), 2),
                                                                 "residual": round(float(rs), 2), "segregated": round(float(s), 2)} for d, g, c, r, rs, s in db.execute(q).all()]}


@router.get("/landfill")
def landfill(user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    return analytics.landfill_intelligence(db)


@router.get("/reports/municipal")
def report(format: str = "json", days: int = 30, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    ov = analytics.city_overview(db, None, days)
    wt = analytics.ward_table(db, days)
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["VYARTHX municipal report", f"period: last {days} days", "ALL VALUES SIMULATED unless stated"])
        w.writerow(["metric", "value", "unit", "period", "source", "data_class"])
        for m in ov["metrics"]:
            w.writerow([m["label"], m["value"], m["unit"], m["period"], m["source"], m["data_class"]])
        w.writerow([])
        w.writerow(["ward", "generated_t_per_day", "collection_completion_pct", "segregation_pct", "residual_share_pct", "pending_complaints", "repeat_hotspots", "data_class"])
        for r in wt:
            w.writerow([r["ward"], r["generated_t_per_day"], r["collection_completion_pct"], r["segregation_pct"], r["residual_share_pct"], r["pending_complaints"], r["repeat_hotspots"], r["data_class"]])
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=vyarthx_municipal_report.csv"})
    return {"overview": ov, "wards": wt, "recommendations": analytics.recommendations(db), "landfill": analytics.landfill_intelligence(db), "impact": analytics.impact_report(db, None, days), "generated_at": now().isoformat()}


@router.get("/reports/impact")
def impact(days: int = 90, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return analytics.impact_report(db, None if user.role == "municipal" else user.id, days)


# ================================================================ Digital twin
@router.get("/simulation/scenarios")
def scenarios(user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    base = twin.baseline_params(db)
    return {"baseline": base, "controls": [{"key": k, "label": l, "min": lo, "max": hi, "step": st, "unit": u} for k, l, lo, hi, st, u in twin.PARAM_META], "scenarios": twin.predefined(db),
            "assumptions": {k: {"label": v[0], "value": v[1], "basis": v[2]} for k, v in twin.ASSUMPTIONS.items()},
            "label": "SIMULATED pilot-zone model — not a live operational digital twin."}


class SimIn(BaseModel):
    name: str = "Custom scenario"
    params: dict = {}


@router.post("/simulation/run")
def run_sim(body: SimIn, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    res = run_workflow(db, "digital_twin", {"name": body.name, "params": body.params}, user, title=f"Digital Twin: {body.name}")
    sid = (res["data"] or {}).get("simulation", {}).get("simulation_id")
    sr = db.get(SimulationRun, sid) if sid else None
    if not sr:
        raise HTTPException(500, "Simulation failed: " + res.get("reason", ""))
    return {"run_id": res["run_id"], "simulation_id": sr.id, "result": sr.result}


@router.get("/simulation/runs")
def sim_runs(user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name, "created_at": s.created_at.isoformat(), "params": s.params,
             "residual_t": s.result.get("scenario", {}).get("kpis", {}).get("residual_t")} for s in db.scalars(select(SimulationRun).order_by(SimulationRun.id.desc()).limit(30)).all()]


@router.get("/simulation/{sid}")
def sim_get(sid: int, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    s = db.get(SimulationRun, sid)
    if not s:
        raise HTTPException(404, "Not found")
    return {"id": s.id, "name": s.name, "created_at": s.created_at.isoformat(), "result": s.result}
