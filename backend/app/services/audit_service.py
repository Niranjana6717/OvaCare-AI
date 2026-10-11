"""
Audit logging (requirement #88): records that an event happened, never the
sensitive health payload involved. `SENSITIVE_FIELD_DENYLIST` is checked
against every key in `metadata_json` before a row is written — a
programming mistake elsewhere in the codebase cannot leak health data into
the audit trail silently.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models.audit_log import AuditLog

SENSITIVE_FIELD_DENYLIST = {
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
}


class SensitiveDataInAuditLogError(Exception):
    pass


def log_event(
    db: Session,
    action: str,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    metadata = metadata or {}
    offending_keys = SENSITIVE_FIELD_DENYLIST.intersection(metadata.keys())
    if offending_keys:
        raise SensitiveDataInAuditLogError(
            f"Refusing to write audit log: metadata contains disallowed keys {offending_keys}."
        )

    entry = AuditLog(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=ip_address,
        metadata_json=metadata,
    )
    db.add(entry)
    db.flush()
    return entry
