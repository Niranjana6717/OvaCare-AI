# OvaCare AI

A cross-platform PCOS-aware health app: menstrual cycle tracking, symptom
tracking, AI-assisted PCOS screening (explainable, non-diagnostic), and a
protected admin portal — one backend, one database, one auth system, one
ML inference path, shared by mobile, web, and admin clients.

This is not a UI mockup and not a set of disconnected screens. The
backend is a real FastAPI + PostgreSQL service with a full REST API, the
ML pipeline trains and compares real candidate models against a real
public dataset, and the clinical-safety rules (never present a screening
result as a diagnosis, never fabricate a prediction, informed consent
before health-data collection, a red-flag ruleset independent of the ML
model, full prediction traceability, ...) are implemented as executable
code with real test coverage, not just prose in a doc. See **"What's
verified vs. written-and-ready"** below for exactly which parts of that
claim were actually run and checked, and which were written to the same
standard but not executable in this project's original development
sandbox.

## Architecture

```
   MOBILE (Flutter)      WEB (static JS)      ADMIN (static JS)
          │                    │                    │
          └────────────────────┼────────────────────┘
                                │  HTTPS / REST, /api/v1/...
                                ▼
                    FastAPI backend (backend/app)
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
         PostgreSQL      ML inference       Notification
        (SQLAlchemy)    (app/ml/, in-      scheduling
                          process)         (app/services/)
```

One backend, one database, one auth system, one ML inference path —
every client talks to the same versioned `/api/v1/` REST API. Full
diagram and the logical-separation rules (frontend never contains ML
logic, ML module never touches HTTP, admin never sees health data) are
in `docs/architecture.md`.

## Repository layout

| Path | What it is |
|---|---|
| `backend/` | FastAPI + PostgreSQL + SQLAlchemy + Alembic + JWT auth. `backend/README.md` |
| `ml-platform/` | Data pipeline, model training/comparison/calibration/explainability. `ml-platform/README.md` |
| `apps/web/` | Patient-facing web app — static HTML/CSS/vanilla JS, no build step |
| `admin/dashboard/` | Admin portal — same pattern, account/system metadata only. `admin/dashboard/README.md` |
| `apps/mobile/` | Flutter/Dart source for Android, iOS. `apps/mobile/README.md` |
| `apps/desktop/` | Same Flutter codebase, desktop targets. `apps/desktop/README.md` |
| `database/` | SQL schema (applied and verified), migration/seed notes. `database/README.md` |
| `shared/` | Cross-app API contract (OpenAPI), TypeScript type reference, enum constants. `shared/README.md` |
| `infrastructure/` | nginx config, and honest notes on what monitoring/logging/deployment tooling isn't wired up yet |
| `docs/` | Architecture, ML documentation, API docs, database design, security, privacy, consent, **clinical safety**, incident response |
| `.github/workflows/` | CI: backend tests, ML tests, frontend checks, build validation |

## Quickstart

```bash
cp .env.example .env   # fill in JWT_SECRET, DATABASE_URL, etc.
docker compose up --build
```

Brings up Postgres (schema auto-applied), the backend
(`http://localhost:8000`, docs at `/docs`), and nginx on
`http://localhost:8080` (`/` → web app, `/admin/` → admin portal, `/api/`
→ backend). Then create an admin account:

```bash
cd backend && python scripts/bootstrap_admin.py   # needs ADMIN_BOOTSTRAP_EMAIL/PASSWORD in .env
```

No production ML model ships in this repo (see below) — assessments will
correctly return an `insufficient_data` screening outcome until one is
trained and promoted:

```bash
cd ml-platform && pip install -r requirements.txt
# download the real dataset (see ml-platform/README.md), then:
python src/train.py --model-version 1.0.0
```

For running each piece without Docker, see the per-directory READMEs
linked above, or `docs/deployment.md` for the full walkthrough.

## What's verified vs. written-and-ready

This project's original development sandbox had **no general internet
access** (pypi, npm, GitHub, and apt were all unreachable — verified with
`curl`, not assumed) and no working Docker daemon. That shaped what could
be *run* versus what was *written correctly but not executed there*. Both
categories are real, complete code — the difference is which ones this
session could prove with a command and its actual output. Full detail,
including the verbatim curl evidence, is in `docs/deployment.md` §1.

