# OvaCare AI — Architecture

## 1. System overview

```
                         OVACARE AI
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
       MOBILE              WEB               ADMIN
    (Flutter, iOS/       (static HTML/       (static HTML/
     Android — source    CSS/JS SPA)          CSS/JS SPA)
     only, see below)
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                        HTTPS / REST
                        /api/v1/...
                             │
                             ▼
                    FastAPI backend (backend/app)
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
      PostgreSQL       ML inference        Notification
      (SQLAlchemy        (app/ml/,          scheduling
       models)          in-process)         (app/services/
                                          notification_service.py)
```

One backend, one database, one auth system, one ML inference path — every
client (mobile, web, admin) talks to the same `/api/v1/` REST API.

## 2. Logical separation (requirement #3)

The product brief requires these to be kept logically separate so "one
component [doesn't] incorrectly act as another":

| Concern | Where it lives | What it must never do |
|---|---|---|
| Health tracking (cycles, symptoms) | `app/services/cycle_service.py`, `cycle_math.py`, `symptom_service.py` | Interpret data as a diagnosis |
| AI screening | `app/ml/*`, `app/services/prediction_service.py` | Run outside the versioned model contract; return a result without a model artifact present |
| Safety rules | `app/safety/*` | Be treated as equivalent to, or a substitute for, the ML model |
| Educational content | `app/services/recommendation_service.py` | Be dynamically generated; every string is static and review-tracked |
| Notifications | `app/services/notification_service.py` | Expose health content when privacy_mode is on |
| Future AI assistant | Not yet built (requirement #41) — see "Future work" below | Independently diagnose PCOS |

Two modules are deliberately **framework-agnostic** (no SQLAlchemy, no
FastAPI import) so their logic can be unit-tested directly:
`app/services/cycle_math.py` and everything under `app/safety/` and
`app/ml/`. This is not a style preference — it is what made it possible to
give this specific, safety-critical logic real, executed test coverage in
an environment where the web framework and ORM couldn't be installed (see
`docs/deployment.md`).

## 3. Request flow: AI screening

```
User answers questionnaire
        │
        ▼
POST /api/v1/assessments          (assessment_service.create_assessment)
  - stores raw_responses verbatim
  - stores which fields were explicitly skipped ("I don't have these results")
  - requires HEALTH_DATA_PROCESSING consent to be active
        │
        ▼
POST /api/v1/predictions          (assessment_service.run_safety_and_prediction)
  - requires AI_SCREENING_ACKNOWLEDGEMENT consent to be active
  - runs safety_service.check_for_red_flags() — independent of the ML path,
    never gated on it succeeding
  - runs prediction_service.generate_prediction_for_assessment()
        │                                   │
        ▼                                   ▼
  app.ml.predictor.run_prediction()    app.safety.red_flag_rules
  1. Is a model loaded? No -> insufficient_data, stop.
  2. Are all REQUIRED fields present   (independent ruleset — see
     and in the validated range? No     docs/clinical_safety.md)
     -> insufficient_data, stop.
  3. Run the real pipeline.
     probability = pipeline.predict_proba(...)
     outcome = higher/lower_indication based on decision_threshold
     explanation = SHAP or documented fallback
        │
        ▼
prediction_service.build_result_payload()
  - looks up the ONE approved string for this outcome from app.safety.wording
  - runs assert_safe_wording() as a second line of defense
  - attaches the medical disclaimer
  - returns model_version/feature_schema_version/preprocessing_version/
    threshold_version for full traceability
```

There is no fourth path that returns a guessed number — see
`backend/app/ml/predictor.py`'s docstring and
`backend/tests/test_predictor_never_fabricates.py`, which proves this
contract against a real (if synthetic-fixture-trained, for testability)
scikit-learn pipeline.

## 4. Repository layout

```
ovacare-ai/
├── apps/
│   ├── mobile/      Flutter/Dart source (structure + core screens).
│   │                Could not be compiled/run in this project's
│   │                development sandbox — no Flutter SDK, no network
│   │                access to install one. See docs/deployment.md.
│   ├── web/         Static HTML/CSS/vanilla-JS SPA. No build step —
│   │                written this way because npm's registry was not
│   │                reachable in the development sandbox either.
│   └── desktop/     Notes only — see apps/desktop/README.md.
├── backend/         FastAPI + SQLAlchemy + PostgreSQL. See docs/deployment.md
│                    for exactly what was and wasn't executable in this
│                    project's development sandbox, and backend/tests/ for
│                    what genuinely has real, passing test output.
├── ml-platform/     Data loading, cleaning, feature engineering, training,
│                    evaluation, calibration, explainability. Targets a
│                    real, cited public dataset (docs/ml_documentation.md)
│                    that could not be downloaded into the sandbox — no
│                    model is shipped as "production" as a result.
├── admin/dashboard/ Static HTML/CSS/vanilla-JS admin portal.
├── database/        Raw SQL schema — applied to and verified against a
│                    real local PostgreSQL 16 instance during development.
├── shared/          Cross-platform types/constants/API contract notes.
├── infrastructure/  nginx/docker/deployment notes.
└── docs/            This directory.
```

## 5. Future work: AI assistant (requirement #41)

Not built in this pass. The intended shape is documented here so it isn't
lost: a conversational layer that explains app features, summarizes a
user's own tracking history, and answers general educational questions —
strictly read-only against the same API a user already has access to, with
no path to call `app.ml.predictor` directly or phrase its own output as a
diagnosis. It would live at `backend/app/api/assistant.py` +
`backend/app/services/assistant_service.py`, calling the existing
`insights`/`reports` services rather than duplicating their logic.
