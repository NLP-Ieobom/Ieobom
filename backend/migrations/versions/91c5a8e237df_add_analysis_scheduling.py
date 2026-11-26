"""사용자와 문서의 분석 차례를 기록한다."""

import sqlalchemy as sa
from alembic import op

revision = "91c5a8e237df"
down_revision = "0d4f6b8e1a23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("extraction_last_served_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user", sa.Column("analysis_last_served_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user", sa.Column("analysis_priority_turns", sa.Integer(), server_default="0", nullable=False))
    op.add_column("analysis_job", sa.Column("last_served_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_job", "last_served_at")
    op.drop_column("user", "analysis_priority_turns")
    op.drop_column("user", "analysis_last_served_at")
    op.drop_column("user", "extraction_last_served_at")
