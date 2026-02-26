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


class _SafeFormatMap(dict):
    """format_map 用的安全字典，未知 key 回傳空字串避免 KeyError"""

    def __missing__(self, key: str) -> str:
        return ""


class _RateLimitExceeded(Exception):
    """內部例外：頻率超限，用於觸發 transaction rollback"""


def _format_limit_msg(
    custom_messages: dict[str, str] | None,
    period: str,
    *,
    limit: int,
    count: int,
    default_msg: str,
) -> str:
    """格式化超限訊息，支援 {limit}、{count} 變數"""
    if custom_messages and custom_messages.get(period):
        return custom_messages[period].format_map(
            _SafeFormatMap(limit=str(limit), count=str(count))
        )
    return default_msg


def _current_hourly_key() -> str:
    """取得當前小時的 period_key（如 '2026-02-26-14'）"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d-%H")


def _current_daily_key() -> str:
    """取得當天的 period_key（如 '2026-02-26'）"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d")


async def check_and_increment(
    bot_user_id: str,
    custom_messages: dict[str, str] | None = None,
) -> tuple[bool, str | None]:
    """原子性地檢查頻率限制並遞增計數器

    在同一個交易中執行 SELECT + UPDATE，避免 TOCTOU 競爭條件。

    Args:
        bot_user_id: bot_users.id (UUID 字串)
        custom_messages: 自訂超限訊息模板，支援的 key：
            - "hourly": 每小時超限訊息（支援 {limit}、{count} 變數）
            - "daily": 每日超限訊息（支援 {limit}、{count} 變數）

    Returns:
        (是否允許, 拒絕訊息) - 允許時拒絕訊息為 None
    """
    if not settings.bot_rate_limit_enabled:
        # 即使未啟用頻率限制，仍記錄使用量供統計分析
        await record_usage(bot_user_id)
        return True, None

    hourly_key = _current_hourly_key()
    daily_key = _current_daily_key()

    try:
        async with get_connection() as conn:
            # 使用交易確保原子性：先遞增再檢查，
            # 若超限則拋出例外觸發 rollback，避免被拒絕的請求虛增計數器
            async with conn.transaction():
                # 先 UPSERT 計數器（+1），再檢查是否超限
                # 這避免了 check-then-act 的 TOCTOU 問題
                hourly_row = await conn.fetchrow(
                    """
                    INSERT INTO bot_usage_tracking (bot_user_id, period_type, period_key, message_count)
                    VALUES ($1, 'hourly', $2, 1)
                    ON CONFLICT (bot_user_id, period_type, period_key)
                    DO UPDATE SET message_count = bot_usage_tracking.message_count + 1,
                                 updated_at = NOW()
                    RETURNING message_count
                    """,
                    bot_user_id,
                    hourly_key,
                )
                daily_row = await conn.fetchrow(
                    """
                    INSERT INTO bot_usage_tracking (bot_user_id, period_type, period_key, message_count)
                    VALUES ($1, 'daily', $2, 1)
                    ON CONFLICT (bot_user_id, period_type, period_key)
                    DO UPDATE SET message_count = bot_usage_tracking.message_count + 1,
                                 updated_at = NOW()
                    RETURNING message_count
                    """,
                    bot_user_id,
                    daily_key,
                )

                hourly_count = hourly_row["message_count"] if hourly_row else 0
                daily_count = daily_row["message_count"] if daily_row else 0

                # 檢查每小時限額（已遞增後的值）
                if hourly_count > settings.bot_rate_limit_hourly:
                    raise _RateLimitExceeded(
                        _format_limit_msg(
                            custom_messages, "hourly",
                            limit=settings.bot_rate_limit_hourly,
                            count=hourly_count,
                            default_msg=(
                                f"您已達到每小時使用上限（{settings.bot_rate_limit_hourly} 則訊息）。\n"
                                "請稍後再試，或綁定帳號以獲得完整服務。"
                            ),
                        )
                    )

                # 檢查每日限額
                if daily_count > settings.bot_rate_limit_daily:
                    raise _RateLimitExceeded(
                        _format_limit_msg(
                            custom_messages, "daily",
                            limit=settings.bot_rate_limit_daily,
                            count=daily_count,
                            default_msg=(
                                f"您已達到每日使用上限（{settings.bot_rate_limit_daily} 則訊息）。\n"
                                "請明天再試，或綁定帳號以獲得完整服務。"
                            ),
                        )
                    )

                return True, None

    except _RateLimitExceeded as e:
        # 超限：transaction 已 rollback，計數器未遞增
        return False, str(e)

    except Exception:
        logger.exception("頻率限制檢查失敗，允許通過（fail-open）")
        return True, None


async def record_usage(bot_user_id: str) -> None:
    """記錄使用量（UPSERT 每小時和每日計數）

    用於 rate limit 未啟用時仍記錄統計資料。

    Args:
        bot_user_id: bot_users.id (UUID 字串)
    """
    hourly_key = _current_hourly_key()
    daily_key = _current_daily_key()

    try:
        async with get_connection() as conn:
            async with conn.transaction():
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


async def cleanup_old_tracking(days: int = 30) -> int:
    """清理過期的使用量追蹤資料

    Args:
        days: 保留天數（預設 30 天）

    Returns:
        刪除的記錄數
    """
    try:
        async with get_connection() as conn:
            result = await conn.execute(
                """
                DELETE FROM bot_usage_tracking
                WHERE updated_at < NOW() - INTERVAL '1 day' * $1
                """,
                days,
            )
            # result 格式如 "DELETE 42"
            deleted = int(result.split()[-1]) if result else 0
            if deleted > 0:
                logger.info("已清理 %d 筆過期的使用量追蹤資料", deleted)
            return deleted
    except Exception:
        logger.exception("清理使用量追蹤資料失敗")
        return 0
