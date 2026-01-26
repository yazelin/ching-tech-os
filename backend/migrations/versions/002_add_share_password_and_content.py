"""新增分享連結密碼和內容欄位

支援密碼保護的分享連結，以及直接儲存內容（用於 MD2PPT/MD2DOC）。

新增欄位：
- content: TEXT - 直接儲存的內容
- content_type: VARCHAR(50) - MIME type
- filename: VARCHAR(255) - 檔案名稱
- password_hash: VARCHAR(255) - bcrypt hash
- attempt_count: INTEGER - 密碼錯誤嘗試次數
- locked_at: TIMESTAMP - 鎖定時間

Revision ID: 002
Revises: 001
Create Date: 2025-01-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新增欄位到 public_share_links 表格
    op.add_column('public_share_links', sa.Column('content', sa.Text(), nullable=True))
    op.add_column('public_share_links', sa.Column('content_type', sa.String(50), nullable=True))
    op.add_column('public_share_links', sa.Column('filename', sa.String(255), nullable=True))
    op.add_column('public_share_links', sa.Column('password_hash', sa.String(255), nullable=True))
    op.add_column('public_share_links', sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('public_share_links', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))

    # 新增註解
    op.execute("COMMENT ON COLUMN public_share_links.content IS '直接儲存的內容（用於 content 資源類型）'")
    op.execute("COMMENT ON COLUMN public_share_links.content_type IS 'MIME type（如 text/markdown）'")
    op.execute("COMMENT ON COLUMN public_share_links.filename IS '檔案名稱'")
    op.execute("COMMENT ON COLUMN public_share_links.password_hash IS '密碼 bcrypt hash'")
    op.execute("COMMENT ON COLUMN public_share_links.attempt_count IS '密碼錯誤嘗試次數'")
    op.execute("COMMENT ON COLUMN public_share_links.locked_at IS '因錯誤次數過多而鎖定的時間'")


def downgrade() -> None:
    op.drop_column('public_share_links', 'locked_at')
    op.drop_column('public_share_links', 'attempt_count')
    op.drop_column('public_share_links', 'password_hash')
    op.drop_column('public_share_links', 'filename')
    op.drop_column('public_share_links', 'content_type')
    op.drop_column('public_share_links', 'content')
