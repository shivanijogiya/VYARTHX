To run VYARTHX on Windows: Extract the ZIP and double-click `run.bat`.

# VYARTHX

*India's AI-Powered City Waste Intelligence & Circular Economy Platform — Segregate better. Earn responsibly. Recover more. Waste less.*

## 1. What is VYARTHX?

VYARTHX is India's AI-powered city waste intelligence and circular-economy platform. Tagline: **Segregate better. Earn responsibly. Recover more. Waste less.** Built for the Bharat Agentic-AI Hackathon 2026, Track 3 – Waste Management. It connects citizens, waste workers, facilities, recyclers, event organisers and municipal officers through an auditable agentic workflow layer.

## 2. Quick start (Windows)

1. Extract the ZIP anywhere (avoid folders needing admin rights).
2. Double-click `run.bat`.
3. Wait for the browser to open `http://127.0.0.1:8000` (first run installs packages: a few minutes, internet needed once).
4. Click a demo account on the login page.
5. Double-click `stop.bat` to stop the server.

## 3. What `run.bat` does

Finds Python 3.10+ → creates `.venv` → installs `requirements.txt` (falls back to `requirements.lock`) → copies `.env.example` to `.env` → initialises the database and seeds sample data → registers the 17 agent workflows → checks the bundled model → starts the backend (which also serves the prebuilt frontend) → waits for `/api/health` → runs `scripts/health_check.py` → opens your browser. No Docker, no manual terminals, Node.js not required.

## 4. System requirements

Windows 10/11 (macOS/Linux work with `python scripts/launcher.py` inside a venv), 64-bit Python 3.10–3.13, ~1.5 GB free disk, internet for the first `pip install` and for map tiles. Node 18+ only if you want to rebuild the frontend.

## 5. Demo credentials

Password for all demo accounts: `Vyarthx@2026`

| Role | Email |
|---|---|
| Citizen | citizen@vyarthx.demo, citizen2@vyarthx.demo |
| Waste worker | worker@vyarthx.demo, worker2@vyarthx.demo |
| Municipal officer | municipal@vyarthx.demo |
| Facility operator | facility@vyarthx.demo, compostops@vyarthx.demo |
| Recycler / buyer | recycler@vyarthx.demo, nursery@vyarthx.demo |
| Event organiser | organiser@vyarthx.demo |

The login page also has one-click buttons (Demo Mode only).

## 6. Demo Mode, guided demo and reset

`DEMO_MODE=true` (default) labels every runtime record as *simulated* and shows a banner. **Guided Demo** (sidebar) runs the end-to-end story with real workflows and offers a click-through script. Municipal users can **Reset sample data** there; or run `python scripts/seed_database.py --reset`.

## 7. Suggested 5-minute demo

1. Citizen → AI Waste Doctor: describe `old AA battery` (hazard, never declared safe), then a clean cardboard photo → submit → schedule pickup.
2. Worker → Accept → Confirm handover with the household code (VX-HH-0001 for citizen@) and weight.
3. Citizen → Wallet: provisional → verified points; Waste Passport created.
4. Facility → receive, then record processing (mass balance must close) → final recovery bonus.
5. Municipal → Dynamic Collection → generate route plan → Approve; Digital Twin → Scenario B/E; AI Agent Centre → open the trace.

## 8. The 22 modules

Citizen Dashboard · AI Waste Doctor · GreenPoints Wallet · Waste Passport · Circular Marketplace · Worker Network · Green Neighbourhood League · Behavioural Intelligence · Compost-to-Community · E-waste & Special Care · Dynamic Collection · Zero-Waste Events · Reuse & Upcycling Exchange · Hotspot Map · Citizen Reporting · Landfill Intelligence · Municipal Command Centre · Waste Digital Twin · AI Agent Activity Centre · Analytics & Impact Reports · Reward Redemption Marketplace · (plus the platform Guided Demo and Data & Honesty panel).

## 9. Citizen Dashboard

Spendable/provisional points, streak, verified kg, CO₂e estimate, upcoming pickup (with your household ID), recent activity, passports, community rank, nudges, challenges and events.

## 10. AI Waste Doctor

