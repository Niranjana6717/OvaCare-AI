"""Requires `pytest` + backend/requirements.txt — see conftest.py docstring.

Test 10 of requirement #90: administrators must only access information
permitted by their role.
"""
from __future__ import annotations


class TestAdminAccessControl:
    def test_ordinary_user_cannot_access_admin_endpoints(self, client, auth_headers):
        for path in ("/api/v1/admin/users", "/api/v1/admin/models", "/api/v1/admin/system-health", "/api/v1/admin/audit-logs"):
            response = client.get(path, headers=auth_headers)
            assert response.status_code == 403, f"{path} should be forbidden to a non-admin user"

    def test_admin_user_endpoints_never_include_health_responses(self, client, db_session, auth_headers):
        """Even for an admin, /admin/users must not leak another user's
        symptoms/assessment answers — those fields must be structurally
        absent from the response, not just unpopulated."""
        from app.database.models.user import User, UserRole

        admin_user = db_session.query(User).first()
        admin_user.role = UserRole.ADMIN
        db_session.commit()

        # Re-login to get a token carrying the new role.
        login = client.post("/api/v1/auth/login", json={"email": admin_user.email, "password": "correcthorse10"})
        admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = client.get("/api/v1/admin/users", headers=admin_headers)
        assert response.status_code == 200
        body_text = response.text.lower()
        for forbidden_field in ("raw_responses", "symptom", "probability", "explanation"):
            assert forbidden_field not in body_text
