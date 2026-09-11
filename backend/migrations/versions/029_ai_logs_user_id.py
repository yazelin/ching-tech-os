"""ai_logs 加 user_id（AI Log 依用戶篩選）

規格：docs/superpowers/specs/2026-09-11-project-module-design.md 第五節第 3 點，
`user_id int null → users.id on delete set null`。

外鍵建在分區父表上。PG16 允許分區表對一般表建 FK，約束會套到所有既有分區；
之後由 `create_ai_logs_partition()` 自動建的分區走的是
`CREATE TABLE … PARTITION OF ai_logs`，父表的約束同樣會繼承，不需要逐個分區補。

`ON DELETE SET NULL` 的好處是「使用者已刪除」直接等同「未記錄使用者」，
讀端與前端只要處理 NULL 一種情形，不會出現查不到名字的孤兒 ID。
代價是刪 users 時要掃過所有分區驗參照，`idx_ai_logs_user_id` 讓這件事走索引。

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
    # 分區父表上建索引會自動在每個分區建對應的 local index。
    # 先建索引再建外鍵：刪 users 時的參照檢查才走得到索引。
    op.create_index("idx_ai_logs_user_id", "ai_logs", ["user_id"])
    op.create_foreign_key(
        "fk_ai_logs_user_id",
        "ai_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ai_logs_user_id", "ai_logs", type_="foreignkey")
    op.drop_index("idx_ai_logs_user_id", table_name="ai_logs")
    op.drop_column("ai_logs", "user_id")