Photo and/or text → item, stream (wet/dry/special/…), contamination, handling, disposal, nearest authorised destinations, local guidance. Pipeline: MobileNetV2 (ONNX) top-5 → hand-written mapping to the knowledge base + keyword match → safety rules → clarification gate (<55% confidence or conflict). Hazardous items always require authorised-channel guidance. **The image model is generic ImageNet, not waste-trained.**

## 11. GreenPoints Wallet

Hybrid, append-only ledger: **provisional** (after verified submission) → **verified** (after collector confirms QR + weight) → **final** (recovery bonus only when a facility confirms recovered kg). Only verified + final are spendable. Daily caps, idempotency keys, streak bonus. Balances come only from backend code.

## 12. Waste Passport

Each collected batch gets a hash-chained, append-only journey (household → collector → facility → recycler/residual). Mass balance: Input = Recovered + Rejects + Loss/moisture + Other; non-closing records are escalated. VYARTHX never claims 'fully recycled' unless ≥98% recovered and balanced.

## 13. Circular Marketplace

Supply and recycler demand listings, scored matches (material, quantity, distance, condition, contamination). Prices are user-entered, indicative only. Transfers create an approval — no money or material moves.

## 14. Worker Network

Mobile-friendly portal: digital ID/QR, tasks nearby, accept/decline, confirm handover (household code, weight, scale vs manual, photo), transfer to facility, transparent simulated earnings ledger, safety guidance, nearby buyers, assisted-onboarding note for workers without smartphones.

## 15. Green Neighbourhood League

Communities ranked by a **quality score** (segregation accuracy, participation, low contamination, correct handover) — not by kilograms. Weekly/monthly challenges, personal goals and rate-limited nudges.

## 16. Behavioural Intelligence

Streaks, recurring-contamination detection, weekly goals and nudges inside each user's notification limits (Behavioural Agent).

## 17. Compost-to-Community

Estimate feedstock, compost and biogas for a society/campus, find compost/biomethanation facilities with headroom. Yields are adjustable estimates.

## 18. E-waste & Special Care

Rules and item guide for batteries, CFLs, e-waste, medicines, sanitary items. Special-care pickups need trained workers and authorised facilities; VYARTHX never declares hazardous waste safe.

## 19. Dynamic Collection

Forecast + pending pickups + hotspot reports → OR-Tools VRP (capacity, priority drop penalties, haversine×1.3 or OSRM distances). 'What-if' vehicle unavailability. Plans need human approval and are *simulated* dispatch only.

## 20. Zero-Waste Events

Plan waste by stream, collection points, volunteers, suggested partners; join as volunteer/sponsor/partner/attendee; log waste; completion report. Certificates require verified (partner/facility) evidence — organiser-reported figures alone are not enough.

## 21. Reuse & Upcycling Exchange

List items to sell/donate/exchange/giveaway/repair, AI category guess, likely recipients, curated upcycling ideas.

## 22. Hotspot Map & Citizen Reporting

Leaflet/OpenStreetMap map of reports (new/verified/pending/resolved), filters, repeat-hotspot clusters. Reports are classified, geo-deduplicated and prioritised; officers must supply a note and evidence reference to resolve; serious closures need approval; citizens can confirm or reopen.

## 23. Landfill Intelligence

Residual inflow vs reported capacity, days-to-capacity estimates, diversion opportunities. Capacities are **simulated**.

## 24. Municipal Command Centre

City KPIs with data-class badges, ward table and map, trends, recommendations, pending approvals, facility utilisation.

## 25. Waste Digital Twin

Python simulation of ward collection queues and city wet/dry processing, recycler demand/stock, downtime and landfill pressure. Scenarios A–F (segregation +30%, vehicle loss, landfill 90%, festival ×1.8, facility downtime 40%, incentives 70%) plus custom sliders; baseline vs scenario, bottlenecks, affected wards, leave-one-out attribution, suggestions and visible assumptions.

## 26. AI Agent Activity Centre

Every workflow run with agent→agent handovers, tools, inputs/outputs, retries, approval gates and an audit log. Orchestrator + 10 specialist agents on LangGraph.

## 27. Analytics & Impact Reports

Facility-confirmed recovery by material, illustrative CO₂e, ward comparison, CSV download, print to PDF.

## 28. Reward Redemption Marketplace

