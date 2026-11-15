"""Rule-based verification & fraud checks used by the Verification Agent."""
from __future__ import annotations

import statistics
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.models import CollectionRequest, Household, Submission, now
from .imagehash import hamming


def check_duplicate_image(db: Session, sha: str, phash: str, user_id: int, exclude_id: int | None = None) -> dict:
    out = {"exact": False, "near": False, "same_user": False, "matches": []}
    if not sha:
        return out
    q = select(Submission).where(Submission.sha256 != "")
    if exclude_id:
        q = q.where(Submission.id != exclude_id)
    for s in db.scalars(q.order_by(Submission.id.desc()).limit(2000)):
        d = 0 if s.sha256 == sha else hamming(phash, s.phash)
        if s.sha256 == sha:
            out["exact"] = True
        elif d <= 5:
            out["near"] = True
        else:
            continue
        out["matches"].append({"submission_id": s.id, "hamming": d, "same_user": s.user_id == user_id})
        if s.user_id == user_id:
            out["same_user"] = True
        if len(out["matches"]) >= 5:
            break
    return out


def check_timestamp(client_ts, exif_ts) -> dict:
    flags = []
    t = now()
    if client_ts:
        skew = abs((t - client_ts).total_seconds())
        if skew > 24 * 3600:
            flags.append({"code": "timestamp_skew", "severity": "high", "detail": f"Device timestamp differs from server time by {skew/3600:.1f} h"})
    if exif_ts:
        age = (t - exif_ts).total_seconds()
        if age > 48 * 3600:
            flags.append({"code": "image_old", "severity": "medium", "detail": f"Photo EXIF time is {age/3600:.0f} h old"})
        elif age < -3600:
            flags.append({"code": "image_future", "severity": "medium", "detail": "Photo EXIF time is in the future"})
    return {"flags": flags, "exif_present": exif_ts is not None, "client_ts_present": client_ts is not None}


def check_velocity(db: Session, user_id: int) -> dict:
    h = db.scalar(select(func.count()).select_from(Submission).where(Submission.user_id == user_id, Submission.created_at >= now() - timedelta(hours=1))) or 0
    d = db.scalar(select(func.count()).select_from(Submission).where(Submission.user_id == user_id, Submission.created_at >= now() - timedelta(days=1))) or 0
    flags = []
    if h > 5:
        flags.append({"code": "burst_submissions", "severity": "high", "detail": f"{h} submissions in the last hour"})
    if d > 20:
        flags.append({"code": "excess_daily_submissions", "severity": "medium", "detail": f"{d} submissions in 24 h"})
    return {"last_hour": h, "last_24h": d, "flags": flags}


def check_qr(provided: str | None, household: Household | None) -> dict:
    if not household:
        return {"status": "skipped", "detail": "No household registered for this user"}
    if not provided:
        return {"status": "missing", "detail": "No QR / household code supplied"}
    ok = provided.strip().upper() == household.code.upper()
    return {"status": "match" if ok else "mismatch", "detail": f"Supplied {provided} vs registered household code"}


def check_weight(db: Session, col: CollectionRequest, weight_kg: float, cfg: dict, worker_capacity: float | None = None) -> dict:
    flags = []
    if weight_kg <= 0:
        flags.append({"code": "non_positive_weight", "severity": "high", "detail": "Weight must be > 0"})
    est = col.est_weight_kg or 0
    if est > 0:
        ratio = weight_kg / est
        if ratio > 3 or ratio < 0.2:
            flags.append({"code": "weight_estimate_mismatch", "severity": "medium", "detail": f"Recorded {weight_kg:g} kg vs citizen estimate {est:g} kg (×{ratio:.1f})"})
    cap = float(cfg.get("max_verified_kg_per_household_day", 25))
    today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    done = db.scalar(select(func.coalesce(func.sum(CollectionRequest.verified_weight_kg), 0)).where(
        CollectionRequest.user_id == col.user_id, CollectionRequest.collected_at >= today, CollectionRequest.id != col.id)) or 0
    if col.kind in ("household", "ewaste", "special") and done + weight_kg > cap:
        flags.append({"code": "household_daily_cap", "severity": "high", "detail": f"{done + weight_kg:g} kg today exceeds household cap {cap:g} kg"})
    if worker_capacity and weight_kg > worker_capacity:
        flags.append({"code": "exceeds_worker_capacity", "severity": "medium", "detail": f"Exceeds worker capacity {worker_capacity:g} kg"})
    hist = [w for (w,) in db.execute(select(CollectionRequest.verified_weight_kg).where(
        CollectionRequest.user_id == col.user_id, CollectionRequest.verified_weight_kg.is_not(None), CollectionRequest.id != col.id)).all()]
    z = None
    if len(hist) >= 5:
        mu, sd = statistics.mean(hist), statistics.pstdev(hist) or 1.0
        z = (weight_kg - mu) / sd
        if abs(z) > 3:
            flags.append({"code": "weight_anomaly", "severity": "medium", "detail": f"Weight is {z:.1f}σ from this household's history"})
    return {"flags": flags, "z_score": z, "history_n": len(hist)}


def risk_score(flags: list[dict]) -> float:
    w = {"high": 0.5, "medium": 0.25, "low": 0.1}
    return round(min(1.0, sum(w.get(f["severity"], 0.1) for f in flags)), 2)
