# infrastructure/monitoring/

## What exists today

- `GET /health` (backend/app/main.py) — a liveness endpoint: process is up
  and can respond. It does not check the database or the ML model (that's
  `GET /api/v1/admin/system-health`, which does check both, but is
  admin-gated since it's slightly more informative than a public endpoint
  should be).
- Structured-enough access/error logs: nginx's `ovacare` log format
  (`infrastructure/nginx/nginx.conf`) and the backend's generic-error
  middleware both key on a `request_id`, so one request can be traced
  across both logs without exposing exception internals to the client
  (`docs/security.md`).
- `model_versions.evaluation_metrics` (JSON, per model version) is the
  closest thing to ML monitoring that exists — a durable record of what a
  model scored at validation time, queryable by an admin via `GET
  /admin/models`. There is no drift-detection or live-scoring-distribution
  monitor comparing production predictions back against that baseline
  over time; `docs/safety_incident_response.md`'s "Model integrity
  problems" section describes the manual query (`predictions` grouped by
  `model_version`) an operator would run by hand today.

## What's intentionally not built

A real metrics/alerting stack (Prometheus + Grafana, or a hosted APM) is
not wired in. Adding one is mechanical once there's a real deployment
target to point it at — scrape `/metrics` if a `prometheus_client`
middleware is added to `backend/app/main.py`, alert on `production_model_loaded
== false` from `/admin/system-health`, alert on a sustained 5xx rate at
the nginx layer, alert on `notifications.delivery_status='pending'`
rows aging past their `scheduled_for` time (see
`docs/safety_incident_response.md`'s "Notification failures" section) —
but standing up the actual Prometheus/Grafana containers here without a
real environment to run them against would be exactly the kind of
unearned "looks done" scaffolding this project has tried to avoid
throughout (see the root README's "What's real vs. written-and-ready"
section).
