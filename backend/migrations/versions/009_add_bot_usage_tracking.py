"""新增 bot_usage_tracking 資料表

追蹤未綁定用戶的訊息使用量，支援 rate limiting。

Revision ID: 009
"""

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE bot_usage_tracking (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bot_user_id UUID NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
            period_type VARCHAR(10) NOT NULL,
            period_key VARCHAR(20) NOT NULL,
            message_count INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(bot_user_id, period_type, period_key)
        )
    """)
    op.execute("""
        CREATE INDEX idx_bot_usage_tracking_user_period
        ON bot_usage_tracking(bot_user_id, period_type, period_key)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bot_usage_tracking")
