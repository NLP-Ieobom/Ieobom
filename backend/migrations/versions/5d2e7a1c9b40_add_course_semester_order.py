"""Store each indexed course's earliest curriculum semester for previous/next course search."""

import sqlalchemy as sa
from alembic import op

revision = "5d2e7a1c9b40"
down_revision = "c4ab0f5b3168"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("course_learning_profile", sa.Column("semester_order", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("course_learning_profile", "semester_order")
