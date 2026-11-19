"""create question table and rework saved_question

Revision ID: e90f71591373
Revises: 30920472128e
Create Date: 2026-11-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e90f71591373'
down_revision: Union[str, Sequence[str], None] = '30920472128e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('question',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_page_id', sa.Uuid(), nullable=False),
    sa.Column('question_type', sa.String(length=50), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('recommended_reason', sa.Text(), nullable=False),
    sa.Column('prerequisite', sa.Text(), nullable=False),
    sa.Column('learning_order', sa.Text(), nullable=False),
    sa.Column('first_activity', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_page_id'], ['document_page.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # saved_question은 이제 질문 본문을 직접 들고 있지 않는다. question_id가 있으면 저장된 상태다.
    op.drop_column('saved_question', 'document_page_id')
    op.drop_column('saved_question', 'content')
    op.add_column('saved_question', sa.Column('question_id', sa.Uuid(), nullable=False))
    op.create_foreign_key('fk_saved_question_question_id', 'saved_question', 'question', ['question_id'], ['id'])
    op.create_unique_constraint('uq_saved_question_question_id', 'saved_question', ['question_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_saved_question_question_id', 'saved_question', type_='unique')
    op.drop_constraint('fk_saved_question_question_id', 'saved_question', type_='foreignkey')
    op.drop_column('saved_question', 'question_id')
    op.add_column('saved_question', sa.Column('content', sa.Text(), nullable=False))
    op.add_column('saved_question', sa.Column('document_page_id', sa.Uuid(), nullable=False))
    op.create_foreign_key('fk_saved_question_document_page_id', 'saved_question', 'document_page', ['document_page_id'], ['id'])
    op.drop_table('question')
