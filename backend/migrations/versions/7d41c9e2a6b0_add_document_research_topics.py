"""문서에서 재사용할 연구 주제와 논문 후보를 저장한다."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "7d41c9e2a6b0"
down_revision = "6c30e7d14b92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_learning",
        sa.Column("research_topics", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("document_learning", "research_topics")
