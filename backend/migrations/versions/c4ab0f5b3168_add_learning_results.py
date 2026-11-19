"""Store extracted pages, generated learning content and course search data."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "c4ab0f5b3168"
down_revision = "04744a50d7ba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_learning",
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("document.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("extraction", JSONB(), nullable=False),
        sa.Column("result", JSONB(), nullable=True),
    )
    op.create_table(
        "course_learning_profile",
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("course.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("corpus_id", sa.String(255), nullable=False, unique=True),
        sa.Column("topics", JSONB(), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
    )
    op.create_table(
        "course_research_cache",
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("course.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("searched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("papers", JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("course_research_cache")
    op.drop_table("course_learning_profile")
    op.drop_table("document_learning")
