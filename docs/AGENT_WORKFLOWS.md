# Agents & workflows

| Agent | Responsibility | Never does |
|---|---|---|
| Orchestrator | plans workflow, routes to agents, enforces gates | decides money, dispatch or safety |
| Segregation | image+text classification, hazard rules, clarification | declare hazardous waste safe |
| Verification | duplicates (SHA-256 + perceptual hash), timestamps, velocity, QR/weight, mass balance | auto-approve flagged cases |
| Reward | asks the ledger for provisional/verified/final credit | compute balances itself |
| Logistics | collector ranking, facility capacity, OR-Tools VRP | dispatch real vehicles |
| Municipal Intelligence | demand, alerts, recommendations | change policy |
| Citizen Reporting | classify, geo-dedupe, prioritise reports | close a complaint without evidence |
| Marketplace Matching | score supply↔demand | move material or money |
| Behavioural | streaks, nudges (rate-limited) | spam or shame users |
| Event Planning | waste/volunteer plan, certificate rules | certify on organiser-only figures |
| Compost & Processing | route wet waste, estimate compost/biogas | present estimates as measured |

Workflows: identify · waste_submission · schedule_pickup · collection_confirm · facility_receive · facility_process · complaint_report · route_plan · marketplace_match · marketplace_request · event_plan · event_report · digital_twin · behaviour_review · reuse_listing · compost_plan · assistant.

Example — `collection_confirm`: Verification (QR + weight) → Reward (verified credit, idempotent) → Waste Passport (batch + hash-chained event) → Marketplace (suggest demand) → Compost (wet routing) → Behavioural (streak/league) → Municipal (stats). If QR mismatches, the run is `escalated`, nothing is credited.

Inspect any run in the **AI Agent Centre** (`/agents?run=<id>`) or `GET /api/agents/runs/{id}`.
