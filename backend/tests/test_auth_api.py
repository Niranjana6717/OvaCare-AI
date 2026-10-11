"""Requires `pytest` + this repo's backend/requirements.txt — see conftest.py
docstring for this suite's execution status."""
from __future__ import annotations


class TestRegistration:
    def test_register_succeeds_with_valid_password(self, client):
        response = client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "correcthorse10"})
        assert response.status_code == 201
        body = response.json()
        assert "access_token" in body and "refresh_token" in body

    def test_register_rejects_weak_password(self, client):
        response = client.post("/api/v1/auth/register", json={"email": "b@example.com", "password": "short1"})
        assert response.status_code in (400, 422)

    def test_register_rejects_duplicate_email(self, client):
        client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "correcthorse10"})
        response = client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "correcthorse10"})
        assert response.status_code == 409

    def test_password_never_returned_in_response(self, client):
        response = client.post("/api/v1/auth/register", json={"email": "c@example.com", "password": "correcthorse10"})
        assert "password" not in response.text.lower()


class TestLoginLogout:
    def test_login_with_correct_credentials(self, client):
        client.post("/api/v1/auth/register", json={"email": "login@example.com", "password": "correcthorse10"})
        response = client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "correcthorse10"})
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_with_wrong_password_fails(self, client):
        client.post("/api/v1/auth/register", json={"email": "login2@example.com", "password": "correcthorse10"})
        response = client.post("/api/v1/auth/login", json={"email": "login2@example.com", "password": "wrongpass1"})
        assert response.status_code == 401

    def test_authorized_endpoint_rejects_missing_token(self, client):
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401

    def test_logout_revokes_access_token(self, client, registered_user_tokens):
        headers = {"Authorization": f"Bearer {registered_user_tokens['access_token']}"}
        logout_response = client.post(
            "/api/v1/auth/logout", json={"refresh_token": registered_user_tokens["refresh_token"]}, headers=headers
        )
        assert logout_response.status_code == 200

        reuse_response = client.get("/api/v1/users/me", headers=headers)
        assert reuse_response.status_code == 401


class TestRefresh:
    def test_refresh_rotates_and_old_token_cannot_be_reused(self, client, registered_user_tokens):
        refresh_token = registered_user_tokens["refresh_token"]
        first = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert first.status_code == 200

        second = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert second.status_code == 401  # rotated tokens can't be replayed


class TestForgotPassword:
    def test_forgot_password_always_returns_generic_message(self, client):
        known = client.post("/api/v1/auth/forgot-password", json={"email": "unknown@example.com"})
        assert known.status_code == 200
        assert "if an account" in known.json()["message"].lower()
