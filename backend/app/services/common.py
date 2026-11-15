from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SEED_DIR, settings
from ..models.models import AuditLog, ConfigEntry, Notification, User, Ward, now

DATA_CLASS_LABELS = {
    "official": "Official data",
    "pilot": "Pilot observation",
    "estimate": "Model estimate",
    "simulated": "Simulated demonstration data",
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def road_km(lat1, lng1, lat2, lng2) -> float:
    """Straight-line distance scaled by a documented urban road factor (no live OSM routing offline)."""
    return haversine_km(lat1, lng1, lat2, lng2) * 1.3


@lru_cache(maxsize=1)
def kb_items() -> list[dict]:
    return json.loads((SEED_DIR / "waste_kb.json").read_text(encoding="utf-8"))["items"]


def kb_by_id(i: str) -> dict | None:
    return next((k for k in kb_items() if k["id"] == i), None)


@lru_cache(maxsize=1)
def policy_snippets() -> list[dict]:
    return json.loads((SEED_DIR / "policy_kb.json").read_text(encoding="utf-8"))["snippets"]


@lru_cache(maxsize=1)
def upcycle_ideas() -> dict:
    return json.loads((SEED_DIR / "upcycling_ideas.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _default_rewards() -> dict:
    return json.loads((SEED_DIR / "rewards_config.json").read_text(encoding="utf-8"))


def get_cfg(db: Session) -> dict:
    """Reward/assumption config: defaults overlaid with DB overrides (editable by municipal users)."""
    cfg = json.loads(json.dumps(_default_rewards()))
    row = db.get(ConfigEntry, "rewards")
    if row and isinstance(row.value, dict):
        for k, v in row.value.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def set_cfg(db: Session, patch: dict) -> dict:
    row = db.get(ConfigEntry, "rewards")
    cur = dict(row.value) if row and isinstance(row.value, dict) else {}
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(cur.get(k), dict):
            cur[k].update(v)
        else:
            cur[k] = v
    if row:
        row.value = cur
        row.updated_at = now()
    else:
        db.add(ConfigEntry(key="rewards", value=cur))
    db.flush()
    return get_cfg(db)


def audit(db: Session, user_id: int | None, action: str, entity: str = "", entity_id: int | None = None, **detail: Any) -> None:
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id, detail=detail))


def notify(db: Session, user_id: int, title: str, message: str, kind: str = "info") -> Notification | None:
    """Respect user notification preferences and avoid notification spam (max N per day)."""
    u = db.get(User, user_id)
    prefs = (u.prefs or {}) if u else {}
    n_prefs = prefs.get("notifications", {})
    if n_prefs.get("enabled") is False and kind not in ("safety", "system"):
        return None
    if n_prefs.get(kind) is False:
        return None
    limit = int(n_prefs.get("max_per_day", 6))
    from datetime import timedelta

    since = now() - timedelta(days=1)
    cnt = db.scalar(
        select(__import__("sqlalchemy").func.count()).select_from(Notification).where(
            Notification.user_id == user_id, Notification.created_at >= since
        )
    ) or 0
    if cnt >= limit and kind not in ("safety", "system"):
        return None
    n = Notification(user_id=user_id, title=title, message=message, kind=kind)
    db.add(n)
    return n


def nearest_ward(db: Session, lat: float, lng: float) -> Ward | None:
    wards = db.scalars(select(Ward)).all()
    if not wards:
        return None
    return min(wards, key=lambda w: haversine_km(lat, lng, w.lat, w.lng))


def label(dc: str) -> str:
    return DATA_CLASS_LABELS.get(dc, dc)


def rec_class() -> str:
    return settings.record_class
