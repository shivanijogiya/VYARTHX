# API

Interactive OpenAPI docs: **http://127.0.0.1:8000/docs**. All routes are under `/api`. Auth: `Authorization: Bearer <JWT>` from `POST /api/auth/login`.

Groups: `auth/*`, `meta`, `health`, `system/status|datasources`, `waste/classify`, `submissions`, `collections/*` (accept, reject, confirm, deliver, cancel), `passports`, `wallet`, `rewards/*`, `facility/*`, `facilities`, `workers/*`, `complaints`, `hotspots`, `logistics/*`, `vehicles`, `municipal/*`, `landfill`, `reports/*`, `simulation/*`, `marketplace/*`, `reuse/*`, `compost/*`, `special/*`, `events/*`, `league`, `challenges`, `behaviour`, `home`, `agents/*`, `approvals`, `audit`, `assistant`, `demo/run-story|reset`.

Errors are `{ "detail": "..." }` with 4xx for rule violations (e.g. 422 resolving a complaint without evidence, 409 for already-decided approvals, 403 for wrong role).
