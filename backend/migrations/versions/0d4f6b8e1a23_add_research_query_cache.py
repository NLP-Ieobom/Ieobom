"""질문 검색어별 논문 후보 캐시를 추가한다."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0d4f6b8e1a23"
down_revision = "f239289f9e5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_query_cache",
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.String(length=200), nullable=False),
        sa.Column("searched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("papers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["course.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("course_id", "query"),
    )


def downgrade() -> None:
    op.drop_table("research_query_cache")
