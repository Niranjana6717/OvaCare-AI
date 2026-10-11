-- OvaCare AI — PostgreSQL schema (requirement #31)
--
-- This is the raw-SQL mirror of backend/app/database/models/*.py — the
-- SQLAlchemy models remain the source of truth (Alembic migrations are
-- generated from them; see database/migrations/versions/0001_initial.py),
-- but this file is kept in sync so the schema is reviewable without a
-- Python environment, and so it can be validated directly against a real
-- PostgreSQL server, which is how it WAS validated during development —
-- see docs/deployment.md, "Environment constraints encountered in the
-- build session": this file was actually run against a local PostgreSQL 16
-- instance with `psql`, not just written and assumed correct.
--
-- Apply with:
--   psql -h <host> -U <user> -d ovacare_db -f database/schema/schema.sql

BEGIN;

-- ---------------------------------------------------------------------
-- Enum types
-- ---------------------------------------------------------------------
CREATE TYPE user_role AS ENUM ('user', 'admin', 'clinical_reviewer');
CREATE TYPE flow_level AS ENUM ('spotting', 'light', 'medium', 'heavy');
CREATE TYPE symptom_type AS ENUM (
    'acne', 'hair_growth_changes', 'hair_loss', 'pelvic_discomfort',
    'fatigue', 'mood_changes', 'other'
);
CREATE TYPE screening_outcome AS ENUM ('lower_indication', 'higher_indication', 'insufficient_data');
CREATE TYPE notification_type AS ENUM (
    'upcoming_period', 'period_logging', 'cycle_tracking', 'symptom_logging'
);
CREATE TYPE consent_type AS ENUM (
    'core_service', 'health_data_processing', 'ai_screening_acknowledgement',
    'notification_permission', 'analytics', 'research_model_improvement'
);
CREATE TYPE model_stage AS ENUM ('development', 'validation', 'staging', 'production', 'archived');

-- ---------------------------------------------------------------------
-- users / profiles
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id                      VARCHAR(36)  PRIMARY KEY,
    email                   VARCHAR(255) NOT NULL UNIQUE,
    hashed_password         VARCHAR(255) NOT NULL,
    role                    user_role    NOT NULL DEFAULT 'user',
    is_active               BOOLEAN      NOT NULL DEFAULT TRUE,
    is_email_verified       BOOLEAN      NOT NULL DEFAULT FALSE,
    email_verification_token VARCHAR(255),
    password_reset_token    VARCHAR(255),
    password_reset_expires_at TIMESTAMPTZ,
    deleted_at              TIMESTAMPTZ,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX ix_users_email ON users (email);

CREATE TABLE profiles (
    id            VARCHAR(36) PRIMARY KEY,
    user_id       VARCHAR(36) NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name     VARCHAR(255),
    date_of_birth DATE,
    height_cm     DOUBLE PRECISION,
    weight_kg     DOUBLE PRECISION,
    country       VARCHAR(100),
    phone         VARCHAR(30),
    timezone      VARCHAR(64) NOT NULL DEFAULT 'UTC',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- cycle tracking / symptoms
-- ---------------------------------------------------------------------
CREATE TABLE cycle_records (
    id                  VARCHAR(36) PRIMARY KEY,
    user_id             VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_date          DATE NOT NULL,
    end_date            DATE,
    flow_level          flow_level,
    cycle_length_days   INTEGER,
    period_duration_days INTEGER,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_cycle_records_user_id ON cycle_records (user_id);
CREATE INDEX ix_cycle_records_user_start_date ON cycle_records (user_id, start_date);

CREATE TABLE symptoms (
    id           VARCHAR(36) PRIMARY KEY,
    user_id      VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symptom_type symptom_type NOT NULL,
    custom_label VARCHAR(120),
    severity     INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
    logged_date  DATE NOT NULL,
    notes        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_symptoms_user_id ON symptoms (user_id);

-- ---------------------------------------------------------------------
-- assessments / predictions
-- ---------------------------------------------------------------------
CREATE TABLE assessments (
    id                 VARCHAR(36) PRIMARY KEY,
    user_id            VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    raw_responses      JSONB NOT NULL,
    unanswered_fields  JSONB NOT NULL DEFAULT '[]',
    submitted_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_assessments_user_id ON assessments (user_id);

CREATE TABLE predictions (
    id                        VARCHAR(36) PRIMARY KEY,
    user_id                   VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assessment_id             VARCHAR(36) NOT NULL UNIQUE REFERENCES assessments(id) ON DELETE CASCADE,
    model_name                VARCHAR(100) NOT NULL,
    model_version             VARCHAR(50) NOT NULL,
    feature_schema_version    VARCHAR(50) NOT NULL,
    preprocessing_version     VARCHAR(50) NOT NULL,
    threshold_version         VARCHAR(50) NOT NULL,
    outcome                   screening_outcome NOT NULL,
    probability               DOUBLE PRECISION CHECK (probability IS NULL OR (probability >= 0 AND probability <= 1)),
    explanation               JSONB NOT NULL,
    insufficient_data_reason  TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Requirement #54/#63: a prediction with an actual result MUST carry a
    -- probability; one that doesn't MUST be insufficient_data. Enforced at
    -- the database layer as well as in application code.
    CONSTRAINT chk_probability_matches_outcome CHECK (
        (outcome = 'insufficient_data' AND probability IS NULL)
        OR (outcome <> 'insufficient_data' AND probability IS NOT NULL)
    )
);
CREATE INDEX ix_predictions_user_id ON predictions (user_id);

-- ---------------------------------------------------------------------
-- notifications
-- ---------------------------------------------------------------------
CREATE TABLE notification_preferences (
    id                          VARCHAR(36) PRIMARY KEY,
    user_id                     VARCHAR(36) NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    period_reminders_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    days_before_period          INTEGER NOT NULL DEFAULT 2 CHECK (days_before_period IN (1, 2, 3, 5)),
    notification_time           TIME NOT NULL DEFAULT '08:00',
    cycle_reminders_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    symptom_reminders_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
    privacy_mode                BOOLEAN NOT NULL DEFAULT TRUE,
    timezone                    VARCHAR(64) NOT NULL DEFAULT 'UTC',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notifications (
    id                VARCHAR(36) PRIMARY KEY,
    user_id           VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type notification_type NOT NULL,
    scheduled_for     TIMESTAMPTZ NOT NULL,
    full_text         TEXT NOT NULL,
    private_text      TEXT NOT NULL DEFAULT 'You have an OvaCare reminder.',
    delivery_status   VARCHAR(30) NOT NULL DEFAULT 'pending',
    delivered_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_notifications_user_id ON notifications (user_id);
CREATE INDEX ix_notifications_scheduled_for ON notifications (scheduled_for);

-- ---------------------------------------------------------------------
-- consent
-- ---------------------------------------------------------------------
CREATE TABLE consent_records (
    id              VARCHAR(36) PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    consent_type    consent_type NOT NULL,
    consent_version VARCHAR(20) NOT NULL,
    policy_version  VARCHAR(20) NOT NULL,
    app_version     VARCHAR(20) NOT NULL,
    accepted        BOOLEAN NOT NULL,
    accepted_at     TIMESTAMPTZ,
    withdrawn_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_consent_records_user_id ON consent_records (user_id);
CREATE INDEX ix_consent_records_user_type ON consent_records (user_id, consent_type, created_at);

-- ---------------------------------------------------------------------
-- ML model registry
-- ---------------------------------------------------------------------
CREATE TABLE model_versions (
    id                     VARCHAR(36) PRIMARY KEY,
    model_name             VARCHAR(100) NOT NULL,
    model_version          VARCHAR(50) NOT NULL,
    feature_schema_version VARCHAR(50) NOT NULL,
    preprocessing_version  VARCHAR(50) NOT NULL,
    threshold_version      VARCHAR(50) NOT NULL,
    stage                  model_stage NOT NULL DEFAULT 'development',
    artifact_path          VARCHAR(500) NOT NULL,
    training_date          TIMESTAMPTZ NOT NULL,
    evaluation_metrics     JSONB NOT NULL,
    dataset_reference      TEXT NOT NULL,
    dataset_version        VARCHAR(100),
    calibration_method     VARCHAR(50),
    limitations            TEXT NOT NULL,
    review_status          VARCHAR(30) NOT NULL DEFAULT 'pending_review',
    reviewed_by_role       VARCHAR(100),
    reviewed_at            TIMESTAMPTZ,
    promoted_at            TIMESTAMPTZ,
    promoted_by_user_id    VARCHAR(36),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Only one model may hold 'production' stage at a time (requirement #39:
-- never silently replace a production model — an attempt to promote a
-- second one must fail loudly, not overwrite the first).
CREATE UNIQUE INDEX ux_model_versions_single_production
    ON model_versions ((1))
    WHERE stage = 'production';

-- ---------------------------------------------------------------------
-- audit log (requirement #88 — never holds raw health data; enforced in
-- application code by app/services/audit_service.py's SENSITIVE_FIELD_DENYLIST)
-- ---------------------------------------------------------------------
CREATE TABLE audit_logs (
    id             VARCHAR(36) PRIMARY KEY,
    actor_user_id  VARCHAR(36),
    actor_role     VARCHAR(30),
    action         VARCHAR(100) NOT NULL,
    target_type    VARCHAR(100),
    target_id      VARCHAR(36),
    ip_address     VARCHAR(64),
    metadata_json  JSONB NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_logs_actor_user_id ON audit_logs (actor_user_id);
CREATE INDEX ix_audit_logs_action ON audit_logs (action);

-- ---------------------------------------------------------------------
-- revoked tokens (logout / refresh rotation)
-- ---------------------------------------------------------------------
CREATE TABLE revoked_tokens (
    jti         VARCHAR(36) PRIMARY KEY,
    revoked_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_revoked_tokens_expires_at ON revoked_tokens (expires_at);

COMMIT;
