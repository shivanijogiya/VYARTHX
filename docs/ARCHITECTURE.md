# VYARTHX — Architecture

```
Browser (React + Tailwind + Recharts + Leaflet)  ──HTTP/JSON──►  FastAPI (single process, port 8000)
                                                                   │  serves /api/* and the built SPA
        ┌──────────────────────────────────────────────────────────┤
        │ api/ (core, citizen, ops, circular, agents_api)            │
        │   └─ thin routers: validation, role checks, to_dict        │
        │ agents/ (LangGraph workflows + specialist agents)          │
        │   └─ runtime.py: Ctx.step = tool call in a SAVEPOINT with  │
        │      retries, AgentStep logging, approval gates            │
        │ services/ (deterministic business logic)                   │
        │   vision · rewards · passport · verification · logistics   │
        │   forecast · marketplace · events · complaints · community │
        │   circular · analytics · demo_story                        │
        │ simulation/twin.py (Digital Twin)                          │
        │ models/ (SQLAlchemy 2) · database/ (engine, seed)          │
        └──────────────────────────────────────────────────────────┘
SQLite (WAL) by default, DATABASE_URL for Postgres.  ONNX MobileNetV2 bundled in ml/models.
```

## Principles
* **Agents propose, deterministic code disposes.** Balances, mass balances, approvals and safety rules live in `services/` and never depend on an LLM.
* **Human gates.** `route_dispatch`, `marketplace_pickup`, `facility_authorisation` and serious `complaint_closure` create an `Approval`; the workflow halts (`awaiting_approval`) and resumes through `decide_approval`.
* **Append-only evidence.** Reward ledger rows are never edited (unique idempotency key); passport events are hash-chained.
* **Data honesty.** Every record carries `data_class` (official / pilot / estimate / simulated). `DEMO_MODE` ⇒ runtime records are `simulated`.
* **No integrations are faked.** No municipal systems, GPS, scales, recycler APIs or IRCTC are connected; the UI says so.

## Orchestration
`agents/graph.py` wraps LangGraph `StateGraph` (with a tiny built-in fallback if LangGraph is missing; `GRAPH_ENGINE` reports which one ran). Each workflow is a linear chain whose nodes no-op once `halt` is set (`awaiting_approval`, `escalated`, `rejected`). Every tool call is logged as an `AgentStep` (agent, tool, input, output, status, approval_status, next_agent, retries, duration).

## Optional LLM
If `ANTHROPIC_API_KEY` is set, the LLM is used only to phrase narration/assistant answers (`llm_text`). Without a key everything runs deterministically.
