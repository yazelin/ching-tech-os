"""將 users.username 的普通索引改為 UNIQUE 約束

原本只有 btree index（idx_users_username），導致 ON CONFLICT (username) 無法使用。

Revision ID: 006
"""

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 移除舊的普通索引
    op.drop_index("idx_users_username", table_name="users")
    # 建立 unique constraint（會自動產生 unique index）
    op.create_unique_constraint("uq_users_username", "users", ["username"])


def downgrade() -> None:
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.create_index("idx_users_username", "users", ["username"])
