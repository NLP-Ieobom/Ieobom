"""분석 잡에 현재 단계와 페이지 진행 정보 추가"""

from alembic import op
import sqlalchemy as sa


revision = "8b7d3e29a641"
down_revision = "e90f71591373"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 잡에는 어느 단계까지 실행됐는지 기록이 없으므로 NULL로 남긴다.
    op.add_column("analysis_job", sa.Column("stage", sa.String(30), nullable=True))
    op.add_column("analysis_job", sa.Column("completed_pages", sa.Integer(), nullable=True))
    op.add_column("analysis_job", sa.Column("total_pages", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_job", "total_pages")
    op.drop_column("analysis_job", "completed_pages")
    op.drop_column("analysis_job", "stage")
