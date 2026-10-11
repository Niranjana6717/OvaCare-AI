# infrastructure/logging/

## What exists today

- `backend/app/middleware/error_handling.py` catches unhandled
  exceptions, logs the real exception (type, message, traceback) via
  Python's standard `logging` module server-side only, and returns a
  generic `{"detail": "Something went wrong. Please try again.",
  "request_id": "..."}` to the client — never a stack trace or raw
  exception string over the wire (requirement #47).
- `backend/app/services/audit_service.py` writes to the `audit_logs`
  table (actor, role, action, target type/id, timestamp) with a
  `SENSITIVE_FIELD_DENYLIST` check (`SensitiveDataInAuditLogError`) that
  refuses to log an event whose payload contains a denylisted field name
  (e.g. `raw_responses`, `symptom_notes`) rather than logging it and
  hoping no one asks for the field back out. This is application-level
  logging into Postgres, not file/stdout logging.
- nginx's access log (`infrastructure/nginx/nginx.conf`) carries the
  same correlation id concept via `request_time`/status, so a slow or
  failing request can be found in both places.

## What's not wired

No centralized log shipping (to something like an ELK stack, Loki, or a
hosted log service) is configured — in this project's current form,
backend process logs go to stdout (picked up by `docker logs` /
whatever container runtime is in use) and nginx logs go to its own log
files inside that container. Wiring a shipper is an operational config
change (a sidecar or a `docker-compose` logging driver), not an
application code change, so it's left for whoever picks an actual log
destination for a real deployment rather than guessed at here.

Nothing in this project's logging paths is permitted to place raw health
data (cycle records, symptoms, assessment responses, prediction
explanations) into a generic log line — see `docs/security.md` for the
full policy this and `audit_service.py` both implement.
