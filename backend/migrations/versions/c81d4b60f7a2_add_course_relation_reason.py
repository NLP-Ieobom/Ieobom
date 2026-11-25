"""과목 연결에 추천 이유와 신뢰도를 추가한다."""

import sqlalchemy as sa
from alembic import op

revision = "c81d4b60f7a2"
down_revision = "a3f71c2e8d50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("course_relation", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("course_relation", sa.Column("confidence", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("course_relation", "confidence")
    op.drop_column("course_relation", "reason")
