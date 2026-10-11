# infrastructure/deployment/

This folder is a pointer, not a duplicate: the actual deployment write-up
is `docs/deployment.md` at the repo root, and it should stay the single
copy so it can't drift. It covers, honestly (what's real vs.
written-and-ready, not a fabricated "just works" guide):

- Running the stack locally with `docker compose up --build`.
- The `.env` variables that must be set before a non-development run
  (`JWT_SECRET` is enforced — the backend refuses to start in production
  without it).
- The "Environment constraints encountered" section — this project's
  original development sandbox had no general internet access (pypi,
  npm, GitHub, apt were all blocked by an egress policy) and no working
  Docker daemon, which is why: the web app and admin portal are plain
  HTML/CSS/JS instead of a bundled framework app, several backend
  dependencies (FastAPI, SQLAlchemy, pytest, XGBoost, SHAP) are correct,
  real source that was never executed there, and `docker-compose.yml` /
  `infrastructure/nginx/*.conf` were validated by syntax-checking tools
  (`docker compose config`) rather than an actual `docker compose up` or
  `nginx -t`.
- A pre-deployment checklist: migrate the database (`alembic upgrade
  head`), bootstrap an admin account (`backend/scripts/bootstrap_admin.py`
  — see `admin/dashboard/README.md`), confirm a production ML model
  artifact is present at `MODEL_PATH` (or accept that assessments will
  correctly return `insufficient_data` until one is promoted — see
  `docs/clinical_safety.md`), and confirm `feature_schema_version`
  compatibility between that artifact and the deployed backend version
  (`docs/safety_incident_response.md`'s "Incorrect model deployment"
  section — this is a manual check today, not an automated gate).

If this folder ever needs environment-specific manifests (a Kubernetes
overlay, a Terraform module, a platform-specific deploy config), they
belong here, next to this pointer — but none exist yet because none of
them has a real target to be written correctly against.
