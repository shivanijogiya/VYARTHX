"""Waste Digital Twin — a transparent, ward-level what-if simulation in plain Python/numpy.

This is a SIMPLIFIED SIMULATION of a *pilot zone*, calibrated from the simulated demo database. It is NOT a live
operational twin of a real city. Every assumption is listed in ASSUMPTIONS and returned with every run.
Daily loop (per ward for collection, city-level for processing):
  generation → participation → collection queue (vehicle capacity) → segregation split →
  compost / MRF processing queues (capacity, downtime) → recycler demand (stock) → residual → landfill pressure
"""
from __future__ import annotations

import math
from copy import deepcopy

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.models import Facility, Vehicle, Ward
from ..services.common import haversine_km

ASSUMPTIONS = {
    "per_capita_kg_per_day": ("Waste generated per person per day", 0.55, "assumption (illustrative; replace with ULB data)"),
    "wet_fraction": ("Share of generated waste that is wet/organic", 0.50, "assumption"),
    "dry_fraction": ("Share that is dry (recyclable + non-recyclable)", 0.32, "assumption"),
    "other_fraction": ("Share that is sanitary/inert/other (goes to residual stream)", 0.18, "assumption"),
    "trips_per_vehicle_per_day": ("Collection trips per vehicle per day at frequency 1.0", 2.0, "assumption"),
    "mixed_recovery_rate": ("Share of MIXED dry waste still recovered informally/at dumpsite sorting", 0.06, "assumption"),
    "mrf_recovery_efficiency": ("Share of clean sorted dry input that becomes saleable material", 0.88, "assumption"),
    "wet_process_efficiency": ("Share of wet input accepted by biological processing (rest rejected)", 0.90, "assumption"),
    "contamination_base": ("Contamination of segregated dry stream at baseline", 0.12, "assumption"),
    "contamination_new_adopter": ("Extra contamination per +1.0 of segregation increase (newcomers learning)", 0.15, "assumption"),
    "queue_days_limit": ("Processing queue spoils/overflows beyond this many days of capacity", 2.0, "assumption"),
    "stock_days_limit": ("Unsold material stock beyond this many days of recycler demand is residual", 10.0, "assumption"),
    "incentive_uplift": ("Max share of the segregation gap closed by GreenPoints enrolment", 0.25, "assumption"),
    "landfill_share": ("Pilot zone's share of total landfill inflow", 0.20, "assumption"),
    "compost_yield": ("Compost output as share of wet input", 0.30, "assumption (estimate only)"),
}

PARAM_META = [
    ("segregation_rate", "Household segregation rate", 0.0, 0.95, 0.01, "share"),
    ("participation", "Collection participation (waste reaching the system)", 0.4, 1.0, 0.01, "share"),
    ("vehicles", "Collection vehicles available", 0, 80, 1, "count"),
    ("vehicle_capacity_t", "Vehicle capacity", 0.5, 8.0, 0.1, "t"),
    ("collection_frequency", "Collection frequency (rounds/day)", 0.25, 2.0, 0.05, "×"),
    ("mrf_capacity_tpd", "Dry processing (MRF) capacity", 0, 400, 1, "t/day"),
    ("compost_capacity_tpd", "Composting + biomethanation capacity", 0, 400, 1, "t/day"),
    ("recycler_demand_tpd", "Recycler demand for recovered material", 0, 200, 1, "t/day"),
    ("festival_multiplier", "Festival / event waste multiplier", 1.0, 3.0, 0.05, "×"),
    ("festival_days", "Festival duration", 0, 21, 1, "days"),
    ("facility_downtime", "Processing facility downtime", 0.0, 1.0, 0.05, "share"),
    ("landfill_remaining_t", "Landfill remaining reported capacity", 1000, 1_500_000, 1000, "t"),
    ("incentive_participation", "GreenPoints incentive enrolment", 0.0, 1.0, 0.05, "share"),
]


