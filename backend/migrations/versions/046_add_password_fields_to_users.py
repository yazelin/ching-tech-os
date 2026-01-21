"""為 users 表新增密碼相關欄位

Revision ID: 046
Revises: 045
Create Date: 2026-01-21

支援獨立會員系統的密碼欄位：
- password_hash: bcrypt 密碼雜湊
- email: 使用者 Email（可選，用於密碼重設）
- password_changed_at: 密碼最後更改時間
- must_change_password: 下次登入需更改密碼
- is_active: 帳號是否啟用
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新增密碼雜湊欄位（允許 NULL，現有用戶需由管理員設定密碼）
    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(255),
            nullable=True,
            comment="bcrypt 密碼雜湊"
        )
    )

    # 新增 email 欄位（可選，用於密碼重設）
    op.add_column(
        "users",
        sa.Column(
            "email",
            sa.String(255),
            nullable=True,
            comment="使用者 Email（可選）"
        )
    )

    # 新增密碼最後更改時間
    op.add_column(
        "users",
        sa.Column(
            "password_changed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="密碼最後更改時間"
        )
    )

    # 新增強制變更密碼標記
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="下次登入需更改密碼"
        )
    )

    # 新增帳號啟用狀態
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
            comment="帳號是否啟用"
        )
    )

    # 建立 email 在租戶內的部分唯一索引（只對 email 不為 NULL 的記錄）
    op.execute("""
        CREATE UNIQUE INDEX idx_users_tenant_email
        ON users (tenant_id, email)
        WHERE email IS NOT NULL;
    """)


def downgrade() -> None:
    # 刪除索引
    op.execute("DROP INDEX IF EXISTS idx_users_tenant_email;")

    # 刪除欄位
    op.drop_column("users", "is_active")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "email")
    op.drop_column("users", "password_hash")
