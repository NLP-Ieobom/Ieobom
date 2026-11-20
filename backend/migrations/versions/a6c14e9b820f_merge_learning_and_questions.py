"""질문 생성 결과를 기존 질문 조회·저장 기능에 연결한다."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a6c14e9b820f"
down_revision = ("e5b208c71a94", "5d2e7a1c9b40")
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("evidence_block_ids", "evidence_blocks", "related_courses", "trends"):
        op.add_column("question", sa.Column(name, JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("question", sa.Column("explanation", JSONB(), nullable=True))


def downgrade() -> None:
    for name in ("explanation", "trends", "related_courses", "evidence_blocks", "evidence_block_ids"):
        op.drop_column("question", name)