def baseline_params(db: Session) -> dict:
    wards = db.scalars(select(Ward).order_by(Ward.id)).all()
    vehicles = db.scalars(select(Vehicle)).all()
    facs = db.scalars(select(Facility)).all()
    mrf = sum(f.capacity_tpd for f in facs if f.type == "mrf")
    comp = sum(f.capacity_tpd for f in facs if f.type in ("compost", "vermicompost", "biomethanation"))
    rec = sum(f.capacity_tpd for f in facs if f.type == "recycler")
    land = [f for f in facs if f.type in ("landfill", "dumpsite") and f.remaining_capacity_t]
    rem = sum(f.remaining_capacity_t for f in land) or 500_000
    avg_cap = (sum(v.capacity_kg for v in vehicles) / len(vehicles) / 1000) if vehicles else 3.0
    return {
        "segregation_rate": 0.42, "participation": 0.88, "vehicles": len(vehicles) or 30, "vehicle_capacity_t": round(avg_cap, 2),
        "collection_frequency": 1.0, "mrf_capacity_tpd": round(mrf, 1) or 45.0, "compost_capacity_tpd": round(comp, 1) or 60.0,
        "recycler_demand_tpd": round(rec * 0.6, 1) or 20.0, "festival_multiplier": 1.0, "festival_days": 0, "facility_downtime": 0.0,
        "landfill_remaining_t": round(rem, 0), "incentive_participation": 0.0,
        "vehicles_down_ward": None,  # ward id losing one vehicle (scenario B)
        "vehicles_down_count": 0,
        "horizon_days": 60,
    }


def _ward_vehicles(wards, vehicles, p):
    n = {w.id: 0 for w in wards}
    for v in vehicles:
        n[v.ward_id] = n.get(v.ward_id, 0) + 1
    base_total = sum(n.values()) or 1
    # scale per-ward vehicle counts to the requested fleet size, keeping the baseline distribution
    target = p["vehicles"]
    out = {}
    acc = 0.0
    for w in wards:
        share = n.get(w.id, 0) / base_total
        out[w.id] = share * target
    if p.get("vehicles_down_ward") and p.get("vehicles_down_count", 0) > 0:
        out[p["vehicles_down_ward"]] = max(0.0, out[p["vehicles_down_ward"]] - p["vehicles_down_count"])
    return out


