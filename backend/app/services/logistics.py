"""Logistics tools: collector assignment, facility matching and capacity-aware routing (Google OR-Tools)."""
from __future__ import annotations

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models.models import Complaint, CollectionRequest, Facility, Vehicle, Ward, Worker
from .common import haversine_km, road_km

FUEL_L_PER_KM = 0.35  # planning assumption for a light compactor/tipper; editable in docs
DEST_TYPE_MAP = {  # KB destination type -> facility.type values
    "mrf": ["mrf"], "recycler": ["recycler"], "compost": ["compost", "vermicompost"], "biomethanation": ["biomethanation"],
    "special_care": ["special_care"], "ewaste": ["ewaste", "special_care"], "ngo": ["ngo"], "refurbisher": ["refurbisher"],
}


def rank_workers(db: Session, ward_id: int | None, lat: float, lng: float, weight_kg: float, stream: str, exclude: set[int] | None = None) -> list[dict]:
    out = []
    for w in db.scalars(select(Worker).where(Worker.available == True)).all():  # noqa: E712
        if exclude and w.id in exclude:
            continue
        d = haversine_km(lat, lng, w.lat, w.lng) if (w.lat or w.lng) else 99.0
        if weight_kg > w.capacity_kg:
            continue
        trained = "special_care" in (w.training or [])
        if stream == "special" and not trained:
            continue
        score = 1.0 / (1.0 + d) + (0.3 if w.ward_id == ward_id else 0) + (0.1 if trained else 0)
        out.append({"worker_id": w.id, "worker_code": w.worker_code, "distance_km": round(d, 2), "score": round(score, 3),
                    "special_care_trained": trained, "same_ward": w.ward_id == ward_id})
    return sorted(out, key=lambda x: -x["score"])


def rank_facilities(db: Session, dest_types: list[str], lat: float, lng: float, weight_kg: float, material_key: str = "") -> list[dict]:
    types: list[str] = []
    for d in dest_types:
        types += DEST_TYPE_MAP.get(d, [d])
    out = []
    for f in db.scalars(select(Facility).where(Facility.type.in_(types))).all():
        if not f.authorised or f.downtime:
            continue
        head = max(0.0, f.capacity_tpd - f.load_tpd)
        if head * 1000 < weight_kg:
            continue
        if f.accepts and material_key and material_key not in f.accepts and "all" not in f.accepts:
            continue
        d = road_km(lat, lng, f.lat, f.lng)
        score = 1.0 / (1.0 + d / 5.0) + 0.3 * (head / max(f.capacity_tpd, 1))
        out.append({"facility_id": f.id, "name": f.name, "type": f.type, "distance_km": round(d, 2), "headroom_t": round(head, 2),
                    "utilisation": round(f.load_tpd / f.capacity_tpd, 2) if f.capacity_tpd else 0, "score": round(score, 3), "data_class": f.data_class})
    return sorted(out, key=lambda x: -x["score"])


def _osrm_matrix(points: list[tuple[float, float]]) -> list[list[int]] | None:
    if not settings.OSRM_URL:
        return None
    try:
        import httpx

        coords = ";".join(f"{lng},{lat}" for lat, lng in points)
        r = httpx.get(f"{settings.OSRM_URL.rstrip('/')}/table/v1/driving/{coords}", params={"annotations": "distance"}, timeout=10)
        r.raise_for_status()
        return [[int(x or 0) for x in row] for row in r.json()["distances"]]
    except Exception:
        return None


def distance_matrix(points: list[tuple[float, float]]) -> tuple[list[list[int]], str]:
    m = _osrm_matrix(points)
    if m:
        return m, "OSRM road distances (configured OSRM_URL)"
    n = len(points)
    return [[int(road_km(*points[i], *points[j]) * 1000) for j in range(n)] for i in range(n)], "haversine × 1.3 urban road factor (no live OSM routing in this build)"


