"""Line Bot 存取控制

Revision ID: 012
Revises: 011
Create Date: 2025-12-24

新增：
- line_groups.allow_ai_response 欄位
- line_binding_codes 表
"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 新增 line_groups.allow_ai_response 欄位
    op.execute("""
        ALTER TABLE line_groups
        ADD COLUMN IF NOT EXISTS allow_ai_response BOOLEAN DEFAULT false
    """)
    op.execute(
        "COMMENT ON COLUMN line_groups.allow_ai_response IS '是否允許 AI 回應（需開啟才會回應）'"
    )

    # 建立 line_binding_codes 表
    op.execute("""
        CREATE TABLE IF NOT EXISTS line_binding_codes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            code VARCHAR(6) NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            used_by_line_user_id UUID REFERENCES line_users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_binding_codes_code ON line_binding_codes(code)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_binding_codes_user_id ON line_binding_codes(user_id)")
    op.execute("COMMENT ON TABLE line_binding_codes IS 'Line 綁定驗證碼'")
    op.execute("COMMENT ON COLUMN line_binding_codes.code IS '6 位數字驗證碼'")
    op.execute("COMMENT ON COLUMN line_binding_codes.expires_at IS '驗證碼過期時間（5 分鐘）'")
    op.execute("COMMENT ON COLUMN line_binding_codes.used_at IS '使用時間'")
    op.execute("COMMENT ON COLUMN line_binding_codes.used_by_line_user_id IS '使用此驗證碼的 Line 用戶'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS line_binding_codes CASCADE")
    op.execute("ALTER TABLE line_groups DROP COLUMN IF EXISTS allow_ai_response")
