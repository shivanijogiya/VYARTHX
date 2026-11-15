"""Waste Passport: append-only, hash-chained batch traceability with mass-balance reporting."""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.models import Batch, CollectionRequest, PassportEvent, now
from .common import rec_class

STAGES = ["household", "collector", "mrf", "recycler", "residual", "final"]


def new_code(db: Session) -> str:
    n = (db.scalar(select(func.max(Batch.id))) or 0) + 1
    return f"VX-{now().year}-{n:05d}"


def create_batch(db: Session, col: CollectionRequest, material: str = "", owner_name: str = "", location: str = "") -> Batch:
    b = Batch(code=new_code(db), owner_user_id=col.user_id, ward_id=col.ward_id, stream=col.stream, material=material,
              material_key=col.material_key, input_kg=0, status="at_household", data_class=rec_class())
    db.add(b)
    db.flush()
    col.batch_id = b.id
    return b


def _hash(prev: str, b: Batch, seq: int, ev: PassportEvent) -> str:
    payload = json.dumps({"prev": prev, "batch": b.code, "seq": seq, "type": ev.event_type, "actor": ev.actor_name, "w": ev.weight_kg,
                          "ts": ev.ts.isoformat(), "meta": ev.meta}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def add_event(db: Session, batch: Batch, stage: str, event_type: str, actor_name: str = "", actor_role: str = "", location: str = "",
              weight_kg: float | None = None, status: str = "recorded", evidence: str = "", meta: dict | None = None, ts=None) -> PassportEvent:
    last = db.scalars(select(PassportEvent).where(PassportEvent.batch_id == batch.id).order_by(PassportEvent.seq.desc()).limit(1)).first()
    seq = (last.seq + 1) if last else 1
    ev = PassportEvent(batch_id=batch.id, seq=seq, stage=stage, event_type=event_type, actor_name=actor_name, actor_role=actor_role,
                       location=location, weight_kg=weight_kg, status=status, evidence=evidence, meta=meta or {}, data_class=rec_class(),
                       ts=ts or now(), prev_hash=last.hash if last else "")
    ev.hash = _hash(ev.prev_hash, batch, seq, ev)
    db.add(ev)
    db.flush()
    return ev


def verify_chain(db: Session, batch: Batch) -> dict:
    evs = db.scalars(select(PassportEvent).where(PassportEvent.batch_id == batch.id).order_by(PassportEvent.seq)).all()
    prev = ""
    for e in evs:
        if e.prev_hash != prev or _hash(prev, batch, e.seq, e) != e.hash:
            return {"intact": False, "broken_at_seq": e.seq, "events": len(evs)}
        prev = e.hash
    return {"intact": True, "events": len(evs), "head": prev[:16]}


def mass_balance(b: Batch) -> dict:
    accounted = b.recovered_kg + b.rejects_kg + b.loss_kg + b.other_kg
    disc = round(b.input_kg - accounted, 3)
    tol = max(0.02 * b.input_kg, 0.05)
    has_output = accounted > 0
    return {
        "input_kg": round(b.input_kg, 3), "recovered_kg": round(b.recovered_kg, 3), "rejects_kg": round(b.rejects_kg, 3),
        "process_loss_kg": round(b.loss_kg, 3), "other_output_kg": round(b.other_kg, 3), "residual_kg": round(b.residual_kg, 3),
        "residual_destination": b.residual_destination, "accounted_kg": round(accounted, 3), "discrepancy_kg": disc,
        "discrepancy_flag": has_output and abs(disc) > tol,
        "recovery_rate": round(b.recovered_kg / b.input_kg, 3) if b.input_kg else 0,
        "equation": "Input = Recovered + Rejects + Process loss/moisture + Other recorded output",
        "complete": has_output,
    }


def final_status(b: Batch) -> str:
    mb = mass_balance(b)
    if not mb["complete"]:
        return b.status
    if b.recovered_kg <= 0:
        return "residual_recorded"
    if b.input_kg and b.recovered_kg / b.input_kg >= 0.98 and not mb["discrepancy_flag"]:
        return "recovery_completed"
    return "partially_recovered"


STATUS_TEXT = {
    "at_household": "At household — awaiting collection", "collected": "Collected by waste worker", "at_facility": "Received at facility",
    "processing": "Being processed", "recovery_completed": "Recovery completed (per recorded quantities)",
    "partially_recovered": "Partially recovered — remainder recorded as rejects / loss", "residual_recorded": "No recovery — residual disposal recorded",
}
