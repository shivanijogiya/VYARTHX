"""GreenPoints ledger. Deterministic backend logic only — no LLM or client can write balances directly.

Buckets: provisional -> verified (after collector confirmation) -> final (after downstream facility confirmation).
Spendable = verified + final. Every entry has a unique idempotency key, so a duplicate credit is impossible.
"""
from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.models import (CollectionRequest, RewardCatalog, RewardTransaction, Redemption, Submission, User, now)
from .common import get_cfg, rec_class

LEVELS = [(0, "Seedling"), (100, "Sprout"), (300, "Sapling"), (700, "Green Champion"), (1500, "Eco Guardian")]


def _add(db: Session, user_id: int, bucket: str, amount: int, kind: str, idem: str, ref_type: str = "", ref_id: int | None = None, note: str = ""):
    if db.scalar(select(RewardTransaction.id).where(RewardTransaction.idem_key == idem)):
        return None
    try:
        with db.begin_nested():
            tx = RewardTransaction(user_id=user_id, bucket=bucket, amount=int(amount), kind=kind, ref_type=ref_type, ref_id=ref_id,
                                   idem_key=idem, note=note, data_class=rec_class())
            db.add(tx)
            db.flush()
        return tx
    except IntegrityError:
        return None


def balances(db: Session, user_id: int) -> dict:
    rows = db.execute(select(RewardTransaction.bucket, func.coalesce(func.sum(RewardTransaction.amount), 0))
                      .where(RewardTransaction.user_id == user_id).group_by(RewardTransaction.bucket)).all()
    b = {"provisional": 0, "verified": 0, "final": 0}
    for k, v in rows:
        b[k] = int(v)
    earned = db.scalar(select(func.coalesce(func.sum(RewardTransaction.amount), 0)).where(
        RewardTransaction.user_id == user_id, RewardTransaction.bucket.in_(["verified", "final"]),
        RewardTransaction.amount > 0, RewardTransaction.kind != "provisional_convert")) or 0
    conv = db.scalar(select(func.coalesce(func.sum(RewardTransaction.amount), 0)).where(
        RewardTransaction.user_id == user_id, RewardTransaction.bucket == "verified", RewardTransaction.kind == "provisional_convert")) or 0
    lifetime = int(earned) + int(conv)
    level = LEVELS[0]
    nxt = None
    for i, (th, nm) in enumerate(LEVELS):
        if lifetime >= th:
            level = (th, nm)
            nxt = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    return {**b, "spendable": b["verified"] + b["final"], "total": sum(b.values()), "lifetime_earned": lifetime,
            "level": level[1], "next_level": nxt[1] if nxt else None, "next_level_at": nxt[0] if nxt else None}


def earned_today(db: Session, user_id: int) -> int:
    since = now().replace(hour=0, minute=0, second=0, microsecond=0)
    return int(db.scalar(select(func.coalesce(func.sum(RewardTransaction.amount), 0)).where(
        RewardTransaction.user_id == user_id, RewardTransaction.amount > 0, RewardTransaction.created_at >= since,
        RewardTransaction.kind.in_(["provisional_credit", "verified_credit", "final_credit", "bonus"]))) or 0)


def streak_days(db: Session, user_id: int) -> int:
    rows = db.scalars(select(CollectionRequest.collected_at).where(
        CollectionRequest.user_id == user_id, CollectionRequest.collected_at.is_not(None))).all()
    days = sorted({r.date() for r in rows}, reverse=True)
    if not days:
        return 0
    today = now().date()
    if (today - days[0]).days > 1:
        return 0
    s, prev = 1, days[0]
    for d in days[1:]:
        if (prev - d).days == 1:
            s += 1
            prev = d
        else:
            break
    return s


def compute_points(cfg: dict, material_key: str, weight_kg: float, contamination: str, stream: str, streak: int) -> dict:
    q = cfg["quality_factor"].get(contamination, 0.7)
    if stream == "special":
        base = float(cfg.get("flat_special_handover", 20))
        q = 1.0
        formula = f"flat special-care handover {base:g} (safe handover rewarded, not weight)"
    else:
        rate = float(cfg["rates_per_kg"].get(material_key, 0))
        base = weight_kg * rate
        formula = f"{weight_kg:g} kg × {rate:g} pts/kg × quality {q:g}"
    behaviour = min(streak, int(cfg["behaviour_bonus_cap"])) * float(cfg["behaviour_bonus_per_streak_day"]) if base > 0 else 0
    total = int(round(base * q + behaviour))
    return {"base": round(base, 2), "quality_factor": q, "behaviour_bonus": behaviour, "total": total,
            "formula": f"{formula} + behaviour bonus {behaviour:g}"}


