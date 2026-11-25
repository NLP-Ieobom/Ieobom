"""과목에 교육과정표의 학년, 학기, 영역을 추가한다."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a3f71c2e8d50"
down_revision = "73e4c0a96d12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("course", sa.Column("year_level", sa.Integer(), nullable=True))
    op.add_column("course", sa.Column("semesters", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("course", sa.Column("areas", postgresql.JSONB(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("course", "areas")
    op.drop_column("course", "semesters")
    op.drop_column("course", "year_level")
