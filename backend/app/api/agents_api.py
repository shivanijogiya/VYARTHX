from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agents import workflows as wf
from ..agents.graph import GRAPH_ENGINE
from ..agents.runtime import WORKFLOWS, decide_approval, run_workflow
from ..config import settings
from ..core.security import current_user, require_roles
from ..database.db import SessionLocal, get_db
from ..models.models import AgentRun, AgentStep, Approval, AuditLog, User
from ..services import demo_story
from ..services.common import audit
from .util import to_dict

router = APIRouter()

AGENTS = [
    ("Orchestrator", "Routes each request to specialist agents, tracks workflow state, enforces approval gates."),
    ("Segregation Agent", "Identifies the item (image/text), explains disposal, flags hazards and asks for clarification when unsure."),
    ("Verification Agent", "Checks duplicates, plausibility, QR/weight evidence and contamination. Escalates suspicious cases."),
    ("Reward Agent", "Requests ledger entries. Balances are computed only by deterministic backend code."),
    ("Logistics Agent", "Ranks collectors/facilities and builds OR-Tools route plans. Never dispatches vehicles without approval."),
    ("Municipal Intelligence Agent", "Aggregates ward signals, forecasts, alerts and recommendations."),
    ("Citizen Reporting Agent", "Classifies citizen garbage reports, de-duplicates and prioritises."),
    ("Marketplace Matching Agent", "Scores supply/demand matches. Transfers need human approval."),
    ("Behavioural Agent", "Builds streaks, nudges and goals within each user's notification limits."),
    ("Event Planning Agent", "Plans zero-waste events and checks certificate evidence."),
    ("Compost & Processing Agent", "Routes wet waste to compost/biomethanation and estimates outputs."),
]


def _run_out(db: Session, r: AgentRun, with_steps: bool = False) -> dict:
    d = to_dict(r, exclude=("state", "input"))
    u = db.get(User, r.user_id) if r.user_id else None
    d["user"] = u.name if u else "system"
    d["step_count"] = db.scalar(select(func.count()).select_from(AgentStep).where(AgentStep.run_id == r.id)) or 0
    wd = WORKFLOWS.get(r.workflow)
    d["agents"] = wd.agents if wd else []
    d["pending_approvals"] = db.scalar(select(func.count()).select_from(Approval).where(Approval.run_id == r.id, Approval.status == "pending")) or 0
    if with_steps:
        d["input"] = r.input
        d["steps"] = [to_dict(s) for s in db.scalars(select(AgentStep).where(AgentStep.run_id == r.id).order_by(AgentStep.seq)).all()]
        d["approvals"] = [to_dict(a) for a in db.scalars(select(Approval).where(Approval.run_id == r.id)).all()]
    return d


@router.get("/agents")
def agents(user: User = Depends(current_user), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(AgentStep.agent, func.count()).group_by(AgentStep.agent)).all())
    return {"engine": GRAPH_ENGINE, "mode": "llm_assisted" if settings.llm_enabled else "deterministic", "agents": [{"name": n, "role": r, "steps_logged": counts.get(n, 0)} for n, r in AGENTS],
            "workflows": [{"name": k, "title": v.title, "agents": v.agents} for k, v in WORKFLOWS.items()],
            "guardrails": ["Agents never move real money.", "Agents never dispatch real vehicles.", "Agents never issue real benefits or declare hazardous waste safe.",
                           "Route dispatch, marketplace transfers, facility authorisation and serious complaint closure need human approval."]}


@router.get("/agents/runs")
def runs(status: str | None = None, workflow: str | None = None, limit: int = 60, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(AgentRun).order_by(AgentRun.id.desc()).limit(max(1, min(limit, 200)))
    if user.role != "municipal":
        q = q.where(AgentRun.user_id == user.id)
    if status:
        q = q.where(AgentRun.status == status)
    if workflow:
        q = q.where(AgentRun.workflow == workflow)
    return [_run_out(db, r) for r in db.scalars(q).all()]


@router.get("/agents/runs/{rid}")
def run_detail(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(AgentRun, rid)
    if not r or (user.role != "municipal" and r.user_id != user.id):
        raise HTTPException(404, "Run not found")
    return _run_out(db, r, True) | {"state": r.state if user.role == "municipal" else {k: v for k, v in (r.state or {}).items() if k in ("classification", "reward", "verification", "summary")}}


@router.get("/agents/stats")
def stats(user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    by_status = dict(db.execute(select(AgentRun.status, func.count()).group_by(AgentRun.status)).all())
    by_wf = dict(db.execute(select(AgentRun.workflow, func.count()).group_by(AgentRun.workflow)).all())
    retries = db.scalar(select(func.coalesce(func.sum(AgentStep.retries), 0))) or 0
    failed = db.scalar(select(func.count()).select_from(AgentStep).where(AgentStep.status == "failed")) or 0
    return {"runs_by_status": by_status, "runs_by_workflow": by_wf, "total_steps": db.scalar(select(func.count()).select_from(AgentStep)) or 0, "retries": int(retries), "failed_steps": failed,
            "pending_approvals": db.scalar(select(func.count()).select_from(Approval).where(Approval.status == "pending")) or 0}


@router.get("/approvals")
def approvals(status: str | None = "pending", user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Approval).order_by(Approval.id.desc()).limit(100)
    if status:
        q = q.where(Approval.status == status)
    if user.role != "municipal":
        q = q.where((Approval.requested_by == user.id) | (Approval.required_role == user.role))
    return [to_dict(a) | {"requested_by_name": (db.get(User, a.requested_by).name if a.requested_by else "agent")} for a in db.scalars(q).all()]


class DecideIn(BaseModel):
    approve: bool
    note: str = ""


@router.post("/approvals/{aid}/decide")
def decide(aid: int, body: DecideIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Approval, aid)
    if not a:
        raise HTTPException(404, "Approval not found")
    if user.role not in (a.required_role, "municipal"):
        raise HTTPException(403, f"This decision needs a '{a.required_role}' user")
    try:
        res = decide_approval(db, a, body.approve, user, body.note)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return res


@router.get("/audit")
def audit_log(limit: int = 100, user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    return [to_dict(a) for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(max(1, min(limit, 500)))).all()]


class AssistIn(BaseModel):
    message: str


@router.post("/assistant")
def assistant(body: AssistIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not body.message.strip():
        raise HTTPException(400, "Ask a question")
    res = run_workflow(db, "assistant", {"message": body.message[:500]}, user, title="Assistant")
    st = res["data"] or {}
    return {"run_id": res["run_id"], "answer": st.get("answer", res["summary"]), "intent": st.get("intent"), "actions": st.get("actions", []), "llm_phrased": st.get("llm_phrased", False)}


# ---------------------------------------------------------------- demo mode
@router.post("/demo/run-story")
def demo_story_run(quick: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not settings.DEMO_MODE:
        raise HTTPException(403, "Demo mode is disabled")
    return demo_story.run_story(db, "Guided demo", quick)


@router.post("/demo/reset")
def demo_reset(user: User = Depends(require_roles("municipal")), db: Session = Depends(get_db)):
    if not settings.DEMO_MODE:
        raise HTTPException(403, "Demo mode is disabled")
    from ..database.seed import reset_schema, seed_all, seed_activity

    audit(db, user.id, "demo:reset", "system", None)
    db.commit()
    reset_schema(db)
    out = seed_all(db)
    seed_activity(db)
    return {"reset": True, "seeded": out, "note": "Sample data restored. Please sign in again if your session is no longer valid."}
