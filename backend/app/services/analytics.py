"""Municipal analytics: city overview, ward performance, landfill intelligence, recommendations, impact."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.models import (Batch, Complaint, CollectionRequest, Community, Facility, RewardTransaction, Redemption, Vehicle, Ward, WardDaily, now)
from . import forecast as fc
from .common import get_cfg, label
from .complaints import hotspot_clusters
from .community import community_stats

LANDFILL_SHARE = 0.20  # assumption: pilot zone = 20% of total landfill inflow (same as the Digital Twin)


def _last_day(db: Session):
    return db.scalar(select(func.max(WardDaily.day)))


def _sum_daily(db: Session, days: int, ward_id: int | None = None) -> dict:
    last = _last_day(db)
    if not last:
        return {k: 0.0 for k in ["generated_t", "collected_t", "segregated_t", "processed_t", "recovered_t", "residual_t"]}
    cols = [func.coalesce(func.sum(getattr(WardDaily, c)), 0) for c in ["generated_t", "collected_t", "segregated_t", "processed_t", "recovered_t", "residual_t"]]
    q = select(*cols).where(WardDaily.day > last - timedelta(days=days))
    if ward_id:
        q = q.where(WardDaily.ward_id == ward_id)
    r = db.execute(q).one()
    return dict(zip(["generated_t", "collected_t", "segregated_t", "processed_t", "recovered_t", "residual_t"], [float(x) for x in r]))


def platform_stats(db: Session, days: int = 30, ward_id: int | None = None) -> dict:
    since = now() - timedelta(days=days)
    cq = select(CollectionRequest).where(CollectionRequest.collected_at >= since)
    bq = select(Batch).where(Batch.created_at >= since)
    if ward_id:
        cq, bq = cq.where(CollectionRequest.ward_id == ward_id), bq.where(Batch.ward_id == ward_id)
    cols = db.scalars(cq).all()
    bs = db.scalars(bq).all()
    pend = db.scalar(select(func.count()).select_from(CollectionRequest).where(CollectionRequest.status.in_(["requested", "assigned", "accepted"]),
                                                                                *( [CollectionRequest.ward_id == ward_id] if ward_id else []))) or 0
    return {
        "collections": len(cols), "verified_collected_kg": round(sum(c.verified_weight_kg or 0 for c in cols), 2),
        "segregated_kg": round(sum((c.verified_weight_kg or 0) for c in cols if c.stream in ("wet", "dry") and c.kind in ("household", "marketplace", "event")), 2),
        "batches": len(bs), "recovered_kg": round(sum(b.recovered_kg for b in bs), 2), "rejects_kg": round(sum(b.rejects_kg for b in bs), 2),
        "residual_kg": round(sum(b.residual_kg for b in bs), 2), "processed_batches": sum(1 for b in bs if b.status in ("recovery_completed", "partially_recovered", "residual_recorded")),
        "pending_pickups": pend, "data_class": "simulated",
    }


def city_overview(db: Session, ward_id: int | None = None, days: int = 30) -> dict:
    s = _sum_daily(db, days, ward_id)
    plat = platform_stats(db, days, ward_id)
    period = f"last {days} days"
    comp = (s["collected_t"] / s["generated_t"]) if s["generated_t"] else 0
    seg_rate = (s["segregated_t"] / s["collected_t"]) if s["collected_t"] else 0
    vehicles = db.scalars(select(Vehicle).where(*( [Vehicle.ward_id == ward_id] if ward_id else []))).all()
    veh = {"total": len(vehicles), "available": sum(1 for v in vehicles if v.status == "available"), "on_route": sum(1 for v in vehicles if v.status == "on_route"),
           "maintenance": sum(1 for v in vehicles if v.status == "maintenance"), "gps_connected": sum(1 for v in vehicles if v.gps_connected),
           "note": "Vehicle locations are simulated; no real GPS feed is connected." if not any(v.gps_connected for v in vehicles) else ""}
    cq = select(func.count()).select_from(Complaint).where(Complaint.status.notin_(["closed", "merged"]), *( [Complaint.ward_id == ward_id] if ward_id else []))
    pending_c = db.scalar(cq) or 0
    since = now() - timedelta(days=days)
    issued = db.scalar(select(func.coalesce(func.sum(RewardTransaction.amount), 0)).where(RewardTransaction.amount > 0, RewardTransaction.created_at >= since,
                                                                                       RewardTransaction.kind.in_(["verified_credit", "final_credit", "bonus", "provisional_credit"]))) or 0
    redeemed = db.scalar(select(func.coalesce(func.sum(Redemption.points), 0)).where(Redemption.created_at >= since)) or 0
    facs = db.scalars(select(Facility).where(Facility.type.in_(["mrf", "recycler", "compost", "vermicompost", "biomethanation", "special_care", "ewaste"]))).all()
    fac_rows = [{"id": f.id, "name": f.name, "type": f.type, "capacity_tpd": f.capacity_tpd, "load_tpd": f.load_tpd,
                 "utilisation": round(f.load_tpd / f.capacity_tpd, 2) if f.capacity_tpd else 0, "downtime": f.downtime, "authorised": f.authorised,
                 "data_class": f.capacity_class} for f in facs]
    comms = [community_stats(db, c, days) for c in db.scalars(select(Community)).all()]
    part = sum(c["participation_pct"] for c in comms) / len(comms) if comms else 0
    SIM = "simulated"
    def m(key, lab, val, unit, src, dc=SIM):
        return {"key": key, "label": lab, "value": round(val, 2) if isinstance(val, float) else val, "unit": unit, "period": period, "source": src, "data_class": dc, "data_class_label": label(dc)}
    metrics = [
        m("generated", "Waste generated", s["generated_t"], "t", "Simulated city baseline (data/seed)"),
        m("collected", "Waste collected", s["collected_t"], "t", "Simulated city baseline"),
        m("segregated", "Waste segregated at source", s["segregated_t"], "t", "Simulated city baseline"),
        m("processed", "Waste processed", s["processed_t"], "t", "Simulated city baseline"),
        m("recovered", "Material recovered", s["recovered_t"], "t", "Simulated city baseline"),
        m("residual", "Residual waste", s["residual_t"], "t", "Simulated city baseline"),
        m("collection_completion", "Collection completion", round(100 * comp, 1), "%", "Simulated city baseline"),
        m("segregation_rate", "Segregation rate", round(100 * seg_rate, 1), "%", "Simulated city baseline"),
        m("vehicles_active", "Vehicles available / total", f"{veh['available']} / {veh['total']}", "", "Simulated fleet records"),
        m("pending_complaints", "Pending complaints", pending_c, "count", "VYARTHX platform records", plat["data_class"]),
        m("community_participation", "Community participation", round(part, 1), "%", "Simulated baseline blended with platform activity"),
        m("greenpoints_issued", "GreenPoints issued", int(issued), "pts", "VYARTHX reward ledger", plat["data_class"]),
        m("greenpoints_redeemed", "GreenPoints redeemed", int(redeemed), "pts", "VYARTHX reward ledger (demo vouchers)", plat["data_class"]),
    ]
    return {"ward_id": ward_id, "days": days, "metrics": metrics, "platform": plat, "vehicles": veh, "facilities": fac_rows, "pending_complaints": pending_c,
            "disclaimer": "City baseline values are SIMULATED demonstration data. 'Platform' values are records created in this running instance."}


def ward_table(db: Session, days: int = 30) -> list[dict]:
    rows = []
    hs = hotspot_clusters(db)
    for w in db.scalars(select(Ward).order_by(Ward.name)).all():
        s = _sum_daily(db, days, w.id)
        pc = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.ward_id == w.id, Complaint.status.notin_(["closed", "merged"]))) or 0
        veh = db.scalar(select(func.count()).select_from(Vehicle).where(Vehicle.ward_id == w.id)) or 0
        pend = db.scalar(select(func.count()).select_from(CollectionRequest).where(CollectionRequest.ward_id == w.id, CollectionRequest.status.in_(["requested", "assigned", "accepted"]))) or 0
        comp = s["collected_t"] / s["generated_t"] if s["generated_t"] else 0
        seg = s["segregated_t"] / s["collected_t"] if s["collected_t"] else 0
        res = s["residual_t"] / s["collected_t"] if s["collected_t"] else 0
        rows.append({"ward_id": w.id, "ward": w.name, "zone": w.zone, "population": w.population, "lat": w.lat, "lng": w.lng,
                     "generated_t_per_day": round(s["generated_t"] / days, 2), "collection_completion_pct": round(100 * comp, 1),
                     "segregation_pct": round(100 * seg, 1), "residual_share_pct": round(100 * res, 1), "recovered_t": round(s["recovered_t"], 1),
                     "pending_complaints": pc, "repeat_hotspots": sum(1 for h in hs if h["ward_id"] == w.id), "vehicles": veh, "pending_pickups": pend,
                     "data_class": "simulated"})
    return rows


def landfill_intelligence(db: Session) -> dict:
    sites = db.scalars(select(Facility).where(Facility.type.in_(["landfill", "dumpsite"]))).all()
    rr = fc.residual_ratio(db)
    f = fc.forecast(db, 30)
    total_gen_fc = (sum(f["total_t_per_day"]) / len(f["total_t_per_day"])) if f.get("total_t_per_day") else 0
    fc_res = total_gen_fc * rr
    last = _last_day(db)
    hist = []
    if last:
        rows = db.execute(select(WardDaily.day, func.sum(WardDaily.residual_t)).group_by(WardDaily.day).order_by(WardDaily.day)).all()
        daily_res = [float(r[1]) for r in rows]
    else:
        rows, daily_res = [], []
    avg7 = sum(daily_res[-7:]) / max(len(daily_res[-7:]), 1) if daily_res else 0
    out = []
    share_total = sum(s.meta.get("inflow_share", 0.5) for s in sites) or 1
    for s in sites:
        share = s.meta.get("inflow_share", 0.5) / share_total
        lshare = LANDFILL_SHARE
        daily_in = avg7 / lshare * share
        f_in = fc_res / lshare * share
        rem = s.remaining_capacity_t or 0
        days_cap = rem / f_in if f_in > 0 else None
        cum, trend = 0.0, []
        for (d, r) in reversed(rows[-60:]):
            cum += float(r) * share
            trend.append({"day": d.date().isoformat(), "remaining_t": round(rem + cum, 0)})
        trend.reverse()
        out.append({"id": s.id, "name": s.name, "type": s.type, "reported_capacity_t": s.reported_capacity_t, "remaining_capacity_t": rem,
                    "remaining_pct": round(100 * rem / s.reported_capacity_t, 1) if s.reported_capacity_t else None,
                    "daily_incoming_t": round(daily_in, 1), "forecast_incoming_t_per_day": round(f_in, 1),
                    "estimated_days_to_capacity": round(days_cap) if days_cap else None, "trend": trend, "capacity_class": s.capacity_class,
                    "capacity_label": label(s.capacity_class), "note": s.source_note})
    # diversion opportunities from baseline simulation parameters
    from ..simulation.twin import simulate

    base = simulate(db, {})
    k = base["kpis"]
    opp = [
        {"title": "Raise source segregation by 10 points", "est_residual_reduction_t_per_day": round(k["residual_t_per_day_last7"] - simulate(db, {"segregation_rate": min(0.95, base["params"]["segregation_rate"] + 0.10)})["kpis"]["residual_t_per_day_last7"], 2), "basis": "Digital Twin run (simulated)"},
        {"title": "Expand composting capacity by 20 t/day", "est_residual_reduction_t_per_day": round(k["residual_t_per_day_last7"] - simulate(db, {"compost_capacity_tpd": base["params"]["compost_capacity_tpd"] + 20})["kpis"]["residual_t_per_day_last7"], 2), "basis": "Digital Twin run (simulated)"},
    ]
    return {"sites": out, "forecast_note": "Planning estimate = remaining reported capacity ÷ forecast daily inflow. Not a substitute for engineering assessment or official landfill records.",
            "forecast_model": f.get("model"), "forecast_data": f.get("training_data"), "diversion_opportunities": opp,
            "capacity_disclaimer": "Capacity figures in this demo are SIMULATED placeholders; official values were not retrieved. Do not recommend landfill as the default route for recyclable or biodegradable material.",
            "residual_ratio_recent": round(rr, 3)}


def recommendations(db: Session) -> list[dict]:
    recs: list[dict] = []
    wt = ward_table(db, 14)
    for r in sorted(wt, key=lambda x: x["collection_completion_pct"])[:3]:
        if r["collection_completion_pct"] < 90:
            recs.append({"id": f"cov-{r['ward_id']}", "severity": "high" if r["collection_completion_pct"] < 85 else "medium", "title": f"Raise collection coverage in {r['ward']}",
                         "detail": f"Collection completion is {r['collection_completion_pct']}% (14-day, simulated baseline) with {r['vehicles']} vehicles assigned.",
                         "action": {"type": "open", "label": "Plan routes", "to": "/collection-planner"}, "requires_approval": True, "data_class": "estimate"})
    for r in sorted(wt, key=lambda x: -x["residual_share_pct"])[:2]:
        recs.append({"id": f"res-{r['ward_id']}", "severity": "medium", "title": f"{r['ward']}: high residual share ({r['residual_share_pct']}%)",
                     "detail": f"Segregation is {r['segregation_pct']}%. Targeted behaviour campaign and a community challenge could reduce residual waste.",
                     "action": {"type": "open", "label": "Create challenge", "to": "/command?tab=challenges"}, "requires_approval": False, "data_class": "estimate"})
    for f in db.scalars(select(Facility).where(Facility.capacity_tpd > 0)).all():
        u = f.load_tpd / f.capacity_tpd
        if u > 0.9 and f.type not in ("landfill", "dumpsite"):
            recs.append({"id": f"fac-{f.id}", "severity": "high", "title": f"{f.name} is at {u:.0%} utilisation",
                         "detail": "Processing bottleneck risk. Divert load to another authorised facility or add shifts.", "action": {"type": "open", "label": "Facilities", "to": "/command?tab=facilities"},
                         "requires_approval": True, "data_class": "simulated"})
    for h in hotspot_clusters(db)[:3]:
        w = db.get(Ward, h["ward_id"]) if h["ward_id"] else None
        recs.append({"id": f"hot-{round(h['lat'],3)}", "severity": "high" if h["count"] >= 5 else "medium", "title": f"Repeated hotspot ({h['count']} reports) in {w.name if w else 'ward'}",
                     "detail": f"Categories: {', '.join(c.replace('_',' ') for c in h['categories'])}. Consider inspection, bin placement or enforcement.", "action": {"type": "open", "label": "View on map", "to": "/hotspots"},
                     "requires_approval": False, "data_class": "pilot" if False else "simulated"})
    for c in db.scalars(select(Community)).all():
        s = community_stats(db, c)
        if s["contamination_pct"] > 25:
            recs.append({"id": f"cont-{c.id}", "severity": "low", "title": f"{c.name}: contamination {s['contamination_pct']}%", "detail": "Offer a Zero-Contamination Week challenge and educational nudges.",
                         "action": {"type": "open", "label": "Create challenge", "to": "/command?tab=challenges"}, "requires_approval": False, "data_class": "estimate"})
    ls = landfill_intelligence(db)
    for s in ls["sites"]:
        if s["estimated_days_to_capacity"] and s["estimated_days_to_capacity"] < 1500:
            recs.append({"id": f"lf-{s['id']}", "severity": "high" if s["estimated_days_to_capacity"] < 700 else "medium", "title": f"{s['name']}: ~{s['estimated_days_to_capacity']} days to reported capacity",
                         "detail": "Planning estimate (simulated capacity). Prioritise wet-waste diversion and dry recovery; run the Digital Twin for interventions.",
                         "action": {"type": "open", "label": "Landfill Intelligence", "to": "/landfill"}, "requires_approval": False, "data_class": "estimate"})
    fcast = fc.forecast(db, 7)
    if fcast.get("trained"):
        for s in fcast["series"]:
            last_week = _sum_daily(db, 7, s["ward_id"])["generated_t"] / 7
            if last_week and s["mean_t_per_day"] > 1.08 * last_week:
                recs.append({"id": f"fc-{s['ward_id']}", "severity": "low", "title": f"{s['ward']}: forecast demand up {100*(s['mean_t_per_day']/last_week-1):.0f}%",
                             "detail": "Next-7-day forecast exceeds last week's average (model trained on simulated history).", "action": None, "requires_approval": False, "data_class": "estimate"})
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(recs, key=lambda r: order[r["severity"]])[:14]


def impact_report(db: Session, user_id: int | None = None, days: int = 90) -> dict:
    cfg = get_cfg(db)
    since = now() - timedelta(days=days)
    q = select(Batch).where(Batch.created_at >= since)
    if user_id:
        q = q.where(Batch.owner_user_id == user_id)
    bs = db.scalars(q).all()
    collected = sum(b.input_kg for b in bs)
    rec = sum(b.recovered_kg for b in bs)
    by: dict[str, float] = {}
    co2 = 0.0
    for b in bs:
        if b.recovered_kg > 0:
            by[b.material_key or "mixed"] = by.get(b.material_key or "mixed", 0) + b.recovered_kg
            co2 += b.recovered_kg * cfg["co2e_factor_kg_per_kg_recovered"].get(b.material_key or "mixed", 0)
    return {"days": days, "verified_collected_kg": round(collected, 2), "facility_confirmed_recovered_kg": round(rec, 2),
            "recovered_by_material_kg": {k: round(v, 2) for k, v in by.items()}, "estimated_co2e_avoided_kg": round(co2, 1),
            "batches": len(bs), "batches_with_facility_confirmation": sum(1 for b in bs if b.recovered_kg > 0 or b.status in ("recovery_completed", "partially_recovered", "residual_recorded")),
            "method": "Only facility-confirmed recovered quantities are counted. CO₂e uses illustrative placeholder factors (editable config), so the figure is an ESTIMATE, not a verified carbon claim.",
            "co2e_note": cfg.get("co2e_note"), "data_class": "estimate"}
