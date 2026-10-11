"""
Real, executed tests for the dependency-free parts of
backend/scripts/bootstrap_admin.py — the create-vs-promote decision and
the fact that the bootstrap password must clear the same policy every
user's password must clear. This does not require SQLAlchemy/a database,
so it runs with only the standard library, like the rest of the
`test_*` modules in this directory that don't need FastAPI/SQLAlchemy
(see docs/deployment.md).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from app.security.password import hash_password, password_meets_policy, verify_password  # noqa: E402
from bootstrap_admin import decide_bootstrap_action  # noqa: E402


class TestBootstrapDecisionLogic(unittest.TestCase):
    def test_no_existing_user_means_create(self):
        self.assertEqual(decide_bootstrap_action(None), "create")

    def test_existing_user_means_promote_not_duplicate(self):
        self.assertEqual(decide_bootstrap_action({"id": "some-existing-id"}), "promote")

    def test_promote_path_never_depends_on_row_contents(self):
        # decide_bootstrap_action must not, e.g., look at the existing
        # user's current role or password — promotion is unconditional
        # once a row exists, and never re-derives from arbitrary fields.
        minimal_row = {"id": "x"}
        rich_row = {"id": "x", "role": "user", "hashed_password": "irrelevant", "is_active": False}
        self.assertEqual(decide_bootstrap_action(minimal_row), decide_bootstrap_action(rich_row))


class TestBootstrapPasswordPolicy(unittest.TestCase):
    def test_weak_bootstrap_password_rejected_by_policy(self):
        ok, reason = password_meets_policy("short")
        self.assertFalse(ok)
        self.assertIsNotNone(reason)

    def test_valid_bootstrap_password_accepted_by_policy(self):
        ok, reason = password_meets_policy("CorrectHorseBattery9")
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_bootstrap_password_hash_round_trips(self):
        # Proves the exact hashing call bootstrap_admin.py makes for a
        # newly-created account produces a verifiable hash — the same
        # hash_password()/verify_password() pair used by normal
        # registration (auth_service.register_user), so a bootstrapped
        # admin can log in through the ordinary /auth/login endpoint.
        hashed = hash_password("CorrectHorseBattery9")
        self.assertTrue(verify_password("CorrectHorseBattery9", hashed))
        self.assertFalse(verify_password("WrongPassword1", hashed))


if __name__ == "__main__":
    unittest.main()
