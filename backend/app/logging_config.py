"""
Centralized structured logging.

Requirement: "Implement structured logging for: API errors, authentication
failures, model inference errors, notification errors, database errors,
background-task failures. Never log: passwords, access tokens, refresh
tokens, raw health information unnecessarily, sensitive personal
information. Use environment-configurable logging. Keep development and
production logging levels separate."

`app/middleware/error_handling.py` already covers API errors (it logs every
unhandled exception with a request id, and never returns the raw exception
to the client). This module adds the piece that was missing: a single JSON
formatter + level policy every part of the backend uses (`configure_logging`,
called once from app/main.py), and a redaction guard (`redact`) every call
site that logs a data dict runs through, so a future log call can't
accidentally leak a secret just because someone passed a convenient dict.

Deliberately has ZERO SQLAlchemy/FastAPI import — unlike most of this
backend, this module (and its redaction logic specifically) is directly
unit-testable in this sandbox without either installed; see
backend/tests/test_logging_config.py. `SENSITIVE_LOG_KEYS` below
intentionally duplicates (rather than imports)
app.services.audit_service.SENSITIVE_FIELD_DENYLIST plus a few log-specific
additions (tokens, secrets) — importing that module would pull in its
SQLAlchemy dependency and lose that testability. Keep the two lists in sync
if either changes.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional

# Mirrors app.services.audit_service.SENSITIVE_FIELD_DENYLIST (health/auth
# payload fields that must never be persisted or logged verbatim) plus keys
# that matter specifically for LOG lines: bearer tokens and secrets, which
# audit_service's list doesn't need to cover since audit metadata never
# carries them in the first place.
SENSITIVE_LOG_KEYS = frozenset(
    {
        "raw_responses",
        "symptom",
        "symptoms",
        "diagnosis",
        "probability",
        "explanation",
        "health_data",
        "password",
        "hashed_password",
        "notes",
        "access_token",
        "refresh_token",
        "token",
        "jwt",
        "secret",
        "jwt_secret",
        "authorization",
    }
)


def redact(data: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Returns a copy of `data` with any key in SENSITIVE_LOG_KEYS replaced
    by the literal string "[redacted]" — never the original value, and the
    key itself is kept (not dropped), so a reader can see THAT sensitive
    data was present without seeing what it was."""
    if not data:
        return {}
    return {key: ("[redacted]" if key.lower() in SENSITIVE_LOG_KEYS else value) for key, value in data.items()}


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line — easy to ship to any real log aggregator
    later without this codebase needing to change; nothing here assumes a
    specific backend (CloudWatch, Datadog, ...) since none is configured in
    this environment (see docs/deployment.md)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_data", None)
        if extra:
            payload["data"] = redact(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(environment: str) -> None:
    """Call once at process startup (app/main.py). Development gets INFO
    and above; anything else (staging/production) gets WARNING and above
    only — requirement: "Keep development and production logging levels
    separate." Idempotent: safe to call more than once (e.g. in tests)."""
    level = logging.INFO if environment.lower() == "development" else logging.WARNING
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
    root.setLevel(level)


def log_structured(logger: logging.Logger, level: int, message: str, **data: Any) -> None:
    """Every call site in this codebase that wants to attach structured
    data to a log line uses this (rather than logger.info()/error()
    directly with a raw `extra=`), so redaction is not opt-in — a
    developer would have to bypass this helper on purpose to log an
    unredacted dict. Pass exc_info=True from inside an `except` block to
    attach the current exception's traceback."""
    exc_info = data.pop("exc_info", False)
    logger.log(level, message, extra={"extra_data": data}, exc_info=exc_info)
