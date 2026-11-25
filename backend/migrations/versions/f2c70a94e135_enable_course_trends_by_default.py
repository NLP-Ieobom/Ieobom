"""연구 동향을 기본으로 켠다."""

import sqlalchemy as sa
from alembic import op

revision = "f2c70a94e135"
down_revision = "c81d4b60f7a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("course", "is_trend_enabled", server_default=sa.text("true"))
    op.execute("UPDATE course SET is_trend_enabled = true")


def downgrade() -> None:
    # 어느 과목이 원래 꺼져 있었는지는 모르니 행은 그대로 두고 기본값만 되돌린다.
    op.alter_column("course", "is_trend_enabled", server_default=None)
