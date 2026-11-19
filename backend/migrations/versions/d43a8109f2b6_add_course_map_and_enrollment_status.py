"""과목 연결과 수강 상태 추가"""

from alembic import op
import sqlalchemy as sa


revision = "d43a8109f2b6"
down_revision = "b291f6a704dc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_course", sa.Column("status", sa.String(20), server_default="in_progress", nullable=False))
    op.create_check_constraint("ck_user_course_status", "user_course", "status IN ('in_progress', 'completed')")
    op.create_table(
        "course_relation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_course_id", sa.Uuid(), nullable=False),
        sa.Column("target_course_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(30), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_course_id"], ["course.id"]),
        sa.ForeignKeyConstraint(["target_course_id"], ["course.id"]),
        sa.UniqueConstraint("source_course_id", "target_course_id", "relation_type", "source", name="uq_course_relation"),
        sa.CheckConstraint("source_course_id <> target_course_id", name="ck_course_relation_distinct_courses"),
    )


def downgrade() -> None:
    op.drop_table("course_relation")
    op.drop_constraint("ck_user_course_status", "user_course", type_="check")
    op.drop_column("user_course", "status")
