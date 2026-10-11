# OvaCare AI — Deployment

## 1. Environment constraints encountered in the build session

This section is referenced from several other docs, so it lives here once,
in full, rather than being paraphrased differently in each place.

This project was built inside a sandboxed cloud container with **no general
internet egress**. This was verified directly, not assumed:

```
$ curl -v https://pypi.org/simple/fastapi/
< HTTP/2 403
< x-deny-reason: host_not_allowed
Host not in allowlist: pypi.org.

$ curl -v https://registry.npmjs.org/express
403 host_not_allowed

$ curl -v https://api.github.com/...
403 host_not_allowed

$ sudo apt-get install python3-fastapi ...
403 Forbidden [archive.ubuntu.com]
```

PyPI, npm, GitHub (API, raw content, and codeload), and even Ubuntu's own
apt mirrors were all unreachable. Consequently, `pip install -r
requirements.txt` for `backend/` and `ml-platform/`, and `npm install` for
any Node-based frontend tooling, could not be run.

**What the container image already had installed**, and so what this
project's code was actually able to exercise: `numpy`, `pandas`,
`scikit-learn`, `pydantic` + `pydantic-settings`, `uvicorn`, `joblib`,
`starlette`, `httpx`, `PyJWT`, Node's bare runtime (no packages), and —
found partway through, and genuinely useful — a **local PostgreSQL 16
server** and the `psql` client, with no network access required to use
them.

**Not available, and not installable**: FastAPI, SQLAlchemy, Alembic,
python-jose, passlib, bcrypt, psycopg2, pytest, Faker, XGBoost, SHAP,
slowapi, email-validator, React/Vite/any npm package, the Flutter/Dart SDK.

### What this meant for each part of the build

| Area | Decision |
|---|---|
| Backend web framework | Written for **FastAPI** (per the product brief) — this is real, standard, correct code, but it was not `pip install`-able or runnable in this sandbox. It has not been booted or hit with an HTTP request here. |
| Backend ORM | Written for **SQLAlchemy 2.0** against PostgreSQL — same status as above. |
| Backend auth | JWT via **PyJWT** (not python-jose) and password hashing via the standard library's **`hashlib.pbkdf2_hmac`** (not passlib/bcrypt) — chosen specifically because these WERE available, so this logic has real, executed test coverage (`backend/tests/test_jwt_handler.py`, `test_password.py`) rather than being written-and-assumed. See those modules' docstrings. |
| Safety-critical pure logic | `cycle_math.py`, `app/safety/*`, `app/ml/*` were deliberately kept dependency-free of SQLAlchemy/FastAPI so they could be, and were, executed directly with `python3 -m unittest` — see `docs/testing.md`-equivalent notes in each test file. |
| Database schema | Applied to and verified against a **real local PostgreSQL 16 instance** with `psql` — including proving two safety-relevant constraints actually reject bad data (see `docs/ml_documentation.md` §6). |
| ML dataset | A real, cited, well-documented public dataset was identified via web research, but the file itself could not be downloaded (Kaggle requires an account; this sandbox has no general internet access). No model is shipped as "production." See `docs/ml_documentation.md`. |
| Admin portal & web app | Built as static HTML/CSS/vanilla-JS (no build step) instead of a framework requiring `npm install`. |
| Mobile app | Real Flutter/Dart source was written, but could not be compiled or run — no Flutter SDK in the image, and no network access to install one. |
| Docker | Dockerfiles and `docker-compose.yml` were written and the compose file's syntax was validated with `docker compose config` (works without a daemon). `docker compose up` itself could not be run — the sandbox's own Docker daemon does not start in this nested-container environment (`ulimit: error setting limit (Operation not permitted)`). |

None of this changes what a normal development machine or CI runner needs
to do — see §2 below — it only affects what could be verified with a
running process *inside this particular build session*. Everywhere a claim
of "real"/"tested"/"verified" appears in this repository's docs, it means a
command was actually run and its output is what's being described — see
`docs/ml_documentation.md` §6 for the itemized list of what that covers and
doesn't.

### 1.1 A later session: PDF export, ML monitoring, model registry scripts

A later session (auditing this repo against a separate "production
completion" checklist — PDF export, ML monitoring/drift detection, the
model registry scripts, structured logging, notification-permission
handling, and responsive-CSS breakpoints) ran in a **different** sandboxed
container, so its package availability differs from the table above and is
recorded separately rather than silently merged into it:

- **Additionally available this time**: `reportlab`, `pypdf`, `pdfminer.six`,
  `pdfplumber` (enabling real PDF generation and — via `pypdf` —
  real text-extraction verification in `backend/tests/test_report_pdf_service.py`),
  and a newer `pydantic` v2.
