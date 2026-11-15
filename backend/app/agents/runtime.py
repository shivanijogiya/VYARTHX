"""Agent runtime: run/step logging, retries, approval gates, optional LLM narration, workflow registry."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models.models import AgentRun, AgentStep, Approval, User, now
from ..services.common import audit
from .graph import END, GRAPH_ENGINE, START, StateGraph


class WfState(TypedDict, total=False):
    data: dict
    halt: str  # "" | "awaiting_approval" | "escalated" | "rejected"
    halt_reason: str


class Halt(Exception):
    """Raise inside a tool to stop the workflow cleanly (not an error)."""

    def __init__(self, kind: str, reason: str = ""):
        super().__init__(reason)
        self.kind, self.reason = kind, reason


def jsonable(obj: Any, limit: int = 6000) -> Any:
    try:
        s = json.dumps(obj, default=str)
        if len(s) > limit:
            return {"_truncated": True, "preview": s[:limit]}
        return json.loads(s)
    except Exception:
        return {"repr": repr(obj)[:500]}


NARRATOR_SYSTEM = "You are the VYARTHX orchestrator narrator. Summarise agent activity factually in 2-3 sentences. Never invent numbers or facts that are not in the provided data."


def llm_text(prompt: str, fallback: str, max_tokens: int = 220, system: str | None = None) -> tuple[str, bool]:
    """Optional LLM phrasing. Never used for decisions, balances, weights or disposal rules."""
    if not settings.llm_enabled:
        return fallback, False
    try:
        from app.services.llm import complete

        txt = complete(prompt, max_tokens=max_tokens, system=system or NARRATOR_SYSTEM)
        return (txt, True) if txt else (fallback, False)
    except Exception:
        return fallback, False


class Ctx:
    """Execution context shared by every node in a workflow run."""

    def __init__(self, db: Session, run: AgentRun, user: User | None):
        self.db, self.run, self.user = db, run, user
        self.seq = (db.scalar(select(AgentStep.seq).where(AgentStep.run_id == run.id).order_by(AgentStep.seq.desc()).limit(1)) or 0)

    def step(self, agent: str, task: str, fn: Callable[[], Any], tool: str = "", inp: Any = None, actor_type: str = "agent",
             approval: str = "not_required", retry: bool = True) -> Any:
        self.seq += 1
        st = AgentStep(run_id=self.run.id, seq=self.seq, agent=agent, actor_type=actor_type, task=task, tool=tool, input=jsonable(inp or {}),
                       status="running", approval_status=approval, started_at=now())
        self.db.add(st)
        self.db.commit()
        t0 = time.perf_counter()
        attempts = (settings.MAX_RETRIES + 1) if retry else 1
        last_err = ""
        for attempt in range(attempts):
            try:
                with self.db.begin_nested():
                    out = fn()
                st.output = jsonable(out if isinstance(out, (dict, list)) else {"result": out})
                st.status = "success"
                st.retries = attempt
                st.duration_ms = int((time.perf_counter() - t0) * 1000)
                if isinstance(out, dict) and out.get("_status"):
                    st.status = out["_status"]
                self.db.commit()
                return out
            except Halt as h:
                st.status = "escalated" if h.kind in ("escalated", "awaiting_approval") else "failed"
                st.output = {"halt": h.kind, "reason": h.reason}
                st.error = h.reason[:400]
                st.duration_ms = int((time.perf_counter() - t0) * 1000)
                self.db.commit()
                raise
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}: {e}"
                st.retries = attempt + 1
                st.status = "retried" if attempt + 1 < attempts else "failed"
                st.error = last_err[:400]
                self.db.commit()
                if attempt + 1 >= attempts:
                    st.duration_ms = int((time.perf_counter() - t0) * 1000)
                    self.db.commit()
                    raise
        raise RuntimeError(last_err)

    def note(self, agent: str, task: str, output: dict, actor_type: str = "orchestrator", status: str = "success", approval: str = "not_required", tool: str = "") -> None:
        self.seq += 1
        self.db.add(AgentStep(run_id=self.run.id, seq=self.seq, agent=agent, actor_type=actor_type, task=task, tool=tool, input={}, output=jsonable(output),
                              status=status, approval_status=approval, duration_ms=0, started_at=now()))
        self.db.commit()

    def request_approval(self, action: str, title: str, payload: dict, required_role: str = "municipal") -> Approval:
        a = Approval(run_id=self.run.id, action=action, title=title, payload=jsonable(payload), requested_by=self.user.id if self.user else None,
                     required_role=required_role, status="pending")
        self.db.add(a)
        self.db.flush()
        return a


@dataclass
class WorkflowDef:
    name: str
    title: str
    agents: list[str]
    build: Callable[[Ctx], Any]  # returns a compiled graph
    roles: tuple[str, ...] = ()


WORKFLOWS: dict[str, WorkflowDef] = {}
APPROVAL_HANDLERS: dict[str, Callable] = {}


def register(wd: WorkflowDef) -> None:
    WORKFLOWS[wd.name] = wd


def node(ctx: Ctx, fn: Callable[[Ctx, dict], dict | None]):
    """Wrap an agent function as a graph node. fn mutates/returns the shared data dict."""

    def _n(state: WfState) -> WfState:
        if state.get("halt"):
            return {"halt": state["halt"]}
        data = dict(state.get("data") or {})
        try:
            out = fn(ctx, data)
            return {"data": out if out is not None else data, "halt": ""}
        except Halt as h:
            return {"data": data, "halt": h.kind, "halt_reason": h.reason}

    return _n


def halted(state: WfState) -> bool:
    return bool(state.get("halt"))


def run_workflow(db: Session, name: str, payload: dict, user: User | None, title: str = "") -> dict:
    wd = WORKFLOWS[name]
    run = AgentRun(workflow=name, title=title or wd.title, status="running", user_id=user.id if user else None, input=jsonable({k: v for k, v in payload.items() if k != "image_bytes"}),
                   mode="llm_assisted" if settings.llm_enabled else "deterministic")
    db.add(run)
    db.commit()
    ctx = Ctx(db, run, user)
    reason = ""
    try:
        ctx.note("Orchestrator", f"Received request '{wd.title}'. Plan: delegate to {', '.join(wd.agents)}.",
                 {"workflow": name, "agents": wd.agents, "engine": GRAPH_ENGINE, "mode": run.mode, "requested_by": user.email if user else "system"},
                 tool="workflow_planner")
        graph = wd.build(ctx)
        final = graph.invoke({"data": dict(payload), "halt": ""})
        halt = final.get("halt") or ""
        reason = final.get("halt_reason", "")
        data = final.get("data", {})
        run.state = jsonable({k: v for k, v in data.items() if k != "image_bytes"}, 20000)
        run.status = {"": "completed", "awaiting_approval": "awaiting_approval", "escalated": "escalated", "rejected": "rejected"}.get(halt, "completed")
    except Exception as e:  # noqa: BLE001
        run.status = "failed"
        run.state = {"error": f"{type(e).__name__}: {e}"}
        reason = str(e)
        data = {}
        ctx.note("Orchestrator", "Workflow failed after retries — no partial rewards were credited outside completed steps.",
                 {"error": reason[:300]}, status="failed")
    steps = db.scalars(select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.seq)).all()
    for i, s in enumerate(steps):
        nxt = next((t.agent for t in steps[i + 1:] if t.agent != s.agent), "")
        s.next_agent = nxt
    run.summary = _summarise(run, steps, reason)
    run.finished_at = now() if run.status != "awaiting_approval" else None
    audit(db, user.id if user else None, f"workflow:{name}", "agent_run", run.id, status=run.status)
    db.commit()
    return {"run_id": run.id, "status": run.status, "summary": run.summary, "data": run.state, "reason": reason}


def _summarise(run: AgentRun, steps: list[AgentStep], reason: str) -> str:
    parts = []
    for s in steps:
        if s.agent == "Orchestrator" and s.seq == 1:
            continue
        if s.status in ("success", "escalated", "retried"):
            parts.append(f"{s.agent}: {s.task}")
    base = " → ".join(parts[:10]) or "No agent steps completed."
    if run.status == "awaiting_approval":
        base += " | Waiting for human approval."
    if run.status in ("escalated", "failed", "rejected") and reason:
        base += f" | {run.status.title()}: {reason[:160]}"
    txt, used = llm_text(f"Workflow {run.workflow}. Steps: {base}", base)
    if used:
        run.mode = "llm_assisted"
    return txt[:1500]


def decide_approval(db: Session, approval: Approval, approve: bool, user: User, note: str = "") -> dict:
    if approval.status != "pending":
        raise ValueError("Approval already decided")
    approval.status = "approved" if approve else "rejected"
    approval.decided_by, approval.decided_at, approval.decision_note = user.id, now(), note
    run = db.get(AgentRun, approval.run_id) if approval.run_id else None
    ctx = Ctx(db, run, user) if run else None
    if ctx:
        ctx.note(f"Human approver ({user.role})", f"{'Approved' if approve else 'Rejected'}: {approval.title}", {"note": note, "approval_id": approval.id},
                 actor_type="human", approval="approved" if approve else "rejected")
    handler = APPROVAL_HANDLERS.get(approval.action)
    result: dict = {}
    if handler:
        result = handler(db, ctx, approval, approve, user) or {}
    if run:
        run.status = "completed" if approve else "rejected"
        run.finished_at = now()
        steps = db.scalars(select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.seq)).all()
        for i, s in enumerate(steps):
            s.next_agent = next((t.agent for t in steps[i + 1:] if t.agent != s.agent), "")
        run.summary = (run.summary or "") + f" | Decision: {'approved' if approve else 'rejected'} by {user.name}."
    audit(db, user.id, "approval:decide", "approval", approval.id, approved=approve)
    db.commit()
    return {"approval_id": approval.id, "status": approval.status, **result}
