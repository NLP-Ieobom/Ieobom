"""미완료 묶음과 연속 실패를 저장한다."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "6c30e7d14b92"
down_revision = "91c5a8e237df"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_learning", sa.Column("pending_batch", postgresql.JSONB(), nullable=True))
    op.add_column("analysis_job", sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False))
    op.add_column("analysis_job", sa.Column("first_failure_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_job", "first_failure_at")
    op.drop_column("analysis_job", "consecutive_failures")
    op.drop_column("document_learning", "pending_batch")