def build_stops(db: Session, ward_ids: list[int] | None = None) -> list[dict]:
    stops: list[dict] = []
    q = select(CollectionRequest).where(CollectionRequest.status.in_(["requested", "assigned", "accepted"]))
    for c in db.scalars(q).all():
        if ward_ids and c.ward_id not in ward_ids:
            continue
        stops.append({"type": "pickup", "id": c.id, "label": f"Pickup #{c.id} ({c.stream})", "lat": c.lat, "lng": c.lng,
                      "demand_kg": max(c.est_weight_kg, 1.0), "priority": c.priority, "ward_id": c.ward_id})
    for k in db.scalars(select(Complaint).where(Complaint.status.in_(["submitted", "ai_classified", "verified", "assigned", "in_progress", "reopened"]))).all():
        if ward_ids and k.ward_id not in ward_ids:
            continue
        stops.append({"type": "hotspot", "id": k.id, "label": f"Hotspot report #{k.id} ({k.category.replace('_', ' ')})", "lat": k.lat, "lng": k.lng,
                      "demand_kg": 300.0 if k.repeat_count < 3 else 600.0, "priority": 1 if (k.priority == 1 or k.repeat_count >= 3) else 2,
                      "ward_id": k.ward_id, "demand_note": "estimate — hotspot quantity not measured"})
    return stops


def _greedy(depot, stops, vehicles, dist_fn):
    routes = [{"vehicle": v, "stops": [], "load": 0.0} for v in vehicles]
    unserved = []
    for s in sorted(stops, key=lambda x: (x["priority"], -x["demand_kg"])):
        best = None
        for r in routes:
            if r["load"] + s["demand_kg"] <= r["vehicle"].capacity_kg:
                last = r["stops"][-1] if r["stops"] else depot
                d = dist_fn(last, s)
                if best is None or d < best[0]:
                    best = (d, r)
        if best:
            best[1]["stops"].append(s)
            best[1]["load"] += s["demand_kg"]
        else:
            unserved.append(s)
    return routes, unserved


