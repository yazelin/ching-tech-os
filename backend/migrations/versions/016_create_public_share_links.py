"""create public_share_links table

Revision ID: 016
Revises: 015
Create Date: 2025-01-06

公開分享連結 - 暫時性公開連結功能
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 公開分享連結表
    op.execute("""
        CREATE TABLE IF NOT EXISTS public_share_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            token VARCHAR(10) NOT NULL UNIQUE,
            resource_type VARCHAR(20) NOT NULL,
            resource_id VARCHAR(100) NOT NULL,
            created_by VARCHAR(100) NOT NULL,
            expires_at TIMESTAMPTZ,
            access_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # 建立索引
    op.execute("CREATE INDEX IF NOT EXISTS idx_share_links_token ON public_share_links(token)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_share_links_created_by ON public_share_links(created_by)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_share_links_resource ON public_share_links(resource_type, resource_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_share_links_expires_at ON public_share_links(expires_at)")

    # 註解
    op.execute("COMMENT ON TABLE public_share_links IS '公開分享連結'")
    op.execute("COMMENT ON COLUMN public_share_links.token IS '短 token 用於 URL，6 字元'")
    op.execute("COMMENT ON COLUMN public_share_links.resource_type IS '資源類型：knowledge 或 project'")
    op.execute("COMMENT ON COLUMN public_share_links.resource_id IS '資源 ID（kb-xxx 或專案 UUID）'")
    op.execute("COMMENT ON COLUMN public_share_links.created_by IS '建立者使用者名稱'")
    op.execute("COMMENT ON COLUMN public_share_links.expires_at IS '過期時間，NULL 表示永久有效'")
    op.execute("COMMENT ON COLUMN public_share_links.access_count IS '存取次數統計'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public_share_links")
