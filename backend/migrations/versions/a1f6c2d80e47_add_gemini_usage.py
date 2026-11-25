"""Gemini 호출별 토큰 사용량을 기록한다."""

from alembic import op
import sqlalchemy as sa

revision = "a1f6c2d80e47"
down_revision = "73e4c0a96d12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gemini_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("call", sa.String(30), nullable=False),
        sa.Column("model", sa.String(60), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("thought_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("gemini_usage")
