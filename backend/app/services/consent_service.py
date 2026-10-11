"""
Informed consent service (requirements #57-61).

Key invariants enforced here:
  * A new consent decision always INSERTS a new ConsentRecord row; it never
    UPDATEs a previous acceptance. History is reconstructable by querying
    all rows for a (user, consent_type) ordered by created_at.
  * Withdrawing a consent sets `withdrawn_at` on the currently-active row
    rather than deleting it — the record that consent was once given (and
    later withdrawn) must remain auditable.
  * Required consents (core service, health-data processing) cannot be
    withdrawn while the account remains active — the caller must be told to
    delete the account instead (requirement #61 explains this to the user).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.consent import ConsentRecord, ConsentType, REQUIRED_CONSENT_TYPES


class RequiredConsentWithdrawalError(Exception):
    """Raised when code attempts to withdraw a consent type that is required
    for basic account operation."""


def record_consent(
    db: Session,
    user_id: str,
    consent_type: ConsentType,
    accepted: bool,
    consent_version: str,
    policy_version: str,
    app_version: str,
) -> ConsentRecord:
    record = ConsentRecord(
        user_id=user_id,
        consent_type=consent_type,
        consent_version=consent_version,
        policy_version=policy_version,
        app_version=app_version,
        accepted=accepted,
        accepted_at=datetime.now(timezone.utc) if accepted else None,
    )
    db.add(record)
    db.flush()
    return record


def get_active_consents(db: Session, user_id: str) -> list[ConsentRecord]:
    """The latest, non-withdrawn record per consent_type."""
    stmt = (
        select(ConsentRecord)
        .where(ConsentRecord.user_id == user_id)
        .order_by(ConsentRecord.created_at.desc())
    )
    all_records = list(db.scalars(stmt).all())
    latest_by_type: dict[ConsentType, ConsentRecord] = {}
    for record in all_records:
        if record.consent_type not in latest_by_type:
            latest_by_type[record.consent_type] = record
    return [r for r in latest_by_type.values() if r.accepted and r.withdrawn_at is None]


def has_required_consents(db: Session, user_id: str) -> bool:
    active_types = {r.consent_type for r in get_active_consents(db, user_id)}
    return REQUIRED_CONSENT_TYPES.issubset(active_types)


def withdraw_consent(db: Session, user_id: str, consent_type: ConsentType) -> ConsentRecord:
    if consent_type in REQUIRED_CONSENT_TYPES:
        raise RequiredConsentWithdrawalError(
            f"{consent_type.value} is required for core account operation and "
            "cannot be withdrawn while the account is active. To stop this "
            "processing entirely, delete your account instead."
        )

    active = get_active_consents(db, user_id)
    match = next((r for r in active if r.consent_type == consent_type), None)
    if match is None:
        raise ValueError(f"No active consent of type {consent_type.value} found to withdraw.")

    match.withdrawn_at = datetime.now(timezone.utc)
    db.flush()
    return match


def is_consent_active(db: Session, user_id: str, consent_type: ConsentType) -> bool:
    return any(r.consent_type == consent_type for r in get_active_consents(db, user_id))
