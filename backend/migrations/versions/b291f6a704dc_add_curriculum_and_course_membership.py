"""커리큘럼과 과목 소속 추가"""

from alembic import op
import sqlalchemy as sa


revision = "b291f6a704dc"
down_revision = "8b7d3e29a641"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "curriculum",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution", sa.String(255), nullable=False),
        sa.Column("department", sa.String(255), nullable=False),
        sa.Column("entry_year", sa.Integer(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution", "department", "entry_year", name="uq_curriculum_identity"),
    )
    # 소속을 확인하지 않은 기존 과목을 임의의 커리큘럼에 넣지 않는다.
    op.add_column("course", sa.Column("curriculum_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_course_curriculum_id", "course", "curriculum", ["curriculum_id"], ["id"])
    op.create_index("ix_course_curriculum_id", "course", ["curriculum_id"])
    op.create_unique_constraint("uq_course_curriculum_code", "course", ["curriculum_id", "course_code"])


def downgrade() -> None:
    op.drop_constraint("uq_course_curriculum_code", "course", type_="unique")
    op.drop_index("ix_course_curriculum_id", table_name="course")
    op.drop_constraint("fk_course_curriculum_id", "course", type_="foreignkey")
    op.drop_column("course", "curriculum_id")
    op.drop_table("curriculum")
