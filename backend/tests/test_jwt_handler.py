"""
Real, executable tests for JWT creation/validation (PyJWT-backed — see
app/security/jwt_handler.py docstring for why PyJWT rather than
python-jose). Run with:

    python3 -m unittest backend.tests.test_jwt_handler -v
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["JWT_SECRET"] = "test-secret-not-for-production"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.security.jwt_handler import (  # noqa: E402
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestTokenCreationAndDecoding(unittest.TestCase):
    def test_access_token_round_trips(self):
        token = create_access_token(user_id="user-123", role="user")
        payload = decode_token(token, expected_type=TokenType.ACCESS)
        self.assertEqual(payload.sub, "user-123")
        self.assertEqual(payload.role, "user")
        self.assertEqual(payload.type, TokenType.ACCESS)

    def test_refresh_token_round_trips(self):
        token = create_refresh_token(user_id="user-456", role="admin")
        payload = decode_token(token, expected_type=TokenType.REFRESH)
        self.assertEqual(payload.sub, "user-456")
        self.assertEqual(payload.type, TokenType.REFRESH)

    def test_each_token_has_a_unique_jti(self):
        token_a = create_access_token("user-1", "user")
        token_b = create_access_token("user-1", "user")
        payload_a = decode_token(token_a, expected_type=TokenType.ACCESS)
        payload_b = decode_token(token_b, expected_type=TokenType.ACCESS)
        self.assertNotEqual(payload_a.jti, payload_b.jti)

    def test_wrong_expected_type_is_rejected(self):
        access_token = create_access_token("user-1", "user")
        with self.assertRaises(InvalidTokenError):
            decode_token(access_token, expected_type=TokenType.REFRESH)

    def test_tampered_token_is_rejected(self):
        token = create_access_token("user-1", "user")
        tampered = token[:-4] + ("aaaa" if token[-4:] != "aaaa" else "bbbb")
        with self.assertRaises(InvalidTokenError):
            decode_token(tampered)

    def test_garbage_token_is_rejected(self):
        with self.assertRaises(InvalidTokenError):
            decode_token("not.a.jwt")

    def test_wrong_secret_cannot_forge_a_token(self):
        import jwt as pyjwt

        forged = pyjwt.encode(
            {"sub": "attacker", "role": "admin", "type": "access", "jti": "x", "iat": time.time(), "exp": time.time() + 900},
            "wrong-secret",
            algorithm="HS256",
        )
        with self.assertRaises(InvalidTokenError):
            decode_token(forged)


if __name__ == "__main__":
    unittest.main()
