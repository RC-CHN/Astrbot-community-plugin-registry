"""add virustotal async polling metadata

Revision ID: 0002_vt_async_polling
Revises: 0001_initial
Create Date: 2026-07-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_vt_async_polling"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("security_scans", sa.Column("virustotal_analysis_id", sa.Text(), nullable=True))
    op.add_column("security_scans", sa.Column("virustotal_file_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "security_scans",
        sa.Column("virustotal_submitted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "security_scans",
        sa.Column("virustotal_deadline_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "security_scans",
        sa.Column("virustotal_next_poll_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "security_scans",
        sa.Column("virustotal_poll_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("security_scans", "virustotal_poll_attempts")
    op.drop_column("security_scans", "virustotal_next_poll_at")
    op.drop_column("security_scans", "virustotal_deadline_at")
    op.drop_column("security_scans", "virustotal_submitted_at")
    op.drop_column("security_scans", "virustotal_file_sha256")
    op.drop_column("security_scans", "virustotal_analysis_id")
