"""create document_page and user_note tables

Revision ID: 0bead747bab1
Revises: fc0536e41ee7
Create Date: 2026-11-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bead747bab1'
down_revision: Union[str, Sequence[str], None] = 'fc0536e41ee7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('document_page',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['document.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'page_number')
    )
    op.create_table('user_note',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_page_id', sa.Uuid(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_page_id'], ['document_page.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_page_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('user_note')
    op.drop_table('document_page')