Demo vouchers. The IRCTC item is labelled *Proposed Indian Railways / IRCTC Partnership — Simulation Only*: no integration exists and no real benefit is issued.

## 29. Agentic design

See `docs/AGENT_WORKFLOWS.md`. Retries (`AGENT_MAX_RETRIES`, default 2) run in savepoints; failures are logged and never leave partial credits. Human approval gates: route dispatch, marketplace transfer, facility authorisation, serious complaint closure.

## 30. Optional LLM key

Works fully without a paid API key (deterministic mode). Optionally set `ANTHROPIC_API_KEY` in `.env` to have an LLM phrase narration/assistant replies and, with `VYARTHX_LLM_VISION=true`, describe photos. The LLM never decides balances, approvals or safety.

## 31. Data honesty

Every figure is labelled official / pilot / estimate / simulated. See `docs/DATA_SOURCES.md` and the in-app **Data & Honesty** page. Official portals were unreachable at build time and are recorded as 'not retrieved'.

## 32. What is real vs simulated

Real: workflow logic, ledger rules, hash chains, OR-Tools routing, simulation maths, the bundled ONNX model, Chennai locality names. Simulated: populations, history, facilities, capacities, fleet, users and activity. Trained: only the sklearn forecaster, on simulated history. Not connected: municipal systems, GPS, scales, recycler APIs, IRCTC.

## 33. Configuration (.env)

`DEMO_MODE`, `PORT`, `DATABASE_URL` (Postgres optional), `ANTHROPIC_API_KEY`, `VYARTHX_LLM_MODEL`, `VYARTHX_LLM_VISION`, `OSRM_URL`, `AGENT_MAX_RETRIES`, `JWT_SECRET` (auto-generated into `data/.jwt_secret` if absent).

## 34. Project structure

```
run.bat stop.bat setup.bat
backend/app/{api,agents,services,simulation,models,database,core}
frontend/{src,dist}   (dist is prebuilt)
data/{seed,sources,datasets,uploads,runtime}
ml/{models,training,inference}
scripts/{launcher,seed_database,health_check,stop_server}.py
docs/  tests/{backend,e2e}
```

## 35. Developing

Backend: `.venv\Scripts\python -m uvicorn app.main:app --reload --app-dir backend`. Frontend: `cd frontend && npm install && npm run dev` (proxies /api to :8000); rebuild with `npm run build`. API docs at `/docs`.

## 36. Running the tests

Backend (29 tests): `.venv\Scripts\pip install -r requirements-dev.txt` then `.venv\Scripts\python -m pytest tests\backend -q`. UI smoke test (needs a running server and Chrome): `python tests\e2e\ui_smoke.py` (set `CHROME_PATH` if needed). Tests use a temporary database.

## 37. Security notes

PBKDF2 password hashes, HS256 JWT, role checks on every route, upload size/type validation (8 MB, verified by Pillow), parameterised SQL via SQLAlchemy, CORS limited to localhost. Demo passwords are public: **do not expose this build to the internet**.

## 38. Known limitations

Generic image model (no waste training or validation on Indian waste); keyword KB drives most decisions. Simulated city data and facilities; CO₂e factors are placeholders. Single-process SQLite is for demo scale. No real payments, GPS, scale or municipal integrations. English UI only (language preference stored; translations not shipped). Forecast accuracy is measured on simulated data only.

## 39. Troubleshooting

See `docs/TROUBLESHOOTING.md`. Logs: `data/runtime/server.log`.

## 40. Further documentation

`docs/ARCHITECTURE.md`, `docs/AGENT_WORKFLOWS.md`, `docs/DATABASE_SCHEMA.md`, `docs/API_DOCUMENTATION.md`, `docs/DATA_SOURCES.md`, `docs/TROUBLESHOOTING.md`, `docs/IMPLEMENTATION_REPORT.md`, `ml/models/MODEL_CARD.md`, `ml/training/README.md`.

## 41. Licences & credits

Application code © the VYARTHX team for the hackathon. Third-party: FastAPI, SQLAlchemy, LangGraph, OR-Tools, scikit-learn, onnxruntime, React, Tailwind, Recharts, Leaflet (BSD/MIT/Apache); MobileNetV2 ONNX (Apache-2.0); map tiles © OpenStreetMap contributors (ODbL).
