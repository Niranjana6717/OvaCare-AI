"""Requires `pytest` + backend/requirements.txt — see conftest.py docstring."""
from __future__ import annotations

from datetime import date, timedelta


def _log_period(client, headers, start: date, end: date):
    return client.post(
        "/api/v1/cycles",
        json={"start_date": start.isoformat(), "end_date": end.isoformat(), "flow_level": "medium"},
        headers=headers,
    )


class TestCycleCrud:
    def test_create_list_update_delete_cycle(self, client, auth_headers):
        create = _log_period(client, auth_headers, date(2026, 1, 1), date(2026, 1, 5))
        assert create.status_code == 201
        cycle_id = create.json()["id"]

        listed = client.get("/api/v1/cycles", headers=auth_headers)
        assert len(listed.json()) == 1

        updated = client.put(f"/api/v1/cycles/{cycle_id}", json={"notes": "felt tired"}, headers=auth_headers)
        assert updated.json()["notes"] == "felt tired"

        deleted = client.delete(f"/api/v1/cycles/{cycle_id}", headers=auth_headers)
        assert deleted.status_code == 204

    def test_cannot_access_another_users_cycle(self, client, auth_headers):
        create = _log_period(client, auth_headers, date(2026, 1, 1), date(2026, 1, 5))
        cycle_id = create.json()["id"]

        client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "correcthorse10"})
        other_login = client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": "correcthorse10"})
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

        response = client.get(f"/api/v1/cycles/{cycle_id}", headers=other_headers)
        assert response.status_code == 404  # not 403 — existence isn't confirmed either


class TestCycleSummaryAndEstimate:
    def test_insufficient_data_with_no_history(self, client, auth_headers):
        summary = client.get("/api/v1/cycles/summary", headers=auth_headers).json()
        assert summary["sufficient_data"] is False
        assert "more cycle history" in summary["message"]

        estimate = client.get("/api/v1/cycles/estimate", headers=auth_headers).json()
        assert estimate["sufficient_data"] is False
        assert estimate["estimated_start_date"] is None

    def test_estimate_reflects_real_average_not_28_days(self, client, auth_headers):
        # Three periods, each 34 days apart — never 28.
        _log_period(client, auth_headers, date(2026, 1, 1), date(2026, 1, 5))
        _log_period(client, auth_headers, date(2026, 2, 4), date(2026, 2, 8))
        _log_period(client, auth_headers, date(2026, 3, 10), date(2026, 3, 14))

        estimate = client.get("/api/v1/cycles/estimate", headers=auth_headers).json()
        assert estimate["sufficient_data"] is True
        assert estimate["estimated_start_date"] == "2026-04-13"  # Mar 10 + 34 days
        assert estimate["label"] == "Estimated next period"
