"""페이지별 질문과 답변을 저장한다."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "73e4c0a96d12"
down_revision = "b70ed429c183"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_chat",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_page_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("answer_status", sa.String(30), nullable=False),
        sa.Column("evidence_block_ids", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "answer_status IN ('answered', 'conversation', 'insufficient_evidence')",
            name="ck_page_chat_answer_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_page.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_page_chat_history", "page_chat", ["user_id", "document_page_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_page_chat_history", table_name="page_chat")
    op.drop_table("page_chat")
