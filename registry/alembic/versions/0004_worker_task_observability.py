"""add worker task observability

Revision ID: 0004_worker_task_observability
Revises: 0003_review_provider_results
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_worker_task_observability"
down_revision: Union[str, None] = "0003_review_provider_results"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("queued_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_run_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'delayed', 'running', 'retrying', 'succeeded', 'failed', 'dead', 'cancelled')",
            name="ck_worker_tasks_status",
        ),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["version_id"], ["plugin_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_worker_tasks_status_created", "worker_tasks", ["status", "created_at"], unique=False)
    op.create_index("idx_worker_tasks_plugin_created", "worker_tasks", ["plugin_id", "created_at"], unique=False)
    op.create_index("idx_worker_tasks_version_created", "worker_tasks", ["version_id", "created_at"], unique=False)
    op.create_index("idx_worker_tasks_type_created", "worker_tasks", ["task_type", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_worker_tasks_type_created", table_name="worker_tasks")
    op.drop_index("idx_worker_tasks_version_created", table_name="worker_tasks")
    op.drop_index("idx_worker_tasks_plugin_created", table_name="worker_tasks")
    op.drop_index("idx_worker_tasks_status_created", table_name="worker_tasks")
    op.drop_table("worker_tasks")
