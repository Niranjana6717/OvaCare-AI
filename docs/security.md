# OvaCare AI — Security

## Authentication
- JWT access tokens (short-lived, default 15 min) + refresh tokens
  (default 30 days), both carrying a unique `jti`.
- Refresh is **rotating**: each use revokes the presented refresh token and
  issues a new one — a stolen, already-used refresh token cannot be
  replayed (`backend/app/services/auth_service.refresh_access_token`).
- Logout revokes the current access token's `jti` (and the refresh token's,
  if supplied) via the `revoked_tokens` table — checked on every
  authenticated request (`app/security/dependencies.get_current_user`).
- Passwords: hashed with PBKDF2-HMAC-SHA256, 600,000 iterations, a random
  16-byte salt per password (`app/security/password.py`) — never stored or
  logged in plaintext. See that module's docstring for why PBKDF2 rather
  than bcrypt/argon2 in this specific build (a swappable choice, not a
  permanent one).
- JWT signing secret (`JWT_SECRET`) is required from the environment; the
  app **refuses to start** in production without one rather than falling
  back to a default (`app/config.py`).

## Authorization
- Role-based: `user`, `admin`, `clinical_reviewer`
  (`app/database/models/user.py:UserRole`).
- `app/security/dependencies.require_role(...)` / `require_admin` gate
  every admin endpoint. Verified by
  `backend/tests/test_admin_access_api.py`: a non-admin gets 403 on every
  `/admin/*` route, and an admin's `/admin/users` response is checked to
  structurally exclude health-data field names.
- Object-level: cycle/symptom lookups check `record.user_id == current_user.id`
  and return 404 (not 403) for a record that exists but isn't the caller's
  — avoids confirming another user's record IDs exist.

## Input validation
Every request body is a Pydantic model (`app/schemas/*.py`) with explicit
types, ranges (e.g. `severity: int = Field(ge=1, le=5)`), and cross-field
validators (e.g. a cycle's `end_date` cannot precede `start_date`).

## Rate limiting
`app/middleware/rate_limit.py` (slowapi), default 60 requests/minute per
client IP, configurable via `RATE_LIMIT_PER_MINUTE`. In-memory by default —
back it with Redis for a multi-instance deployment.

The brute-force/enumeration-sensitive auth endpoints have their own
tighter, endpoint-specific limits layered on top of that app-wide default
(`app/api/auth.py`): `POST /auth/register` at 10/minute, `POST /auth/login`
and `POST /auth/forgot-password` at 5/minute each. A failed login is also
logged as a structured `auth.login_failed` event (IP address only — never
the attempted email or password) so unusually frequent failures are
visible without waiting for the rate limit to actually trip.

## CORS
Configured from `CORS_ORIGINS` (comma-separated), not wildcarded in any
committed config.

## Secrets
Nothing sensitive is hard-coded. `.env.example` lists every variable with a
placeholder; `.env` is gitignored. `docker-compose.yml` reads `JWT_SECRET`
from the host environment with an explicitly-labeled dev-only fallback.

## Error handling
`app/middleware/error_handling.py` — unhandled exceptions return a generic
`{"detail": "Something went wrong. Please try again.", "request_id": "..."}`
and the real exception is logged server-side only, tagged with the same
`request_id` for support correlation. Validation errors and deliberately
raised HTTP errors (401/403/404/409) pass through their already-safe
message.

## Application logging
`app/logging_config.py` is the one place the app configures Python's
`logging` module (`configure_logging()`, called once from `app/main.py`
right after settings load) — every logger in the app inherits its
JSON formatter and redaction, so no call site can opt out by mistake.
`log_structured(logger, level, message, **data)` is the one intended way
application code writes a structured log line; it, and the formatter
itself, both run every field through `redact()`, which replaces the value
of any key in `SENSITIVE_LOG_KEYS` — passwords, tokens, raw questionnaire
responses, symptom/diagnosis/explanation content, emails, and similar —
with `"[REDACTED]"` before the line is ever serialized, recursing into
nested dicts/lists so a sensitive field can't hide inside a larger payload.
This list is deliberately a separate, hand-kept copy of
`audit_service.SENSITIVE_FIELD_DENYLIST` (see below) rather than an import
of it, so this module has zero SQLAlchemy dependency and can be — and is —
exercised with real, executed tests (`backend/tests/test_logging_config.py`,
9 tests) independent of the database layer; the two lists are kept in sync
by hand and a change to one should be checked against the other.

## Audit logging
`app/services/audit_service.log_event()` is the only way to write an
`AuditLog` row, and it checks every metadata key against
`SENSITIVE_FIELD_DENYLIST` (`raw_responses`, `symptom`, `diagnosis`,
`probability`, `explanation`, `password`, `notes`, ...) and **raises**
rather than writing if a caller passes one — a programming mistake
elsewhere can't leak health data into the audit trail silently. Logged
events: login, logout, registration (extend as more admin/security actions
are added).

## What's real vs. written-and-ready here
JWT creation/validation, password hashing/verification, and the structured
logging + redaction module are exercised by real, executed tests in this
sandbox (`test_jwt_handler.py`, `test_password.py`, `test_logging_config.py`
— see `docs/deployment.md`). The FastAPI-level authorization and
rate-limiting wiring (role checks, ownership checks, the `@limiter.limit`
decorators on `/auth/*`) is written and consistent with those patterns but
was not booted/hit with a live request in this sandbox — see
`docs/deployment.md` for why.
