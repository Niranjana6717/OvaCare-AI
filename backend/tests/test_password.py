"""
Real, executable tests for password hashing (stdlib PBKDF2-backed — see
app/security/password.py docstring for why not passlib/bcrypt). Run with:

    python3 -m unittest backend.tests.test_password -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.security.password import hash_password, password_meets_policy, verify_password  # noqa: E402


class TestPasswordHashing(unittest.TestCase):
    def test_correct_password_verifies(self):
        hashed = hash_password("correcthorse10")
        self.assertTrue(verify_password("correcthorse10", hashed))

    def test_wrong_password_does_not_verify(self):
        hashed = hash_password("correcthorse10")
        self.assertFalse(verify_password("wrongpassword1", hashed))

    def test_plaintext_password_never_appears_in_the_hash(self):
        hashed = hash_password("correcthorse10")
        self.assertNotIn("correcthorse10", hashed)

    def test_same_password_hashed_twice_produces_different_output(self):
        """Proves a random salt is actually being used — otherwise two
        users with the same password would have identical hashes."""
        first = hash_password("correcthorse10")
        second = hash_password("correcthorse10")
        self.assertNotEqual(first, second)
        # But both still verify correctly.
        self.assertTrue(verify_password("correcthorse10", first))
        self.assertTrue(verify_password("correcthorse10", second))

    def test_malformed_hash_fails_closed_not_open(self):
        self.assertFalse(verify_password("anything", "not-a-real-hash"))
        self.assertFalse(verify_password("anything", ""))


class TestPasswordPolicy(unittest.TestCase):
    def test_rejects_short_password(self):
        ok, reason = password_meets_policy("short1")
        self.assertFalse(ok)
        self.assertIsNotNone(reason)

    def test_rejects_letters_only(self):
        ok, _ = password_meets_policy("onlylettersnodigits")
        self.assertFalse(ok)

    def test_rejects_digits_only(self):
        ok, _ = password_meets_policy("12345678901234")
        self.assertFalse(ok)

    def test_accepts_valid_password(self):
        ok, reason = password_meets_policy("correcthorse10")
        self.assertTrue(ok)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
