# VYARTHX — Implementation Report

**Status:** working, tested build. Backend 29/29 pytest tests pass; scripted API E2E and a headless-Chrome smoke test of 44 role/page combinations pass with no JS errors or failed API calls; launcher/health-check/stop verified on Linux (the `.bat` files were not executed on Windows in the build environment).

## Features
All 22 mandatory modules are implemented (see README §8). Role-based UI for citizen, worker, facility, recycler, organiser and municipal users; Demo Mode, guided demo, sample-data reset, assistant widget, data-class badges, loading/error/empty states, responsive layout.

## Agents
Orchestrator + Segregation, Verification, Reward, Logistics, Municipal Intelligence, Citizen Reporting, Marketplace Matching, Behavioural, Event Planning, Compost & Processing — 17 LangGraph workflows with state, tool invocation, structured outputs, savepoint retries, human approval gates (route dispatch, marketplace transfer, facility authorisation, serious complaint closure), audit log and a visible trace UI. Works with no API key.

## Models and what was trained
* Image: bundled MobileNetV2 ONNX (ImageNet, Apache-2.0) + hand-written mapping and knowledge base. **Not trained on waste; not validated on Indian waste images.**
* Forecast: scikit-learn GradientBoosting per ward, **trained at runtime on SIMULATED history**; holdout MAPE (~3%) is on simulated data and says nothing about real accuracy.
* Routing: OR-Tools VRP (not learned). Digital Twin: deterministic Python simulation.

## Data sources
See `docs/DATA_SOURCES.md`. No official dataset was retrieved (portals unreachable from the build environment) — recorded as "not retrieved". No data was fabricated as official.

## Simulated / not connected
Populations, ward history, facilities and capacities, dumpsites, fleet, users, activity, worker earnings, vouchers. Not connected: municipal systems, vehicle GPS, scales, recycler confirmation, IRCTC/Railways (labelled "Proposed … Simulation Only").

## Tests executed
`pytest tests/backend` (auth/roles, hazard safety, clarification, provisional≠spendable, wrong-QR escalation, idempotent credit, hash-chain, mass-balance rejection, final bonus only after facility confirmation, never "fully recycled", approval gates and role checks, complaint evidence rule, twin scenarios + attribution, forecast/landfill labelling, event certificate rule, league ordering, IRCTC simulation-only, agent retry logging, assistant without key, demo story, no legacy branding). UI: `tests/e2e/ui_smoke.py`.

## Limitations
See README §38.

## Startup
Extract ZIP → double-click `run.bat` → open http://127.0.0.1:8000 → `stop.bat` to stop.
