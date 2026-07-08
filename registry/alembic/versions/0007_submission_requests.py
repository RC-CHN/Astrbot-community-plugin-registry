"""plugin submission requests

Revision ID: 0007_submission_requests
Revises: 0006_user_registration
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_submission_requests"
down_revision: Union[str, None] = "0006_user_registration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plugin_submission_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repo_url", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=50), server_default=sa.text("'github'"), nullable=False),
        sa.Column("ref_type", sa.String(length=32), server_default=sa.text("'default'"), nullable=False),
        sa.Column("ref", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'pending_review'"), nullable=False),
        sa.Column("resolved_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("accepted_plugin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_message", sa.Text(), nullable=True),
        sa.Column("admin_message", sa.Text(), nullable=True),
        sa.Column("accepted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending_review', 'accepted', 'rejected', 'duplicate')",
            name="ck_plugin_submission_requests_status",
        ),
        sa.CheckConstraint(
            "ref_type IN ('default', 'branch', 'tag', 'commit')",
            name="ck_plugin_submission_requests_ref_type",
        ),
        sa.ForeignKeyConstraint(["accepted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepted_plugin_id"], ["plugins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepted_version_id"], ["plugin_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_submission_requests_status_created", "plugin_submission_requests", ["status", "created_at"])
    op.create_index("idx_submission_requests_user_created", "plugin_submission_requests", ["user_id", "created_at"])
    op.create_index("idx_submission_requests_repo", "plugin_submission_requests", ["repo_url"])


def downgrade() -> None:
    op.drop_index("idx_submission_requests_repo", table_name="plugin_submission_requests")
    op.drop_index("idx_submission_requests_user_created", table_name="plugin_submission_requests")
    op.drop_index("idx_submission_requests_status_created", table_name="plugin_submission_requests")
    op.drop_table("plugin_submission_requests")
