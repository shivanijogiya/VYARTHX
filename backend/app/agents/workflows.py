"""Workflow graphs (LangGraph) and human-approval handlers for VYARTHX."""
from __future__ import annotations

from sqlalchemy import select

from ..models.models import (CollectionRequest, Complaint, Facility, MarketListing, MarketMatch, RoutePlan, User, Worker)
from ..services import complaints as cmp, logistics as lg, marketplace as mk
from ..services.common import notify
from . import specialists as S
from .graph import END, GRAPH_ENGINE, START, StateGraph
from .runtime import APPROVAL_HANDLERS, WORKFLOWS, Ctx, WfState, WorkflowDef, node, register, run_workflow  # noqa: F401


def _chain(ctx: Ctx, steps: list[tuple[str, callable]]):
    g = StateGraph(WfState)
    prev = START
    for name, fn in steps:
        g.add_node(name, node(ctx, fn))
        g.add_edge(prev, name)
        prev = name
    g.add_edge(prev, END)
    return g.compile()


def _reg(name, title, agents, steps, roles=()):
    register(WorkflowDef(name, title, agents, lambda ctx, _s=steps: _chain(ctx, _s), roles))


_reg("identify", "Identify waste (AI Waste Doctor)", [S.A_SEG], [("segregation", S.segregation_agent)])
_reg("waste_submission", "Record segregated waste submission", [S.A_SEG, S.A_VER, S.A_REW, S.A_LOG],
     [("segregation", S.segregation_agent), ("verification", S.verification_submission), ("reward", S.reward_provisional), ("logistics", S.logistics_options)])
_reg("schedule_pickup", "Schedule pickup", [S.A_LOG], [("logistics", S.logistics_schedule)])
_reg("collection_confirm", "Collector confirms handover → reward → passport → downstream",
     [S.A_VER, S.A_REW, S.S_PASS, S.A_MKT, S.A_CMP, S.A_BEH, S.A_MUN],
     [("verification", S.verification_collection), ("reward", S.reward_verified), ("passport", S.passport_collection), ("marketplace", S.marketplace_downstream),
      ("compost", S.compost_route), ("behaviour", S.behaviour_update), ("municipal", S.municipal_update)])
_reg("facility_receive", "Facility receives batch", [S.A_VER, S.A_LOG, S.S_PASS], [("receive", S.facility_receive)])
_reg("facility_process", "Facility records processing & recovery", [S.A_VER, S.A_CMP, S.S_PASS, S.A_REW, S.A_MKT, S.A_MUN], [("process", S.facility_process)])
_reg("complaint_report", "Citizen garbage report", [S.A_REP, S.A_VER, S.A_MUN],
     [("reporting", S.reporting_agent), ("verification", S.verification_complaint), ("municipal", S.municipal_complaint)])
_reg("route_plan", "Dynamic collection route plan (approval required)", [S.A_MUN, S.A_LOG],
     [("demand", S.municipal_demand), ("logistics", S.logistics_plan), ("approval", S.approval_gate_route)])
_reg("marketplace_match", "Marketplace matching", [S.A_MKT], [("matching", S.marketplace_recommend)])
_reg("marketplace_request", "Marketplace transfer request (approval required)", [S.A_MKT], [("request", S.marketplace_request)])
_reg("event_plan", "Zero-waste event plan", [S.A_EVT, S.A_LOG, S.A_CMP], [("planning", S.event_plan_node)])
_reg("event_report", "Post-event report & certificate decision", [S.A_EVT, S.A_MUN], [("report", S.event_report_node), ("municipal", S.municipal_event)])
_reg("digital_twin", "Digital Twin scenario", [S.A_MUN], [("twin", S.twin_node)])
_reg("behaviour_review", "Behavioural review", [S.A_BEH], [("behaviour", S.behaviour_review)])
_reg("reuse_listing", "Reuse listing matching", [S.A_MKT], [("reuse", S.reuse_node)])
_reg("compost_plan", "Compost-to-Community plan", [S.A_CMP, S.A_LOG], [("compost", S.compost_plan_node)])
_reg("assistant", "Assistant request", ["Orchestrator", S.A_SEG, S.A_REW, S.A_EVT, S.A_BEH], [("assistant", S.assistant_node)])


# ------------------------------------------------------------------ approval handlers
def _h_route(db, ctx, ap, approve, user):
    group = ap.payload.get("plan_group")
    plans = db.scalars(select(RoutePlan).where(RoutePlan.plan_group == group)).all()
    for p in plans:
        p.status = "approved_simulated" if approve else "rejected"
        p.approved_by = user.id
    if approve:
        for p in plans:
            for st in p.stops:
                if st.get("type") == "pickup":
                    c = db.get(CollectionRequest, st["id"])
                    if c and c.status == "requested" and p.vehicle_id:
                        c.notes = (c.notes + f" | Route {group} approved").strip(" |")[:290]
    if ctx:
        ctx.note(S.A_LOG, "Route plan recorded as approved (SIMULATION — no real vehicle was dispatched)" if approve else "Route plan rejected — nothing dispatched",
                 {"plan_group": group, "routes": len(plans)}, actor_type="agent", tool="route_status_update")
    return {"routes": len(plans)}


