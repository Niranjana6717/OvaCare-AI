# backend/

FastAPI + PostgreSQL + SQLAlchemy + Alembic + Pydantic v2. See
`docs/architecture.md` and `docs/api_documentation.md` for the full
design; this file is the "how to run it."

## Setup

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env   # then fill in JWT_SECRET, DATABASE_URL, etc.
```

## Database

```bash
alembic upgrade head
```

Or apply `database/schema/schema.sql` directly (what `docker-compose.yml`'s
`db` service does on first boot via `/docker-entrypoint-initdb.d`) — both
define the same schema; the migration exists for incremental changes
going forward.

## Run

```bash
uvicorn app.main:app --reload
```

API docs at `http://localhost:8000/docs` (FastAPI's generated OpenAPI UI
— the live, always-accurate version of `shared/api-contracts/openapi.yaml`).

## Create an admin account

```bash
# after setting ADMIN_BOOTSTRAP_EMAIL / ADMIN_BOOTSTRAP_PASSWORD in .env
python scripts/bootstrap_admin.py
```

See `admin/dashboard/README.md` for why this is a script and not an
endpoint.

## Test

```bash
# Dependency-free tests — run with only the standard library, no install needed:
python -m unittest discover -s tests -p "test_*.py" -v

# Full API + database integration suite (needs requirements.txt installed):
pytest tests/ -v
```

The `unittest` suite (113 tests as of this writing) covers the modules
that have zero SQLAlchemy/FastAPI imports by design — `app/safety/`,
`app/ml/`, `app/services/cycle_math.py`, `app/services/report_pdf_service.py`,
`app/services/monitoring_service.py`, `app/logging_config.py`,
`app/security/password.py` and `jwt_handler.py`, `scripts/bootstrap_admin.py`,
`scripts/register_model_version.py`, and `scripts/promote_model_version.py`'s
decision logic — plus, for the two safety-critical modules that DO import
SQLAlchemy (`notification_service.py`, `prediction_service.py`), a
static-analysis check on their source (via Python's stdlib `ast` module)
combined with a behavioral check against the dependency-free code
underneath them (see `tests/test_notification_privacy.py` and
`tests/test_prediction_version_immutability.py`). All of it was actually
run in this project's development sandbox (across two sessions — see
`docs/deployment.md` §1 for what each one had installed), neither of which
had FastAPI or SQLAlchemy. The `pytest` suite (`conftest.py`,
`test_auth_api.py`, `test_cycles_api.py`,
`test_consent_and_assessment_api.py`, `test_admin_access_api.py` — 4
files, unchanged this session) is syntactically complete and was written to
the same standard, but was not executed there — `.github/workflows/backend-tests.yml`
runs it for real on every push, since GitHub's runners have normal
internet access to install the dependencies that sandbox didn't.

## ML model

The backend loads a production model from `MODEL_PATH` at runtime
(`app/ml/model_loader.py`). If none is present, `POST /predictions`
correctly returns an `insufficient_data` outcome rather than a fabricated
prediction — this is intended fail-safe behavior, not a bug. See
`ml-platform/README.md` to train one.
