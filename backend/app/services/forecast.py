"""Ward-level waste generation forecasting (scikit-learn GradientBoostingRegressor).

IMPORTANT: the model is trained on the *simulated* WardDaily history shipped with the demo. It demonstrates the
forecasting pipeline; it is not evidence of accuracy on real municipal data. Replace WardDaily with official
collection records to calibrate.
"""
from __future__ import annotations

import math
import time
from datetime import timedelta

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.models import Ward, WardDaily

_CACHE: dict = {}


def _features(days: list, idx0: int, festival: set) -> np.ndarray:
    rows = []
    for i, d in enumerate(days):
        doy = d.timetuple().tm_yday
        rows.append([d.weekday(), 1 if d.weekday() >= 5 else 0, math.sin(2 * math.pi * doy / 365), math.cos(2 * math.pi * doy / 365),
                     idx0 + i, 1 if d.date() in festival else 0])
    return np.array(rows, dtype=float)


def _festival_days(days: list) -> set:
    # festival bumps are generated at fixed offsets in the simulated history (see seed); infer from residual spikes
    return set()


def train(db: Session) -> dict:
    from sklearn.ensemble import GradientBoostingRegressor

    rows = db.execute(select(WardDaily.ward_id, WardDaily.day, WardDaily.generated_t).order_by(WardDaily.day)).all()
    key = (len(rows),)
    if _CACHE.get("key") == key:
        return _CACHE["model"]
    if len(rows) < 60:
        return {"trained": False, "reason": "insufficient history"}
    by_ward: dict[int, list] = {}
    for w, d, g in rows:
        by_ward.setdefault(w, []).append((d, g))
    models, metrics, means = {}, [], {}
    for w, series in by_ward.items():
        series.sort()
        days = [d for d, _ in series]
        y = np.array([g for _, g in series])
        mean = float(y[-28:].mean()) if len(y) >= 28 else float(y.mean())
        yr = y / max(float(y.mean()), 1e-6)
        X = _features(days, 0, set())
        hold = 14
        m = GradientBoostingRegressor(n_estimators=120, max_depth=3, learning_rate=0.08, subsample=0.9, random_state=7)
        m.fit(X[:-hold], yr[:-hold])
        pred = m.predict(X[-hold:])
        mape = float(np.mean(np.abs(pred - yr[-hold:]) / np.maximum(yr[-hold:], 1e-6)))
        metrics.append(mape)
        m2 = GradientBoostingRegressor(n_estimators=120, max_depth=3, learning_rate=0.08, subsample=0.9, random_state=7)
        m2.fit(X, yr)
        models[w] = (m2, float(y.mean()), days[-1], len(days))
        means[w] = mean
    info = {"trained": True, "models": models, "holdout_mape": round(float(np.mean(metrics)), 4), "wards": len(models), "trained_at": time.time(),
            "model": "sklearn GradientBoostingRegressor per ward (ratio-to-mean target)",
            "training_data": "SIMULATED ward history (data/seed) — pipeline demonstration only", "data_class": "estimate"}
    _CACHE["key"], _CACHE["model"] = key, info
    return info


def forecast(db: Session, horizon: int = 14, ward_id: int | None = None) -> dict:
    info = train(db)
    if not info.get("trained"):
        return {"trained": False, "series": [], "reason": info.get("reason")}
    out = []
    wards = {w.id: w for w in db.scalars(select(Ward)).all()}
    for wid, (m, mean, last, n) in info["models"].items():
        if ward_id and wid != ward_id:
            continue
        days = [last + timedelta(days=i + 1) for i in range(horizon)]
        X = _features(days, n, set())
        pred = np.clip(m.predict(X) * mean, 0, None)
        out.append({"ward_id": wid, "ward": wards[wid].name if wid in wards else str(wid),
                    "daily": [{"day": d.date().isoformat(), "generated_t": round(float(p), 3)} for d, p in zip(days, pred)],
                    "mean_t_per_day": round(float(pred.mean()), 3)})
    total = [round(sum(o["daily"][i]["generated_t"] for o in out), 3) for i in range(horizon)] if out else []
    return {"trained": True, "model": info["model"], "holdout_mape": info["holdout_mape"], "training_data": info["training_data"],
            "data_class": "estimate", "horizon_days": horizon, "series": out, "total_t_per_day": total,
            "note": "Holdout MAPE is measured on simulated data and must not be quoted as real-world accuracy."}


def residual_ratio(db: Session, days: int = 14, ward_id: int | None = None) -> float:
    q = select(func.sum(WardDaily.residual_t), func.sum(WardDaily.generated_t))
    last = db.scalar(select(func.max(WardDaily.day)))
    if not last:
        return 0.35
    q = q.where(WardDaily.day > last - timedelta(days=days))
    if ward_id:
        q = q.where(WardDaily.ward_id == ward_id)
    r, g = db.execute(q).one()
    return float(r or 0) / float(g or 1)
