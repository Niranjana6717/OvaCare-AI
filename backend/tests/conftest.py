"""
Shared pytest fixtures for the FastAPI/SQLAlchemy integration suite.

NOTE ON THIS FILE'S STATUS: written to run with `pytest` against a real
FastAPI + SQLAlchemy install. In the sandbox this repository was originally
developed in, neither package could be installed (see docs/deployment.md,
"Environment constraints encountered in the build session") so this suite
has NOT been executed there. It is syntactically complete and follows the
same patterns as the tests that WERE executed (test_cycle_math.py,
test_safety_wording.py, test_red_flag_rules.py,
test_predictor_never_fabricates.py — all in this directory, all passing).
Run it with `pytest` in any environment with backend/requirements.txt
installed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402


@pytest.fixture()
def db_session():
    from app.database.database import Base
    import app.database.models  # noqa: F401 — registers all models on Base.metadata

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    from app.database.database import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def registered_user_tokens(client):
    response = client.post(
        "/api/v1/auth/register", json={"email": "patient@example.com", "password": "correcthorse10"}
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def auth_headers(registered_user_tokens):
    return {"Authorization": f"Bearer {registered_user_tokens['access_token']}"}


@pytest.fixture()
def consented_auth_headers(client, auth_headers):
    """Grants the two required consents so assessment/prediction endpoints
    are reachable in tests that aren't specifically testing consent gating."""
    for consent_type in ("core_service", "health_data_processing", "ai_screening_acknowledgement"):
        client.post(
            "/api/v1/consent",
            json={
                "consent_type": consent_type,
                "accepted": True,
                "consent_version": "1.0.0",
                "policy_version": "1.0.0",
                "app_version": "0.1.0",
            },
            headers=auth_headers,
        )
    return auth_headers
