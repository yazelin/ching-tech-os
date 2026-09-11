"""ai_logs 加 user_id（AI Log 依用戶篩選）

規格：docs/superpowers/specs/2026-09-11-project-module-design.md 第五節第 3 點。

刻意不加外鍵到 users：ai_logs 是以 created_at range 分區的分區表，
PG16 雖然允許分區表對一般表建 FK，但 users 每刪一筆就要掃過所有分區驗參照，
代價不值得。孤兒 user_id 在讀端用 LEFT JOIN 處理（查不到 username 就是 NULL）。

在分區父表上 add_column 會自動套到所有既有與未來分區，所以不需要逐個分區改。

Revision ID: 029
"""

import sqlalchemy as sa
from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_logs",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    # 分區父表上建索引會自動在每個分區建對應的 local index
    op.create_index("idx_ai_logs_user_id", "ai_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_ai_logs_user_id", table_name="ai_logs")
    op.drop_column("ai_logs", "user_id")
