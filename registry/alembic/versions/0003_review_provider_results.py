"""add generic review provider results

Revision ID: 0003_review_provider_results
Revises: 0002_vt_async_polling
Create Date: 2026-07-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_review_provider_results"
down_revision: Union[str, None] = "0002_vt_async_polling"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_provider_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), server_default=sa.text("'scan'"), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("mode", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("submitted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deadline_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_poll_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('scan', 'human')", name="ck_review_provider_kind"),
        sa.CheckConstraint("mode IN ('pending', 'real', 'skipped', 'error')", name="ck_review_provider_mode"),
        sa.ForeignKeyConstraint(["version_id"], ["plugin_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "provider", name="uq_review_provider_version_provider"),
    )
    op.create_index("idx_review_provider_version", "review_provider_results", ["version_id"], unique=False)
    op.create_index(
        "idx_review_provider_provider_mode",
        "review_provider_results",
        ["provider", "mode"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO review_provider_results (
            version_id,
            provider,
            kind,
            passed,
            message,
            mode,
            external_id,
            submitted_at,
            deadline_at,
            next_poll_at,
            attempts,
            completed_at,
            created_at,
            updated_at
        )
        SELECT
            version_id,
            'virustotal',
            'scan',
            virustotal_pass,
            virustotal_msg,
            virustotal_mode,
            virustotal_analysis_id,
            virustotal_submitted_at,
            virustotal_deadline_at,
            virustotal_next_poll_at,
            virustotal_poll_attempts,
            CASE WHEN virustotal_mode IN ('real', 'skipped', 'error') THEN scanned_at ELSE NULL END,
            scanned_at,
            scanned_at
        FROM security_scans
        ON CONFLICT (version_id, provider) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO review_provider_results (
            version_id,
            provider,
            kind,
            passed,
            message,
            mode,
            completed_at,
            created_at,
            updated_at
        )
        SELECT
            version_id,
            'llm_agent',
            'scan',
            llm_agent_pass,
            llm_agent_msg,
            llm_agent_mode,
            CASE WHEN llm_agent_mode IN ('real', 'skipped', 'error') THEN scanned_at ELSE NULL END,
            scanned_at,
            scanned_at
        FROM security_scans
        ON CONFLICT (version_id, provider) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("idx_review_provider_provider_mode", table_name="review_provider_results")
    op.drop_index("idx_review_provider_version", table_name="review_provider_results")
    op.drop_table("review_provider_results")
