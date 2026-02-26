"""Bot 頻率限制器

使用 PostgreSQL 的 bot_usage_tracking 表追蹤未綁定用戶的使用量。
僅在 BOT_UNBOUND_USER_POLICY=restricted 且 BOT_RATE_LIMIT_ENABLED=true 時生效。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ...config import settings
from ...database import get_connection

logger = logging.getLogger(__name__)


def _current_hourly_key() -> str:
    """取得當前小時的 period_key（如 '2026-02-26-14'）"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d-%H")


def _current_daily_key() -> str:
    """取得當天的 period_key（如 '2026-02-26'）"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d")


async def check_rate_limit(bot_user_id: str) -> tuple[bool, str | None]:
    """檢查未綁定用戶是否超過頻率限制

    Args:
        bot_user_id: bot_users.id (UUID 字串)

    Returns:
        (是否允許, 拒絕訊息) - 允許時拒絕訊息為 None
    """
    if not settings.bot_rate_limit_enabled:
        return True, None

    hourly_key = _current_hourly_key()
    daily_key = _current_daily_key()

    async with get_connection() as conn:
        # 一次查詢取得每小時和每日的使用量
        rows = await conn.fetch(
            """
            SELECT period_type, message_count
            FROM bot_usage_tracking
            WHERE bot_user_id = $1
              AND (
                (period_type = 'hourly' AND period_key = $2)
                OR (period_type = 'daily' AND period_key = $3)
              )
            """,
            bot_user_id,
            hourly_key,
            daily_key,
        )

    hourly_count = 0
    daily_count = 0
    for row in rows:
        if row["period_type"] == "hourly":
            hourly_count = row["message_count"]
        elif row["period_type"] == "daily":
            daily_count = row["message_count"]

    # 檢查每小時限額
    if hourly_count >= settings.bot_rate_limit_hourly:
        return False, (
            f"您已達到每小時使用上限（{settings.bot_rate_limit_hourly} 則訊息）。\n"
            "請稍後再試，或綁定帳號以獲得完整服務。"
        )

    # 檢查每日限額
    if daily_count >= settings.bot_rate_limit_daily:
        return False, (
            f"您已達到每日使用上限（{settings.bot_rate_limit_daily} 則訊息）。\n"
            "請明天再試，或綁定帳號以獲得完整服務。"
        )

    return True, None


async def record_usage(bot_user_id: str) -> None:
    """記錄使用量（UPSERT 每小時和每日計數）

    不論 rate limit 是否啟用都會記錄，供後續統計分析使用。

    Args:
        bot_user_id: bot_users.id (UUID 字串)
    """
    hourly_key = _current_hourly_key()
    daily_key = _current_daily_key()

    try:
        async with get_connection() as conn:
            # UPSERT 每小時計數
            await conn.execute(
                """
                INSERT INTO bot_usage_tracking (bot_user_id, period_type, period_key, message_count)
                VALUES ($1, 'hourly', $2, 1)
                ON CONFLICT (bot_user_id, period_type, period_key)
                DO UPDATE SET message_count = bot_usage_tracking.message_count + 1,
                             updated_at = NOW()
                """,
                bot_user_id,
                hourly_key,
            )
            # UPSERT 每日計數
            await conn.execute(
                """
                INSERT INTO bot_usage_tracking (bot_user_id, period_type, period_key, message_count)
                VALUES ($1, 'daily', $2, 1)
                ON CONFLICT (bot_user_id, period_type, period_key)
                DO UPDATE SET message_count = bot_usage_tracking.message_count + 1,
                             updated_at = NOW()
                """,
                bot_user_id,
                daily_key,
            )
    except Exception:
        # 記錄使用量失敗不應阻擋訊息處理
        logger.exception("記錄使用量失敗")
