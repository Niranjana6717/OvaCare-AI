"""
Create-or-promote a single admin account from ADMIN_BOOTSTRAP_EMAIL /
ADMIN_BOOTSTRAP_PASSWORD (see .env.example).

This is a manual, operator-run script, deliberately NOT an HTTP endpoint —
requirement #30 treats role elevation as an operational action taken by
someone who already has infrastructure access, not a self-service action
reachable over the API. Run it once per environment after the database
schema exists:

    cd backend
    python scripts/bootstrap_admin.py

Behavior (idempotent — safe to re-run):
  - If ADMIN_BOOTSTRAP_EMAIL / ADMIN_BOOTSTRAP_PASSWORD are unset, the
    script exits with a message and does nothing (no accidental prompts,
    no fabricated default credentials).
  - If no user with that email exists, one is created directly with the
    admin role, using the project's real password hashing
    (app.security.password.hash_password — PBKDF2-HMAC-SHA256,
    600,000 iterations; see that module's docstring).
  - If a user with that email already exists, it is promoted to admin
    in place (role updated) rather than duplicated. The existing
    password is left untouched — ADMIN_BOOTSTRAP_PASSWORD is not applied
    to an already-existing account, so this script can never be used to
    silently take over an existing, unrelated account by knowing its
    email address.
  - The password itself is validated against the same
    password_meets_policy() every self-registered user's password must
    pass — no bootstrap-only exception to the password policy.

This script imports the real app.database models and app.security.password
module, so it depends on the same packages as the rest of backend/app
(SQLAlchemy, etc.) — see docs/deployment.md for why those aren't
installable in this project's original development sandbox, and why that
does not mean this code is untested: its core, dependency-free logic
(hash generation + the create-vs-promote decision) is exercised directly,
without SQLAlchemy, in backend/tests/test_bootstrap_admin_logic.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.security.password import hash_password, password_meets_policy  # noqa: E402


def decide_bootstrap_action(existing_user_row: dict | None) -> str:
    """Pure decision logic, independent of SQLAlchemy/the database.

    Returns one of "skip_no_credentials", "create", or "promote". Kept as
    a standalone function (rather than inlined in main()) specifically so
    it can be unit-tested without a database connection — see
    backend/tests/test_bootstrap_admin_logic.py.
    """
    if existing_user_row is None:
        return "create"
    return "promote"


def main() -> int:
    settings = get_settings()
    email = settings.ADMIN_BOOTSTRAP_EMAIL.strip().lower()
    password = settings.ADMIN_BOOTSTRAP_PASSWORD

    if not email or not password:
        print("ADMIN_BOOTSTRAP_EMAIL / ADMIN_BOOTSTRAP_PASSWORD not set — nothing to do.")
        return 0

    ok, reason = password_meets_policy(password)
    if not ok:
        print(f"Refusing to bootstrap: ADMIN_BOOTSTRAP_PASSWORD {reason}")
        return 1

    # Imported here (not at module scope) so `decide_bootstrap_action` and
    # the password-policy check above stay importable/testable even in an
    # environment without SQLAlchemy installed.
    from sqlalchemy import select

    from app.database.database import SessionLocal
    from app.database.models.user import User, UserRole

    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == email))
        action = decide_bootstrap_action({"id": existing.id} if existing else None)

        if action == "create":
            user = User(email=email, hashed_password=hash_password(password), role=UserRole.ADMIN, is_active=True)
            db.add(user)
            db.commit()
            print(f"Created new admin account: {email}")
        else:
            existing.role = UserRole.ADMIN
            db.commit()
            print(f"Promoted existing account to admin: {email} (password left unchanged)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
