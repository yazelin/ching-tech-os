"""scheduled_tasks 加 consecutive_failures（連續失敗計數）

排程只留最後一次結果，連續失敗七天跟失敗一次從外面看完全一樣。
加一個連續失敗計數：成功歸零、失敗 +1，讓失敗推播講得出「連續第 N 次」。

Revision ID: 027
"""

import sqlalchemy as sa
from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scheduled_tasks",
        sa.Column(
            "consecutive_failures",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("scheduled_tasks", "consecutive_failures")