def plan_routes(db: Session, ward_ids: list[int] | None = None, unavailable_vehicle_ids: list[int] | None = None, time_limit_s: int = 2) -> dict[str, Any]:
    """Capacity-aware vehicle routing with priority-weighted drop penalties."""
    unavailable = set(unavailable_vehicle_ids or [])
    vq = select(Vehicle).where(Vehicle.status == "available")
    vehicles = [v for v in db.scalars(vq).all() if v.id not in unavailable and (not ward_ids or v.ward_id in ward_ids)]
    stops = build_stops(db, ward_ids)
    if not stops:
        return {"routes": [], "unserved": [], "note": "No pending pickups or hotspots in scope.", "solver": "none", "distance_basis": ""}
    if not vehicles:
        return {"routes": [], "unserved": stops, "note": "No available vehicles in scope — add capacity or widen the ward filter.", "solver": "none", "distance_basis": ""}
    # processing destination: nearest authorised MRF with headroom
    c_lat = sum(s["lat"] for s in stops) / len(stops)
    c_lng = sum(s["lng"] for s in stops) / len(stops)
    fac = rank_facilities(db, ["mrf"], c_lat, c_lng, 0)
    depot_f = db.get(Facility, fac[0]["facility_id"]) if fac else None
    depot = {"lat": depot_f.lat if depot_f else c_lat, "lng": depot_f.lng if depot_f else c_lng, "label": depot_f.name if depot_f else "Ward yard"}
    pts = [(depot["lat"], depot["lng"])] + [(s["lat"], s["lng"]) for s in stops]
    matrix, basis = distance_matrix(pts)
    solver = "ortools"
    routes_out: list[dict] = []
    unserved: list[dict] = []
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2

        n = len(pts)
        mgr = pywrapcp.RoutingIndexManager(n, len(vehicles), 0)
        routing = pywrapcp.RoutingModel(mgr)
        cb = routing.RegisterTransitCallback(lambda i, j: matrix[mgr.IndexToNode(i)][mgr.IndexToNode(j)])
        routing.SetArcCostEvaluatorOfAllVehicles(cb)
        demand = [0] + [int(math.ceil(s["demand_kg"])) for s in stops]
        dcb = routing.RegisterUnaryTransitCallback(lambda i: demand[mgr.IndexToNode(i)])
        routing.AddDimensionWithVehicleCapacity(dcb, 0, [int(v.capacity_kg) for v in vehicles], True, "Load")
        for idx, s in enumerate(stops, start=1):
            penalty = 5_000_000 if s["priority"] <= 1 else 1_000_000
            routing.AddDisjunction([mgr.NodeToIndex(idx)], penalty)
        p = pywrapcp.DefaultRoutingSearchParameters()
        p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        p.time_limit.seconds = time_limit_s
        sol = routing.SolveWithParameters(p)
        if sol is None:
            raise RuntimeError("no solution")
        served = set()
        for vi, v in enumerate(vehicles):
            idx = routing.Start(vi)
            seq, load, dist = [], 0.0, 0
            prev = 0
            while not routing.IsEnd(idx):
                node = mgr.IndexToNode(idx)
                if node != 0:
                    s = stops[node - 1]
                    load += s["demand_kg"]
                    dist += matrix[prev][node]
                    seq.append({**s, "cum_load_kg": round(load, 1)})
                    served.add(node)
                    prev = node
                idx = sol.Value(routing.NextVar(idx))
            if seq:
                dist += matrix[prev][0]
                routes_out.append({"vehicle": v, "stops": seq, "load": load, "dist_m": dist})
        unserved = [s for i, s in enumerate(stops, start=1) if i not in served]
    except Exception:
        solver = "greedy_fallback"
        dfn = lambda a, b: road_km(a["lat"], a["lng"], b["lat"], b["lng"]) * 1000  # noqa: E731
        rr, unserved = _greedy(depot, stops, vehicles, dfn)
        for r in rr:
            if not r["stops"]:
                continue
            d, prev = 0.0, depot
            for s in r["stops"]:
                d += dfn(prev, s)
                prev = s
                s["cum_load_kg"] = 0
            d += dfn(prev, depot)
            routes_out.append({"vehicle": r["vehicle"], "stops": r["stops"], "load": r["load"], "dist_m": int(d)})
    result_routes = []
    for r in routes_out:
        km = r["dist_m"] / 1000
        result_routes.append({
            "vehicle_id": r["vehicle"].id, "vehicle_code": r["vehicle"].code, "capacity_kg": r["vehicle"].capacity_kg,
            "load_kg": round(r["load"], 1), "load_pct": round(100 * r["load"] / r["vehicle"].capacity_kg, 1), "distance_km": round(km, 2),
            "est_fuel_l": round(km * FUEL_L_PER_KM, 2), "stops": r["stops"], "depot": depot,
        })
    return {
        "routes": result_routes, "unserved": unserved, "solver": solver, "distance_basis": basis, "depot": depot,
        "vehicles_considered": len(vehicles), "stops_considered": len(stops),
        "fuel_assumption": f"{FUEL_L_PER_KM} L/km planning assumption (not measured)",
        "note": "Proposal only — real vehicle dispatch requires municipal approval.",
    }


def alternative_for_breakdown(db: Session, vehicle_id: int) -> dict:
    v = db.get(Vehicle, vehicle_id)
    base = plan_routes(db, ward_ids=[v.ward_id] if v else None)
    alt = plan_routes(db, ward_ids=None, unavailable_vehicle_ids=[vehicle_id])
    return {"affected_vehicle": v.code if v else None, "baseline_unserved": len(base["unserved"]), "alternative_unserved": len(alt["unserved"]), "alternative": alt}


def ward_demand_estimate(db: Session, ward: Ward, forecast_t: float | None = None) -> dict:
    pending = db.scalars(select(CollectionRequest).where(CollectionRequest.ward_id == ward.id, CollectionRequest.status.in_(["requested", "assigned", "accepted"]))).all()
    return {"ward_id": ward.id, "ward": ward.name, "pending_pickups": len(pending), "pending_kg": round(sum(p.est_weight_kg for p in pending), 1),
            "forecast_t_per_day": forecast_t}