def simulate(db: Session, params: dict | None = None, base: dict | None = None) -> dict:
    wards = db.scalars(select(Ward).order_by(Ward.id)).all()
    vehicles = db.scalars(select(Vehicle)).all()
    base = base or baseline_params(db)
    p = deepcopy(base)
    p.update({k: v for k, v in (params or {}).items() if v is not None})
    A = {k: v[1] for k, v in ASSUMPTIONS.items()}
    T = int(p["horizon_days"])
    W = len(wards)
    pop = np.array([w.population for w in wards], dtype=float)
    veh = _ward_vehicles(wards, vehicles, p)
    veh_arr = np.array([veh[w.id] for w in wards], dtype=float)

    seg_base = base["segregation_rate"]
    gap = max(0.0, 1 - p["segregation_rate"])
    seg = min(0.98, p["segregation_rate"] + A["incentive_uplift"] * p["incentive_participation"] * gap)
    part = min(1.0, p["participation"] + 0.05 * p["incentive_participation"])
    contam = min(0.6, A["contamination_base"] + A["contamination_new_adopter"] * max(0.0, seg - seg_base))

    mrf_cap = p["mrf_capacity_tpd"] * (1 - p["facility_downtime"])
    comp_cap = p["compost_capacity_tpd"] * (1 - p["facility_downtime"])
    cap_per_vehicle = p["vehicle_capacity_t"] * A["trips_per_vehicle_per_day"] * p["collection_frequency"]
    coll_cap_w = veh_arr * cap_per_vehicle

    backlog = np.zeros(W)
    wet_q = dry_q = stock = 0.0
    cum_residual = 0.0
    ts = {k: [] for k in ["generated", "collected", "backlog", "residual", "mrf_util", "compost_util", "recovered", "delay_days", "uncollected"]}
    totals = dict(generated=0.0, reach=0.0, uncollected=0.0, collected=0.0, segregated=0.0, wet_processed=0.0, dry_processed=0.0,
                  recovered_sold=0.0, compost=0.0, residual=0.0, spoiled=0.0, rejects=0.0, mixed_recovered=0.0, clean_dry=0.0, mixed=0.0, wet_seg=0.0, dry_seg=0.0)
    mrf_hi = comp_hi = 0
    peak_backlog_ward = np.zeros(W)
    f0 = 10  # festival starts on day 10
    for d in range(T):
        mult = p["festival_multiplier"] if (f0 <= d < f0 + int(p["festival_days"])) else 1.0
        gen_w = pop * A["per_capita_kg_per_day"] / 1000.0 * mult
        reach_w = gen_w * part
        unc_w = gen_w - reach_w
        avail = backlog + reach_w
        coll_w = np.minimum(avail, coll_cap_w)
        backlog = avail - coll_w
        peak_backlog_ward = np.maximum(peak_backlog_ward, backlog)
        coll = float(coll_w.sum())
        wet_c, dry_c, oth_c = coll * A["wet_fraction"], coll * A["dry_fraction"], coll * A["other_fraction"]
        wet_s, dry_s = wet_c * seg, dry_c * seg
        mixed_w, mixed_d = wet_c - wet_s, dry_c - dry_s
        # wet processing
        wet_avail = wet_s + wet_q
        wet_proc = min(wet_avail, comp_cap)
        wet_q = wet_avail - wet_proc
        spoil_w = max(0.0, wet_q - A["queue_days_limit"] * max(comp_cap, 0.001)) if comp_cap > 0 else wet_q
        wet_q -= spoil_w
        wet_rej = wet_proc * (1 - A["wet_process_efficiency"])
        compost = (wet_proc - wet_rej) * A["compost_yield"]
        # dry processing
        dry_avail = dry_s + dry_q
        dry_proc = min(dry_avail, mrf_cap)
        dry_q = dry_avail - dry_proc
        spoil_d = max(0.0, dry_q - A["queue_days_limit"] * max(mrf_cap, 0.001)) if mrf_cap > 0 else dry_q
        dry_q -= spoil_d
        clean = dry_proc * (1 - contam)
        mat = clean * A["mrf_recovery_efficiency"]
        dry_rej = dry_proc - mat
        stock += mat
        sold = min(stock, p["recycler_demand_tpd"])
        stock -= sold
        over = max(0.0, stock - A["stock_days_limit"] * max(p["recycler_demand_tpd"], 0.001)) if p["recycler_demand_tpd"] > 0 else stock
        stock -= over
        mixed_rec = mixed_d * A["mixed_recovery_rate"]
        resid = oth_c + mixed_w + mixed_d - mixed_rec + wet_rej + dry_rej + spoil_w + spoil_d + over
        cum_residual += resid
        for k, v in dict(generated=float(gen_w.sum()), reach=float(reach_w.sum()), uncollected=float(unc_w.sum()), collected=coll, segregated=wet_s + dry_s,
                         wet_processed=wet_proc, dry_processed=dry_proc, recovered_sold=sold, compost=compost, residual=resid, spoiled=spoil_w + spoil_d + over,
                         rejects=wet_rej + dry_rej, mixed_recovered=mixed_rec, clean_dry=clean, mixed=mixed_w + mixed_d, wet_seg=wet_s, dry_seg=dry_s).items():
            totals[k] += v
        cap_total = float(coll_cap_w.sum())
        ts["generated"].append(round(float(gen_w.sum()), 2)); ts["collected"].append(round(coll, 2)); ts["backlog"].append(round(float(backlog.sum()), 2))
        ts["residual"].append(round(resid, 2)); ts["recovered"].append(round(sold + compost, 2))
        mu = (dry_proc / mrf_cap) if mrf_cap > 0 else (1.0 if dry_avail > 0 else 0)
        cu = (wet_proc / comp_cap) if comp_cap > 0 else (1.0 if wet_avail > 0 else 0)
        ts["mrf_util"].append(round(min(mu, 1.0), 3)); ts["compost_util"].append(round(min(cu, 1.0), 3))
        ts["delay_days"].append(round(float((backlog.sum() / cap_total)) if cap_total > 0 else (99 if backlog.sum() > 0 else 0), 2))
        ts["uncollected"].append(round(float(unc_w.sum()), 2))
        mrf_hi += 1 if mu >= 0.95 else 0
        comp_hi += 1 if cu >= 0.95 else 0

    last7_res = float(np.mean(ts["residual"][-7:])) if ts["residual"] else 0.0
    inflow_total = last7_res / max(A["landfill_share"], 0.01)
    days_to_cap = p["landfill_remaining_t"] / inflow_total if inflow_total > 0 else None
    land_press = min(1.0, (cum_residual / A["landfill_share"]) / max(p["landfill_remaining_t"], 1))
    cap_total = float(coll_cap_w.sum())
    coll_util = float(np.mean([min(c / max(cap_total, 1e-9), 1.0) for c in ts["collected"]])) if cap_total else 0.0
    end_backlog = float(backlog.sum())
    bottlenecks = []
    if mrf_hi / T >= 0.25:
        bottlenecks.append({"stage": "Dry processing (MRF)", "detail": f"≥95% utilised on {mrf_hi} of {T} days", "severity": "high" if mrf_hi / T > 0.6 else "medium"})
    if comp_hi / T >= 0.25:
        bottlenecks.append({"stage": "Composting / biomethanation", "detail": f"≥95% utilised on {comp_hi} of {T} days", "severity": "high" if comp_hi / T > 0.6 else "medium"})
    if end_backlog > 0.5 * max(cap_total, 1e-6) and ts["backlog"][-1] >= ts["backlog"][T // 2]:
        bottlenecks.append({"stage": "Collection", "detail": f"Backlog of {end_backlog:.1f} t at end of horizon and not clearing", "severity": "high"})
    if totals["spoiled"] > 0.02 * totals["collected"]:
        bottlenecks.append({"stage": "Queue overflow", "detail": f"{totals['spoiled']:.1f} t overflowed processing queues/stock into residual", "severity": "medium"})
    if p["recycler_demand_tpd"] > 0 and stock > 0.8 * A["stock_days_limit"] * p["recycler_demand_tpd"]:
        bottlenecks.append({"stage": "Recycler demand", "detail": "Recovered material is accumulating faster than it is sold", "severity": "medium"})
    affected = []
    for i, w in enumerate(wards):
        cap_w, gen_w0 = coll_cap_w[i], pop[i] * A["per_capita_kg_per_day"] / 1000.0 * part
        if peak_backlog_ward[i] > 0.25 * max(gen_w0, 1e-6) and cap_w < gen_w0 * 1.02:
            affected.append({"ward_id": w.id, "ward": w.name, "peak_backlog_t": round(float(peak_backlog_ward[i]), 2),
                             "capacity_t_per_day": round(float(cap_w), 2), "demand_t_per_day": round(float(gen_w0), 2),
                             "shortfall_t_per_day": round(float(max(gen_w0 - cap_w, 0)), 2)})
    affected.sort(key=lambda a: -a["peak_backlog_t"])
    kpis = {
        "generated_t": round(totals["generated"], 1), "collected_t": round(totals["collected"], 1), "uncollected_dispersed_t": round(totals["uncollected"], 1),
        "segregated_t": round(totals["segregated"], 1), "clean_dry_available_t": round(totals["clean_dry"], 1), "mixed_waste_t": round(totals["mixed"], 1),
        "wet_processed_t": round(totals["wet_processed"], 1), "dry_processed_t": round(totals["dry_processed"], 1),
        "recovered_material_t": round(totals["recovered_sold"] + totals["mixed_recovered"], 1), "compost_estimate_t": round(totals["compost"], 1),
        "residual_t": round(totals["residual"], 1), "residual_share": round(totals["residual"] / totals["collected"], 3) if totals["collected"] else 0,
        "contamination_rate": round(contam, 3), "effective_segregation_rate": round(seg, 3),
        "end_backlog_t": round(end_backlog, 1), "max_delay_days": round(max(ts["delay_days"]), 2), "avg_delay_days": round(float(np.mean(ts["delay_days"])), 2),
        "collection_utilisation": round(coll_util, 3), "mrf_utilisation": round(float(np.mean(ts["mrf_util"])), 3), "compost_utilisation": round(float(np.mean(ts["compost_util"])), 3),
        "landfill_pressure": round(land_press, 4), "landfill_days_to_capacity": round(days_to_cap) if days_to_cap else None,
        "residual_t_per_day_last7": round(last7_res, 2), "unsold_stock_t": round(stock, 1),
        "vehicle_capacity_t_per_day": round(cap_total, 1), "extra_vehicles_needed": max(0, math.ceil(end_backlog / max(cap_per_vehicle * T / 4, 1e-6))) if end_backlog > 0.1 else 0,
    }
    return {"params": p, "kpis": kpis, "timeseries": ts, "bottlenecks": bottlenecks, "affected_wards": affected[:8], "wards": W}


def _delta(base_k: dict, new_k: dict) -> dict:
    out = {}
    for k, v in new_k.items():
        b = base_k.get(k)
        if isinstance(v, (int, float)) and isinstance(b, (int, float)):
            out[k] = {"baseline": b, "scenario": v, "abs": round(v - b, 3), "pct": round(100 * (v - b) / b, 1) if b else None}
    return out


def explain(db: Session, base: dict, params: dict, full: dict) -> list[dict]:
    """Leave-one-out attribution: how much each changed assumption contributed to the headline outcomes."""
    changed = {k: v for k, v in params.items() if v is not None and k in base and v != base[k]}
    if not changed:
        return []
    rows = []
    for k in changed:
        rest = {kk: vv for kk, vv in changed.items() if kk != k}
        r = simulate(db, rest, base)["kpis"]
        fk = full["kpis"]
        rows.append({"parameter": k, "from": base[k], "to": changed[k],
                     "effect_on_residual_t": round(fk["residual_t"] - r["residual_t"], 1),
                     "effect_on_recovered_t": round(fk["recovered_material_t"] - r["recovered_material_t"], 1),
                     "effect_on_end_backlog_t": round(fk["end_backlog_t"] - r["end_backlog_t"], 1)})
    rows.sort(key=lambda x: -(abs(x["effect_on_residual_t"]) + abs(x["effect_on_recovered_t"]) + abs(x["effect_on_end_backlog_t"])))
    return rows


def suggestions(db: Session, base_res: dict, res: dict, params: dict) -> list[str]:
    s = []
    k, b = res["kpis"], base_res["kpis"]
    wards = {w.id: w for w in db.scalars(select(Ward)).all()}
    if res["affected_wards"]:
        top = res["affected_wards"][0]
        w0 = wards.get(top["ward_id"])
        if w0:
            near = sorted([w for w in wards.values() if w.id != w0.id], key=lambda w: haversine_km(w0.lat, w0.lng, w.lat, w.lng))[:2]
            names = ", ".join(w.name for w in near)
            s.append(f"{top['ward']} is short by {top['shortfall_t_per_day']} t/day: borrow spare vehicle capacity from nearby wards ({names}) or add a temporary vehicle.")
    if k["extra_vehicles_needed"]:
        s.append(f"About {k['extra_vehicles_needed']} additional vehicle(s) would be needed to clear the end-of-horizon backlog (planning estimate).")
    if k["landfill_days_to_capacity"] is not None and k["landfill_days_to_capacity"] < 730:
        s.append(f"At this residual rate the landfill reaches reported capacity in ~{k['landfill_days_to_capacity']} days — prioritise wet-waste diversion and dry recovery.")
    if k["compost_utilisation"] > 0.9:
        s.append("Biological processing is saturated: add composting/biomethanation capacity or decentralised composting.")
    if k["mrf_utilisation"] > 0.9:
        s.append("Dry processing is saturated: add MRF shifts or capacity before pushing segregation higher.")
    if k["residual_t"] < b["residual_t"] * 0.95:
        s.append(f"Residual waste falls by {100*(1-k['residual_t']/b['residual_t']):.1f}% versus baseline under these assumptions.")
    return s


def run_scenario(db: Session, name: str, params: dict) -> dict:
    base = baseline_params(db)
    base_res = simulate(db, {}, base)
    res = simulate(db, params, base)
    return {"name": name, "baseline": {"kpis": base_res["kpis"], "timeseries": base_res["timeseries"], "bottlenecks": base_res["bottlenecks"], "params": base_res["params"]},
            "scenario": res, "delta": _delta(base_res["kpis"], res["kpis"]), "attribution": explain(db, base, params, res),
            "suggestions": suggestions(db, base_res, res, params), "assumptions": {k: {"label": v[0], "value": v[1], "basis": v[2]} for k, v in ASSUMPTIONS.items()},
            "label": "Simulated demonstration data — simplified model of a pilot zone, not a live digital twin of a real city.", "data_class": "simulated"}


def predefined(db: Session) -> list[dict]:
    base = baseline_params(db)
    wards = db.scalars(select(Ward).order_by(Ward.population.desc())).all()
    big = wards[0].id if wards else None
    return [
        {"id": "A", "name": "A · 30% more households segregate correctly", "description": "Segregation rate ×1.3 across the pilot zone.",
         "params": {"segregation_rate": round(min(0.95, base["segregation_rate"] * 1.3), 3)}},
        {"id": "B", "name": "B · A collection vehicle becomes unavailable", "description": "One vehicle is lost in the most populous ward.",
         "params": {"vehicles_down_ward": big, "vehicles_down_count": 1}},
        {"id": "C", "name": "C · Landfill reaches 90% of reported capacity", "description": "Only 10% of reported landfill capacity remains.",
         "params": {"landfill_remaining_t": round(0.10 * (_landfill_reported(db) or base["landfill_remaining_t"] * 3.0), 0)}},
        {"id": "D", "name": "D · Festival increases waste generation", "description": "Waste ×1.8 for 7 days.", "params": {"festival_multiplier": 1.8, "festival_days": 7}},
        {"id": "E", "name": "E · Processing facility downtime (40%)", "description": "MRF and composting run at 60% capacity.", "params": {"facility_downtime": 0.4}},
        {"id": "F", "name": "F · GreenPoints incentives reach 70% of households", "description": "Incentive enrolment lifts segregation and participation.", "params": {"incentive_participation": 0.7}},
    ]


def _landfill_reported(db: Session) -> float:
    fs = db.scalars(select(Facility).where(Facility.type.in_(["landfill", "dumpsite"]), Facility.reported_capacity_t.is_not(None))).all()
    return float(sum(f.reported_capacity_t for f in fs))
