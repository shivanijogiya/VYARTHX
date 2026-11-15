# Database schema (SQLAlchemy models in `backend/app/models/models.py`)

Geography: `wards`, `ward_daily` (simulated 180-day history) · People: `users`, `households`, `workers`, `worker_payments` (simulated ledger), `communities`
Assets: `facilities`, `vehicles` · Flow: `submissions`, `collection_requests`, `batches`, `passport_events` (hash chain), `processing_records`
Rewards: `reward_transactions` (append-only, unique `idem_key`), `reward_catalog`, `redemptions`
Circular: `market_listings`, `market_matches`, `reuse_listings` · Civic: `complaints`, `challenges`, `challenge_participation`, `events`, `event_participation`, `event_waste`
Ops: `route_plans`, `simulation_runs`, `notifications`, `config_entries`
Agents: `agent_runs`, `agent_steps`, `approvals`, `audit_log`

Roles: citizen, worker, municipal, facility, recycler, organiser. Every operational table has `data_class`.
