"""add calibration_method and dataset_version to model_versions

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-21

Additive, nullable columns — no existing row is touched, no existing
column is renamed or dropped, and downgrade() reverses this cleanly.
Backs the "store calibration_method, dataset_version" requirement (see
ml-platform/src/train.py, which now writes both into model_metadata.json,
and backend/scripts/register_model_version.py, which copies them from
there into these columns). Same "hand-written, alembic autogenerate not
runnable in this sandbox" caveat as 0001_initial_schema.py — mirror this
change into database/schema/schema.sql too (done alongside this file).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_versions", sa.Column("calibration_method", sa.String(50), nullable=True))
    op.add_column("model_versions", sa.Column("dataset_version", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("model_versions", "dataset_version")
    op.drop_column("model_versions", "calibration_method")
