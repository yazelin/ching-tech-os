"""新增 api_tokens 表（長效 API token / PAT）

供 CLI 與自動化工具以 Authorization: Bearer ctos_pat_xxx 存取 API。
僅儲存 token 的 SHA-256 hash，原始 token 只在建立時回傳一次。

Revision ID: 025
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        # 允許存取的 app id 清單（如 ["knowledge-base"]），空陣列代表使用者全部 app 權限
        sa.Column("scopes", JSONB(), nullable=False, server_default="[]"),
        sa.Column("read_only", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_api_tokens_user_id", "api_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_api_tokens_user_id", table_name="api_tokens")
    op.drop_table("api_tokens")
