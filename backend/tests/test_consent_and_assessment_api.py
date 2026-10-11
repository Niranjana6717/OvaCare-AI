"""Requires `pytest` + backend/requirements.txt — see conftest.py docstring.

Covers requirement #90 tests 3, 8 (missing data must not fabricate a
prediction; withdrawing consent stops the gated processing) at the HTTP
level — the same contract test_predictor_never_fabricates.py proves at the
pure-function level, exercised here through the actual API + consent gate.
"""
from __future__ import annotations


def _grant(client, headers, consent_type):
    return client.post(
        "/api/v1/consent",
        json={
            "consent_type": consent_type,
            "accepted": True,
            "consent_version": "1.0.0",
            "policy_version": "1.0.0",
            "app_version": "0.1.0",
        },
        headers=headers,
    )


class TestConsentGating:
    def test_assessment_blocked_without_health_data_consent(self, client, auth_headers):
        response = client.post("/api/v1/assessments", json={"responses": {"age": 25}}, headers=auth_headers)
        assert response.status_code == 403

    def test_assessment_allowed_after_consent_granted(self, client, auth_headers):
        _grant(client, auth_headers, "health_data_processing")
        response = client.post("/api/v1/assessments", json={"responses": {"age": 25}}, headers=auth_headers)
        assert response.status_code == 201

    def test_required_consent_cannot_be_withdrawn(self, client, auth_headers):
        _grant(client, auth_headers, "core_service")
        response = client.put("/api/v1/consent/core_service", headers=auth_headers)
        assert response.status_code == 400

    def test_optional_consent_can_be_withdrawn(self, client, auth_headers):
        _grant(client, auth_headers, "notification_permission")
        response = client.put("/api/v1/consent/notification_permission", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["withdrawn_at"] is not None


class TestAssessmentNeverFabricatesWithoutModel:
    def test_prediction_reports_insufficient_data_when_no_model_deployed(self, client, consented_auth_headers):
        """No production model artifact exists in the test environment (see
        docs/ml_documentation.md) — the API must say so honestly rather than
        return a fabricated number. This is test 3 of requirement #90 at
        the HTTP layer."""
        create = client.post(
            "/api/v1/assessments",
            json={
                "responses": {"age": 27, "cycle_regularity": "irregular"},
                "unanswered_fields": ["amh"],
            },
            headers=consented_auth_headers,
        )
        assert create.status_code == 201
        assessment_id = create.json()["assessment_id"]

        prediction = client.post(
            "/api/v1/predictions", json={"assessment_id": assessment_id}, headers=consented_auth_headers
        )
        assert prediction.status_code == 201
        body = prediction.json()
        assert body["result"]["outcome"] == "insufficient_data"
        assert body["result"]["probability"] is None
        assert "no validated production" in body["result"]["insufficient_data_reason"].lower()
        # And the urgent-safety check still ran independent of the ML path:
        assert "urgent" in body["safety"]

    def test_result_never_contains_diagnostic_language(self, client, consented_auth_headers):
        create = client.post(
            "/api/v1/assessments", json={"responses": {"age": 27}}, headers=consented_auth_headers
        )
        assessment_id = create.json()["assessment_id"]
        prediction = client.post(
            "/api/v1/predictions", json={"assessment_id": assessment_id}, headers=consented_auth_headers
        )
        message = prediction.json()["result"]["message"].lower()
        assert "you have pcos" not in message
        assert "you do not have pcos" not in message