def provisional_award(db: Session, user_id: int, sub: Submission) -> dict:
    cfg = get_cfg(db)
    cls = sub.classification or {}
    if not cls.get("reward_eligible"):
        return {"credited": 0, "reason": cls.get("reward_note", "not eligible")}
    if sub.confidence < cfg["provisional_min_confidence"]:
        return {"credited": 0, "reason": "confidence below threshold"}
    q = cfg["quality_factor"].get(sub.contamination, 0.7)
    amount = max(1, int(round(cfg["provisional_flat"] * q)))
    room = int(cfg["max_points_per_user_day"]) - earned_today(db, user_id)
    if room <= 0:
        return {"credited": 0, "reason": "daily points cap reached"}
    amount = min(amount, room)
    tx = _add(db, user_id, "provisional", amount, "provisional_credit", f"prov:sub:{sub.id}", "submission", sub.id, "AI-verified submission (provisional)")
    return {"credited": amount if tx else 0, "duplicate": tx is None, "tx_id": tx.id if tx else None}


def verified_award(db: Session, col: CollectionRequest, weight_kg: float, contamination: str) -> dict:
    """Credit verified points after collector confirmation. Idempotent per collection."""
    cfg = get_cfg(db)
    gate = f"ver:coll:{col.id}"
    if db.scalar(select(RewardTransaction.id).where(RewardTransaction.idem_key == gate)):
        return {"duplicate": True, "credited": 0}
    streak = streak_days(db, col.user_id) + 1
    pts = compute_points(cfg, col.material_key, weight_kg, contamination, col.stream, streak)
    total = pts["total"]
    room = int(cfg["max_points_per_user_day"]) - earned_today(db, col.user_id)
    capped = False
    if total > room:
        total, capped = max(room, 0), True
    prov = 0
    if col.submission_id:
        prov = int(db.scalar(select(func.coalesce(func.sum(RewardTransaction.amount), 0)).where(
            RewardTransaction.user_id == col.user_id, RewardTransaction.bucket == "provisional",
            RewardTransaction.ref_type == "submission", RewardTransaction.ref_id == col.submission_id)) or 0)
    conv = min(prov, total) if prov > 0 else 0
    extra = total - conv
    with db.begin_nested():
        if conv > 0:
            _add(db, col.user_id, "provisional", -conv, "provisional_convert", f"conv:{col.id}:p", "submission", col.submission_id, "Provisional → verified")
            _add(db, col.user_id, "verified", conv, "provisional_convert", f"conv:{col.id}:v", "submission", col.submission_id, "Provisional → verified")
        if prov - conv > 0:
            _add(db, col.user_id, "provisional", -(prov - conv), "provisional_expire", f"exp:{col.id}", "submission", col.submission_id, "Unconverted provisional released")
        _add(db, col.user_id, "verified", extra, "verified_credit", gate, "collection", col.id,
             f"Collector-confirmed handover ({pts['formula']})" + (" — daily cap applied" if capped else ""))
    return {"credited": total, "converted": conv, "extra": extra, "capped": capped, "breakdown": pts, "streak_days": streak}


def final_award(db: Session, user_id: int, batch_id: int, record_id: int, material_key: str, recovered_kg: float) -> dict:
    cfg = get_cfg(db)
    rate = float(cfg["rates_per_kg"].get(material_key, 0))
    amount = int(round(recovered_kg * rate * float(cfg["recovery_bonus_factor"])))
    if amount <= 0:
        return {"credited": 0, "reason": "no recovered quantity or no reward rate"}
    tx = _add(db, user_id, "final", amount, "final_credit", f"fin:batch:{batch_id}:{record_id}", "batch", batch_id,
              f"Recovery bonus: facility confirmed {recovered_kg:g} kg recovered")
    return {"credited": amount if tx else 0, "duplicate": tx is None}


def redeem(db: Session, user: User, item: RewardCatalog) -> Redemption:
    b = balances(db, user.id)
    if not item.active:
        raise ValueError("Reward is not active")
    if b["spendable"] < item.points_cost:
        raise ValueError(f"Insufficient spendable points ({b['spendable']} available, {item.points_cost} needed). Provisional points cannot be redeemed.")
    levels = [nm for _, nm in LEVELS]
    if item.min_level and levels.index(b["level"]) < item.min_level:
        raise ValueError(f"Requires level {levels[item.min_level]}")
    from_verified = min(b["verified"], item.points_cost)
    from_final = item.points_cost - from_verified
    token = secrets.token_hex(4)
    with db.begin_nested():
        if from_verified:
            _add(db, user.id, "verified", -from_verified, "redemption", f"red:{token}:v", "reward", item.id, f"Redeemed: {item.title}")
        if from_final:
            _add(db, user.id, "final", -from_final, "redemption", f"red:{token}:f", "reward", item.id, f"Redeemed: {item.title}")
        r = Redemption(user_id=user.id, catalog_id=item.id, points=item.points_cost,
                       voucher_code=f"VX-DEMO-{token.upper()}", status="issued_demo_voucher")
        db.add(r)
        db.flush()
    return r


def community_points(db: Session, user_ids: list[int], days: int = 30) -> int:
    if not user_ids:
        return 0
    since = now() - timedelta(days=days)
    return int(db.scalar(select(func.coalesce(func.sum(RewardTransaction.amount), 0)).where(
        RewardTransaction.user_id.in_(user_ids), RewardTransaction.amount > 0, RewardTransaction.created_at >= since,
        RewardTransaction.kind.in_(["verified_credit", "final_credit", "bonus"]))) or 0)
