"""新增主動推送設定預設值

在 bot_settings 表中新增 proactive_push_enabled 設定：
- Line：預設關閉（false）
- Telegram：預設開啟（true）

Revision ID: 014
"""

from datetime import datetime, timezone

from alembic import op


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    op.execute(
        f"""
        INSERT INTO bot_settings (platform, key, value, updated_at)
        VALUES
            ('line',     'proactive_push_enabled', 'false', '{now.isoformat()}'),
            ('telegram', 'proactive_push_enabled', 'true',  '{now.isoformat()}')
        ON CONFLICT (platform, key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM bot_settings
        WHERE key = 'proactive_push_enabled'
          AND platform IN ('line', 'telegram')
        """
    )