def _h_market(db, ctx, ap, approve, user):
    m = db.get(MarketMatch, ap.payload["match_id"])
    if not m:
        return {}
    if user.id != ap.payload.get("owner_user_id") and user.role != "municipal":
        raise ValueError("Only the counterparty (or a municipal admin) can decide this request")
    if not approve:
        m.status = "rejected"
        if ctx:
            ctx.note(S.A_MKT, "Request rejected by counterparty", {"match_id": m.id}, actor_type="agent")
        return {"match_status": m.status}
    m.status = "accepted"
    col = mk.create_pickup_from_match(db, m)
    sup = db.get(MarketListing, m.supply_id)
    cands = lg.rank_workers(db, col.ward_id, col.lat, col.lng, col.est_weight_kg, col.stream)
    if cands:
        col.worker_id = col.suggested_worker_id = cands[0]["worker_id"]
        col.status = "assigned"
        w = db.get(Worker, col.worker_id)
        notify(db, w.user_id, "New marketplace pickup", f"Pickup #{col.id}: {col.est_weight_kg:g} kg {col.material_key}.", "task")
    notify(db, sup.user_id, "Transfer approved", f"Your {sup.material_key} listing has an approved buyer; pickup #{col.id} created.", "pickup")
    if ctx:
        ctx.note(S.A_MKT, "Pickup request created after approval", {"collection_id": col.id, "collector": cands[0]["worker_code"] if cands else None}, actor_type="agent", tool="create_pickup")
    return {"collection_id": col.id, "match_status": m.status}


def _h_facility(db, ctx, ap, approve, user):
    f = db.get(Facility, ap.payload["facility_id"])
    if f:
        f.authorised = bool(approve)
        f.authorisation_note = f"{'Approved' if approve else 'Rejected'} in VYARTHX by {user.name} (demo — not an official authorisation)"
    return {"facility_id": f.id if f else None}


def _h_complaint(db, ctx, ap, approve, user):
    c = db.get(Complaint, ap.payload["complaint_id"])
    if c:
        if approve:
            cmp.push_history(c, "closed", user.name, "Closure approved after evidence review: " + (ap.decision_note or ""))
        else:
            cmp.push_history(c, "reopened", user.name, "Closure rejected: " + (ap.decision_note or ""))
    return {"complaint_id": c.id if c else None}


APPROVAL_HANDLERS.update({"route_dispatch": _h_route, "marketplace_pickup": _h_market, "facility_authorisation": _h_facility, "complaint_closure": _h_complaint})


# ------------------------------------------------------------------ registry shown in the Agent Activity Centre
AGENT_REGISTRY = [
    {"name": "VYARTHX Orchestrator Agent", "role": "Receives requests and system events, selects the workflow and agents, passes structured state between them, retries failures, requests human approval and writes the audit log.",
     "tools": ["workflow_planner", "intent_router", "approval_gate", "audit_log"], "approvals": "Creates approval gates; never approves its own gates."},
    {"name": S.A_SEG, "role": "Classifies waste (image + text), identifies material, four-stream category, contamination, disposal guidance, local policy retrieval, confidence-based escalation.",
     "tools": ["vision_classify (MobileNetV2-ONNX + knowledge base)", "policy_retrieve", "facility_lookup", "confidence_gate", "safety_rule"], "approvals": "Never declares hazardous waste safe; escalates to authorised handling."},
    {"name": S.A_VER, "role": "Duplicate-image detection, timestamp/QR/weight/velocity checks, collection confirmation, mass-balance checks, evidence tracking, fraud prevention.",
     "tools": ["evidence_store", "perceptual_hash_compare", "timestamp_validator", "qr_verify", "weight_rules", "mass_balance", "rule_engine"], "approvals": "Flagged items go to human review."},
    {"name": S.A_REW, "role": "Calculates provisional / verified / finalised GreenPoints and recommends credits. The deterministic ledger enforces rules — the agent cannot write balances.",
     "tools": ["reward_policy", "reward_formula", "ledger.provisional_credit", "ledger.verified_credit", "ledger.final_credit"], "approvals": "No real benefits or money are issued."},
    {"name": S.A_LOG, "role": "Collector assignment, facility matching, capacity checks, OR-Tools route planning, priority-based collection, alternative routes.",
     "tools": ["collector_match", "facility_capacity_check", "ortools.vrp", "alternative_routes", "partner_match"], "approvals": "Route dispatch requires municipal approval."},
    {"name": S.A_MUN, "role": "Forecasting, ward analytics, hotspot identification, performance analysis, landfill pressure, recommendations and digital-twin scenarios.",
     "tools": ["forecast (scikit-learn)", "analytics.platform_stats", "hotspot_analysis", "twin.simulate"], "approvals": "Recommendations only; officers decide."},
    {"name": S.A_REP, "role": "Turns photo / voice-transcript / text reports into structured complaints, detects duplicates, identifies location and recommends ward assignment.",
     "tools": ["complaint_classifier", "duplicate_detector", "geo_ward_lookup", "vision_classify"], "approvals": "Cannot close serious complaints."},
    {"name": S.A_MKT, "role": "Matches supply with recycler demand and reusable items with recipients; checks compatibility, quantity and distance; creates pickups only after approval.",
     "tools": ["material_match", "match_validator", "recipient_match", "reuse_classifier"], "approvals": "Counterparty approval before pickup creation."},
    {"name": S.A_BEH, "role": "Participation analysis, streaks, personalised nudges, challenge progress, educational tips, notification control.",
     "tools": ["behaviour_profile", "challenge_hook"], "approvals": "Respects user notification preferences and daily caps."},
    {"name": S.A_EVT, "role": "Estimates event waste, recommends collection-point placement and volunteers, matches partners, generates post-event reports and certificate decisions.",
     "tools": ["event_waste_model", "partner_match", "event_report", "certificate_rules"], "approvals": "Certificates require partner-verified evidence."},
    {"name": S.A_CMP, "role": "Organic feedstock estimation, composting / biomethanation matching, facility-capacity checks, batch tracking, compost-output estimates.",
     "tools": ["feedstock_match", "yield_estimator", "facility_capacity_check"], "approvals": "Output figures are labelled estimates."},
]
