"""PDF 페이지 수와 사용자 열람 기록 추가"""

from alembic import op
import sqlalchemy as sa


revision = "e5b208c71a94"
down_revision = "d43a8109f2b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document", sa.Column("page_count", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_document_page_count", "document", "page_count > 0")
    op.execute("""
        UPDATE document AS document
        SET page_count = job.total_pages
        FROM (
            SELECT DISTINCT ON (document_id) document_id, total_pages
            FROM analysis_job
            WHERE total_pages > 0
            ORDER BY document_id, created_at DESC, id DESC
        ) AS job
        WHERE document.id = job.document_id
    """)
    op.create_table(
        "user_document_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("last_page_number", sa.Integer(), nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "document_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"]),
        sa.CheckConstraint("last_page_number > 0", name="ck_document_progress_page_number"),
    )
    op.create_table(
        "user_page_view",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("first_viewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "document_id", "page_number"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"]),
        sa.CheckConstraint("page_number > 0", name="ck_page_view_page_number"),
    )


def downgrade() -> None:
    op.drop_table("user_page_view")
    op.drop_table("user_document_progress")
    op.drop_constraint("ck_document_page_count", "document", type_="check")
    op.drop_column("document", "page_count")
