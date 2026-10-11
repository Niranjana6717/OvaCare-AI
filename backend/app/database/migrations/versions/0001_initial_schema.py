"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-21

Hand-written (alembic autogenerate was not runnable in this project's
development sandbox — see docs/deployment.md) to mirror
database/schema/schema.sql, which WAS applied to and verified against a
real local PostgreSQL 16 instance during development, including its check
constraints. Keep both files in sync if the models change.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = sa.Enum("user", "admin", "clinical_reviewer", name="user_role")
    flow_level = sa.Enum("spotting", "light", "medium", "heavy", name="flow_level")
    symptom_type = sa.Enum(
        "acne", "hair_growth_changes", "hair_loss", "pelvic_discomfort", "fatigue", "mood_changes", "other",
        name="symptom_type",
    )
    screening_outcome = sa.Enum("lower_indication", "higher_indication", "insufficient_data", name="screening_outcome")
    notification_type = sa.Enum(
        "upcoming_period", "period_logging", "cycle_tracking", "symptom_logging", name="notification_type"
    )
    consent_type = sa.Enum(
        "core_service", "health_data_processing", "ai_screening_acknowledgement",
        "notification_permission", "analytics", "research_model_improvement",
        name="consent_type",
    )
    model_stage = sa.Enum("development", "validation", "staging", "production", "archived", name="model_stage")

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_email_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("email_verification_token", sa.String(255)),
        sa.Column("password_reset_token", sa.String(255)),
        sa.Column("password_reset_expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255)),
        sa.Column("date_of_birth", sa.Date),
        sa.Column("height_cm", sa.Float),
        sa.Column("weight_kg", sa.Float),
        sa.Column("country", sa.String(100)),
        sa.Column("phone", sa.String(30)),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "cycle_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date),
        sa.Column("flow_level", flow_level),
        sa.Column("cycle_length_days", sa.Integer),
        sa.Column("period_duration_days", sa.Integer),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cycle_records_user_id", "cycle_records", ["user_id"])
    op.create_index("ix_cycle_records_user_start_date", "cycle_records", ["user_id", "start_date"])

    op.create_table(
        "symptoms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symptom_type", symptom_type, nullable=False),
        sa.Column("custom_label", sa.String(120)),
        sa.Column("severity", sa.Integer, sa.CheckConstraint("severity BETWEEN 1 AND 5"), nullable=False),
        sa.Column("logged_date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_symptoms_user_id", "symptoms", ["user_id"])

    op.create_table(
        "assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_responses", sa.JSON, nullable=False),
        sa.Column("unanswered_fields", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_assessments_user_id", "assessments", ["user_id"])

    op.create_table(
        "predictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "assessment_id", sa.String(36), sa.ForeignKey("assessments.id", ondelete="CASCADE"),
            nullable=False, unique=True,
        ),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("feature_schema_version", sa.String(50), nullable=False),
        sa.Column("preprocessing_version", sa.String(50), nullable=False),
        sa.Column("threshold_version", sa.String(50), nullable=False),
        sa.Column("outcome", screening_outcome, nullable=False),
        sa.Column("probability", sa.Float),
        sa.Column("explanation", sa.JSON, nullable=False),
        sa.Column("insufficient_data_reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(outcome = 'insufficient_data' AND probability IS NULL) OR "
            "(outcome <> 'insufficient_data' AND probability IS NOT NULL)",
            name="chk_probability_matches_outcome",
        ),
    )
    op.create_index("ix_predictions_user_id", "predictions", ["user_id"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("period_reminders_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("days_before_period", sa.Integer, sa.CheckConstraint("days_before_period IN (1,2,3,5)"), nullable=False, server_default="2"),
        sa.Column("notification_time", sa.Time, nullable=False, server_default="08:00:00"),
        sa.Column("cycle_reminders_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("symptom_reminders_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("privacy_mode", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("full_text", sa.Text, nullable=False),
        sa.Column("private_text", sa.Text, nullable=False, server_default="You have an OvaCare reminder."),
        sa.Column("delivery_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_scheduled_for", "notifications", ["scheduled_for"])

    op.create_table(
        "consent_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consent_type", consent_type, nullable=False),
        sa.Column("consent_version", sa.String(20), nullable=False),
        sa.Column("policy_version", sa.String(20), nullable=False),
        sa.Column("app_version", sa.String(20), nullable=False),
        sa.Column("accepted", sa.Boolean, nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])
    op.create_index("ix_consent_records_user_type", "consent_records", ["user_id", "consent_type", "created_at"])

    op.create_table(
        "model_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("feature_schema_version", sa.String(50), nullable=False),
        sa.Column("preprocessing_version", sa.String(50), nullable=False),
        sa.Column("threshold_version", sa.String(50), nullable=False),
        sa.Column("stage", model_stage, nullable=False, server_default="development"),
        sa.Column("artifact_path", sa.String(500), nullable=False),
        sa.Column("training_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_metrics", sa.JSON, nullable=False),
        sa.Column("dataset_reference", sa.Text, nullable=False),
        sa.Column("limitations", sa.Text, nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False, server_default="pending_review"),
        sa.Column("reviewed_by_role", sa.String(100)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("promoted_at", sa.DateTime(timezone=True)),
        sa.Column("promoted_by_user_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_model_versions_single_production "
        "ON model_versions ((1)) WHERE stage = 'production'"
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_user_id", sa.String(36)),
        sa.Column("actor_role", sa.String(30)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100)),
        sa.Column("target_id", sa.String(36)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("metadata_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(36), primary_key=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_table("revoked_tokens")
    op.drop_table("audit_logs")
    op.drop_table("model_versions")
    op.drop_table("consent_records")
    op.drop_table("notifications")
    op.drop_table("notification_preferences")
    op.drop_table("predictions")
    op.drop_table("assessments")
    op.drop_table("symptoms")
    op.drop_table("cycle_records")
    op.drop_table("profiles")
    op.drop_table("users")

    sa.Enum(name="model_stage").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="consent_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notification_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="screening_outcome").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="symptom_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="flow_level").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
