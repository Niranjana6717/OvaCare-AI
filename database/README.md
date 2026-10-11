# database/

- `schema/schema.sql` — the full DDL: 7 enum types, 12 tables, indexes,
  and two safety-relevant constraints (`chk_probability_matches_outcome`,
  `ux_model_versions_single_production`). Applied to and verified against
  a real local PostgreSQL 16 instance during development, including live
  proof that those two constraints reject bad data — see
  `docs/database_design.md` and `docs/deployment.md` §1. This is also
  what `docker-compose.yml`'s `db` service mounts as its init script.
- `migrations/` — intentionally empty. The real, versioned Alembic
  migration lives at `backend/app/database/migrations/` (next to the
  SQLAlchemy models it's generated from), not here — see
  `backend/app/database/migrations/versions/0001_initial_schema.py`.
  This directory is kept as a placeholder matching the product brief's
  originally specified repo layout, but two copies of the same migration
  history would just be a way for them to drift, so there is only one.
- `seed/` — intentionally empty. This project does not ship fabricated
  seed data (fake user accounts, fake health records, fake predictions)
  — that would cut directly against requirement #54's "NEVER fabricate a
  dataset" / "NEVER hard-code health risk scores" rules, just moved to a
  different file. To get a usable local database: apply the schema, then
  either register a real account through the API/web app, or run
  `backend/scripts/bootstrap_admin.py` for an admin account (see
  `admin/dashboard/README.md`).
