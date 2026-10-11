# OvaCare AI — Database Design

PostgreSQL. Source of truth: `backend/app/database/models/*.py`
(SQLAlchemy). Mirrored in `database/schema/schema.sql`, which was **applied
to and verified against a real local PostgreSQL 16 instance** during
development (see `docs/deployment.md` and `docs/ml_documentation.md` §6) —
including proving that two safety-relevant constraints actually reject bad
data:

```sql
-- A prediction with a real outcome must carry a probability; one that
-- doesn't must be insufficient_data. Verified live: inserting
-- ('higher_indication', probability=NULL) is REJECTED by PostgreSQL.
ALTER TABLE predictions ADD CONSTRAINT chk_probability_matches_outcome CHECK (
    (outcome = 'insufficient_data' AND probability IS NULL)
    OR (outcome <> 'insufficient_data' AND probability IS NOT NULL)
);

-- Only one model may be 'production' at a time. Verified live: a second
-- INSERT with stage='production' is REJECTED.
CREATE UNIQUE INDEX ux_model_versions_single_production
    ON model_versions ((1)) WHERE stage = 'production';
```

## Entity overview

```
users ──1:1── profiles
  │
  ├──1:N── cycle_records
  ├──1:N── symptoms
  ├──1:N── assessments ──1:1── predictions
  ├──1:N── consent_records
  ├──1:1── notification_preferences
  ├──1:N── notifications
  └──1:N── audit_logs (actor_user_id, nullable FK-by-convention only —
                        see note below)

model_versions        (standalone registry, no user FK)
revoked_tokens         (standalone, jti + expiry)
```

`audit_logs.actor_user_id` is intentionally **not** a hard foreign key
(no `ON DELETE` behavior needed to matter) — an audit trail should still
show that *some* account performed an action even across an account
deletion; see `docs/privacy.md` for how account deletion is scoped.

## Key design decisions

- **String UUID primary keys** (`VARCHAR(36)`), generated in Python
  (`uuid.uuid4()`), not `SERIAL`/`BIGSERIAL` — avoids leaking row counts
  and keeps IDs generatable before an INSERT (useful for the
  create-then-relate patterns in `assessment_service.py`).
- **`Assessment` and `Prediction` are separate tables**, 1:1, not one
  table — see the docstring in `backend/app/database/models/assessment.py`.
  This means a later model change can never rewrite what a past
  assessment's *input* was, and a past prediction always keeps the exact
  model/feature-schema/preprocessing/threshold versions that produced it
  (requirement #76), even if the production model is later replaced.
- **`ConsentRecord` is append-only** — a new consent decision or version is
  always a new row; `consent_service.py` never `UPDATE`s a prior
  acceptance. Full history is reconstructable per (`user_id`,
  `consent_type`) ordered by `created_at`.
- **`cycle_length_days` / `period_duration_days` are derived, cached
  columns** — recomputed from the raw `start_date`/`end_date` by
  `cycle_service.recompute_derived_fields()` after every create/update/
  delete, never trusted from client input, so they can't drift from the
  source dates.
- **`AuditLog` has no `updated_at`** — audit rows are immutable by design;
  only `TimestampMixin`'s `created_at` semantics apply (see
  `backend/app/database/models/audit_log.py`, which deliberately does not
  use `TimestampMixin`).
- **JSONB columns** (`raw_responses`, `explanation`, `evaluation_metrics`,
  `metadata_json`) are used only where the shape is genuinely variable
  (questionnaire answers, a model's own metric set) — every other field is
  a real typed column, not a JSON blob, so the database itself can enforce
  the constraints above.

## Migrations

`backend/app/database/migrations/versions/0001_initial_schema.py` is a
hand-written Alembic migration mirroring `schema.sql` (Alembic itself
wasn't installable in this project's development sandbox to autogenerate
it — see `docs/deployment.md`). Keep both files in sync if the models
change; `schema.sql` is the one that's been verified against a live
database.