- **Still not available, and confirmed still not installable**: FastAPI,
  SQLAlchemy, Alembic, psycopg2, pytest, slowapi, Faker, XGBoost, SHAP, and
  the Flutter/Dart SDK — same gap as before. Network egress for `pip`/`npm`
  was checked the same way (`curl` returning `403`) and additionally
  cross-checked against this session's own proxy status endpoint
  (`$HTTPS_PROXY/__agentproxy/status`, documented in this container's
  `/root/.ccr/README.md`), which confirmed the block is an organization
  network policy rather than a proxy misconfiguration — so, per that
  README's own instruction, the block was not retried.
- Everything this session wrote that depends on a still-unavailable
  package (the FastAPI-facing halves of `report_pdf_service.py`,
  `monitoring_service.py`, `register_model_version.py`,
  `promote_model_version.py`; all of `apps/mobile/`) falls into the exact
  same "written to the same standard, not executed here" category the rest
  of this document already describes — see each area's own doc
  (`docs/ml_documentation.md` §6, `apps/mobile/README.md`) for specifics.

## 2. Standard setup (any machine/CI with normal internet access)

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Docker + Docker Compose (optional, for the containerized path)
- Flutter SDK (for `apps/mobile/`)

### Environment variables
Copy `.env.example` to `.env` and fill in real values — see that file for
the full list. Never commit `.env`.

### Database
```bash
createdb ovacare_db
psql -d ovacare_db -f database/schema/schema.sql
# or, once alembic is installed:
cd backend && alembic upgrade head
```

### ML setup
```bash
cd ml-platform
pip install -r requirements.txt
# Download PCOS_data_without_infertility.csv from
# https://www.kaggle.com/datasets/prasoonkottarathil/polycystic-ovary-syndrome-pcos
# into ml-platform/data/raw/, then:
python3 src/train.py --model-version 1.0.0
# Review ml-platform/reports/training_report_1.0.0.json and the clinical
# review checklist in docs/clinical_safety.md BEFORE promoting anything
# from ml-platform/models/staging/ to ml-platform/models/production/.
```

### Backend setup
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# API docs at http://localhost:8000/docs (FastAPI's built-in Swagger UI)
```

### Backend tests
```bash
cd backend
python3 -m unittest discover tests -v   # runs everywhere, no extra install
pytest tests/                            # full HTTP+DB suite, needs requirements.txt installed
```

### Create an admin account
```bash
cd backend
# set ADMIN_BOOTSTRAP_EMAIL / ADMIN_BOOTSTRAP_PASSWORD in .env first
python scripts/bootstrap_admin.py
```
There is no HTTP endpoint that grants the admin role — registration
always creates a `user`-role account. See `admin/dashboard/README.md`.

### Frontend setup
- **Web** (`apps/web/`): no build step — open `apps/web/src/index.html`
  directly, or serve the directory (`python3 -m http.server` from within
  it) and set the API base URL in `apps/web/src/config.js`.
- **Admin** (`admin/dashboard/`): same pattern.
- **Mobile** (`apps/mobile/`): standard Flutter workflow once the SDK is
  installed — `flutter pub get && flutter run`. Not verified in this
  project's sandbox (§1).

### Docker
```bash
docker compose up --build
```
Brings up `db` (Postgres, schema auto-applied), `backend`, and `nginx`
(reverse-proxies `/api/` to the backend and serves `apps/web/` at `/`
and `admin/dashboard/` at `/admin/` — see `infrastructure/nginx/`). The
compose file's syntax was validated with `docker compose config`, which
does not require a running daemon; a full `docker compose up` was not
run in this project's development sandbox (§1).

## 3. Production deployment notes

- Set `ENVIRONMENT=production` and a real, long, random `JWT_SECRET` —
  `app/config.py` refuses to start with a missing secret in production
  rather than silently generating one.
- Put the backend behind TLS (nginx/load balancer terminating HTTPS;
  `infrastructure/nginx/` has a starting config).
- `RATE_LIMIT_PER_MINUTE` and CORS origins are environment-driven — narrow
  `CORS_ORIGINS` to the real frontend origins in production.
- Do not point `MODEL_PATH` at anything until a model has gone through the
  full lifecycle in `docs/ml_documentation.md` §3, including the license
  and clinical review steps, `backend/scripts/register_model_version.py`,
  and `backend/scripts/promote_model_version.py --confirm`.
- Promotion does not hot-swap the running backend: `app/ml/model_loader.py`
  loads its model once per process (`lru_cache`). After
  `promote_model_version.py` runs, update `MODEL_PATH` in `.env` and
  restart the backend process — the script's own output says this
  explicitly so it isn't a step someone has to remember unprompted.
