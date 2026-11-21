"""PDF 삭제 시 개인 학습 기록을 함께 정리한다."""

from alembic import op

revision = "b70ed429c183"
down_revision = "f18ac732de60"
branch_labels = None
depends_on = None

REFERENCES = (
    ("analysis_job", "document_id", "document"),
    ("document_page", "document_id", "document"),
    ("question", "document_page_id", "document_page"),
    ("user_note", "document_page_id", "document_page"),
    ("saved_question", "question_id", "question"),
    ("user_document_progress", "document_id", "document"),
    ("user_page_view", "document_id", "document"),
)


def upgrade() -> None:
    for table, column, parent in REFERENCES:
        name = "fk_saved_question_question_id" if table == "saved_question" else f"{table}_{column}_fkey"
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, parent, [column], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    for table, column, parent in REFERENCES:
        name = "fk_saved_question_question_id" if table == "saved_question" else f"{table}_{column}_fkey"
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, parent, [column], ["id"])
