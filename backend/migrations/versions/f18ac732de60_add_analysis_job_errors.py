"""분석 실패 사유를 상태 조회에 제공한다."""

from alembic import op
import sqlalchemy as sa

revision = "f18ac732de60"
down_revision = "a6c14e9b820f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_job", sa.Column("error_code", sa.String(50), nullable=True))
    op.add_column("analysis_job", sa.Column("error_message", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_job", "error_message")
    op.drop_column("analysis_job", "error_code")