**Actually executed, across two build sessions, with real output:**
- **124 automated tests, all passing** — 113 in `backend/tests/` (safety
  wording guards, red-flag rules, JWT handling, password hashing, cycle
  math that never assumes a 28-day cycle, an ML predictor contract test
  that trains a real small model and proves it refuses to fabricate a
  prediction, the admin-bootstrap script's logic, notification-privacy
  wording, prediction version-traceability, PDF health-report generation
  with real text-extraction checks, ML monitoring/drift-signal logic,
  structured-logging redaction, and the model registry scripts' decision
  logic) + 11 in `ml-platform/tests/` (the training pipeline's
  preprocessing, feature engineering, and leakage guards, run end-to-end
  against a clearly labeled synthetic fixture, plus a metadata-field test
  for the newer `calibration_method`/`dataset_version` fields). See
  `docs/deployment.md` §1.1 for what changed between the two sessions'
  sandboxes.
- The full Postgres schema (`database/schema/schema.sql`), applied to a
  real local PostgreSQL 16 instance, including live proof that its two
  safety-relevant constraints actually reject bad data.
- `docker-compose.yml` and `infrastructure/nginx/*.conf`'s syntax,
  validated with `docker compose config` (works without a daemon).
- `shared/api-contracts/openapi.yaml`, parsed and checked (28 paths, 30
  schemas as of this writing — `/reports/pdf` and `/admin/monitoring`
  added in a later session) — and cross-checked field-by-field against the
  real backend Pydantic schemas, catching and fixing real mismatches in
  the process
  (see `apps/mobile/README.md` for what that surfaced).

**Written to the same standard, not executable in that sandbox — real
code, real tests included, just not run there:**
- The FastAPI/SQLAlchemy backend itself (needs `pip install
  fastapi sqlalchemy ...`) — `.github/workflows/backend-tests.yml` runs
  it, and its full `pytest` integration suite, for real on every push,
  since GitHub's runners have normal internet access.
- Training against the real PCOS dataset (needs a Kaggle download this
  sandbox couldn't reach) — see `ml-platform/README.md`. No fabricated
  "production" model is shipped as a substitute.
- `apps/mobile/` (needs the Flutter SDK) — `.github/workflows/frontend-checks.yml`
  runs `flutter analyze`/`flutter test` on it for real.
- `docker compose up` itself (needs a working Docker daemon) and
  `nginx -t` (needs the nginx binary).

**What this project will not do**, even to make a demo look more
finished: fabricate a dataset, fabricate a model or its accuracy,
hard-code a health risk score, claim clinical validation or review that
didn't happen, or silently produce a screening prediction when required
information is missing. Where a real dependency was unavailable, that
dependency is named — in this README, `docs/deployment.md`, and inline
in the affected source — rather than invented around.

## Clinical safety

This is the part of the spec with hard, non-negotiable constraints, so it
gets its own document rather than a summary here:
**`docs/clinical_safety.md`** covers every one of the ten required
safety tests (a low result never says "No PCOS," a high result never
says "You have PCOS," missing required data never produces a fabricated
prediction, historical predictions keep their original model version,
withdrawing consent actually stops the gated processing, and so on) with
its actual status — passing test, or an honestly flagged gap — not a
blanket "done."

## Testing

```bash
# Backend — dependency-free tests, run anywhere:
cd backend && python -m unittest discover -s tests -p "test_*.py" -v
# Backend — full API+DB suite, needs requirements.txt:
cd backend && pytest tests/ -v
# ML pipeline:
cd ml-platform && python -m pytest tests/ -v
# Frontend JS syntax:
find apps/web admin/dashboard -name "*.js" -exec node --check {} \;
# Mobile (needs Flutter SDK):
cd apps/mobile && flutter analyze && flutter test
```

## Documentation

`docs/architecture.md` · `docs/ml_documentation.md` ·
`docs/api_documentation.md` · `docs/database_design.md` ·
`docs/security.md` · `docs/privacy.md` · `docs/consent.md` ·
`docs/clinical_safety.md` · `docs/safety_incident_response.md` ·
`docs/deployment.md`
