"""Rate Limiter 單元測試"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ching_tech_os.services.bot.rate_limiter import (
    check_and_increment,
    record_usage,
    cleanup_old_tracking,
    _current_hourly_key,
    _current_daily_key,
)


# ============================================================
# 輔助函式測試
# ============================================================


class TestPeriodKeys:
    """period_key 格式測試"""

    def test_hourly_key_format(self):
        """每小時 key 格式為 YYYY-MM-DD-HH"""
        key = _current_hourly_key()
        assert len(key) == 13
        parts = key.split("-")
        assert len(parts) == 4
        assert len(parts[0]) == 4
        assert len(parts[1]) == 2
        assert len(parts[2]) == 2
        assert len(parts[3]) == 2

    def test_daily_key_format(self):
        """每日 key 格式為 YYYY-MM-DD"""
        key = _current_daily_key()
        assert len(key) == 10
        parts = key.split("-")
        assert len(parts) == 3


# ============================================================
# 輔助 mock 工廠
# ============================================================


def _make_conn_mock(hourly_count: int = 0, daily_count: int = 0):
    """建立模擬 DB 連線（支援 transaction + fetchrow）

    asyncpg 的 conn.transaction() 回傳一個同步物件，但支援 async with。
    """
    mock_conn = MagicMock()

    # fetchrow 依次回傳 hourly 和 daily 的計數結果
    mock_conn.fetchrow = AsyncMock(
        side_effect=[
            {"message_count": hourly_count},
            {"message_count": daily_count},
        ]
    )
    mock_conn.execute = AsyncMock()

    # transaction() 是同步呼叫，回傳的物件支援 async with
    mock_txn = MagicMock()
    mock_txn.__aenter__ = AsyncMock(return_value=mock_txn)
    mock_txn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=mock_txn)

    return mock_conn


def _make_get_conn_patch(mock_conn):
    """建立 get_connection context manager patch"""
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "ching_tech_os.services.bot.rate_limiter.get_connection",
        return_value=mock_ctx,
    )


# ============================================================
# check_and_increment() 測試
# ============================================================


class TestCheckAndIncrement:
    """測試原子性 check_and_increment()"""

    @pytest.mark.asyncio
    async def test_rate_limit_disabled_allows_all(self):
        """停用 rate limit → 一律通過（但仍記錄用量）"""
        mock_conn = _make_conn_mock()

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            _make_get_conn_patch(mock_conn),
        ):
            mock_settings.bot_rate_limit_enabled = False
            allowed, msg = await check_and_increment("uuid-123")
            assert allowed is True
            assert msg is None

    @pytest.mark.asyncio
    async def test_within_limits_allowed(self):
        """使用量在限額內（遞增後 6 和 11）→ 通過"""
        mock_conn = _make_conn_mock(hourly_count=6, daily_count=11)

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            _make_get_conn_patch(mock_conn),
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50

            allowed, msg = await check_and_increment("uuid-123")
            assert allowed is True
            assert msg is None

    @pytest.mark.asyncio
    async def test_hourly_limit_exceeded(self):
        """遞增後超過每小時限額 → 拒絕"""
        mock_conn = _make_conn_mock(hourly_count=21, daily_count=30)

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            _make_get_conn_patch(mock_conn),
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50

            allowed, msg = await check_and_increment("uuid-123")
            assert allowed is False
            assert "每小時" in msg
            assert "20" in msg

    @pytest.mark.asyncio
    async def test_daily_limit_exceeded(self):
        """遞增後超過每日限額 → 拒絕"""
        mock_conn = _make_conn_mock(hourly_count=5, daily_count=51)

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            _make_get_conn_patch(mock_conn),
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50

            allowed, msg = await check_and_increment("uuid-123")
            assert allowed is False
            assert "每日" in msg
            assert "50" in msg

    @pytest.mark.asyncio
    async def test_first_message_allowed(self):
        """第一則訊息（遞增後 hourly=1, daily=1）→ 通過"""
        mock_conn = _make_conn_mock(hourly_count=1, daily_count=1)

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            _make_get_conn_patch(mock_conn),
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50

            allowed, msg = await check_and_increment("uuid-123")
            assert allowed is True
            assert msg is None

    @pytest.mark.asyncio
    async def test_hourly_custom_message(self):
        """自訂每小時超限訊息 + 變數替換"""
        mock_conn = _make_conn_mock(hourly_count=21, daily_count=30)

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            _make_get_conn_patch(mock_conn),
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50

            allowed, msg = await check_and_increment(
                "uuid-123",
                custom_messages={"hourly": "每小時最多 {hourly_limit} 則，請稍後再試。"},
            )
            assert allowed is False
            assert msg == "每小時最多 20 則，請稍後再試。"

    @pytest.mark.asyncio
    async def test_daily_custom_message(self):
        """自訂每日超限訊息 + 變數替換"""
        mock_conn = _make_conn_mock(hourly_count=5, daily_count=51)

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            _make_get_conn_patch(mock_conn),
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50

            allowed, msg = await check_and_increment(
                "uuid-123",
                custom_messages={"daily": "今日已達 {daily_limit} 則上限，明天再來！"},
            )
            assert allowed is False
            assert msg == "今日已達 50 則上限，明天再來！"

    @pytest.mark.asyncio
    async def test_custom_message_unknown_variable_safe(self):
        """自訂訊息含未知變數 → 不拋出 KeyError，變數替換為空字串"""
        mock_conn = _make_conn_mock(hourly_count=21, daily_count=30)

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            _make_get_conn_patch(mock_conn),
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50

            allowed, msg = await check_and_increment(
                "uuid-123",
                custom_messages={"hourly": "上限 {hourly_limit}，{unknown_var} 再試"},
            )
            assert allowed is False
            assert "上限 20" in msg
            assert "{unknown_var}" not in msg

    @pytest.mark.asyncio
    async def test_custom_messages_none_uses_default(self):
        """custom_messages=None → 使用預設訊息"""
        mock_conn = _make_conn_mock(hourly_count=21, daily_count=30)

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            _make_get_conn_patch(mock_conn),
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50

            allowed, msg = await check_and_increment("uuid-123", custom_messages=None)
            assert allowed is False
            assert "每小時" in msg
            assert "20" in msg

    @pytest.mark.asyncio
    async def test_db_error_fail_open(self):
        """DB 錯誤 → fail-open（允許通過）"""
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.bot.rate_limiter.get_connection",
                return_value=mock_ctx,
            ),
        ):
            mock_settings.bot_rate_limit_enabled = True

            allowed, msg = await check_and_increment("uuid-123")
            assert allowed is True
            assert msg is None


# ============================================================
# record_usage() 測試
# ============================================================


class TestRecordUsage:
    """測試 record_usage()"""

    @pytest.mark.asyncio
    async def test_record_executes_upserts(self):
        """記錄使用量在交易中執行兩次 UPSERT（hourly + daily）"""
        mock_conn = _make_conn_mock()

        with _make_get_conn_patch(mock_conn):
            await record_usage("uuid-123")
            assert mock_conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_record_failure_does_not_raise(self):
        """記錄失敗不應拋出例外"""
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "ching_tech_os.services.bot.rate_limiter.get_connection",
            return_value=mock_ctx,
        ):
            await record_usage("uuid-123")


# ============================================================
# cleanup_old_tracking() 測試
# ============================================================


class TestCleanupOldTracking:
    """測試 cleanup_old_tracking()"""

    @pytest.mark.asyncio
    async def test_cleanup_returns_count(self):
        """清理成功回傳刪除筆數"""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 42")

        with _make_get_conn_patch(mock_conn):
            deleted = await cleanup_old_tracking(days=30)
            assert deleted == 42

    @pytest.mark.asyncio
    async def test_cleanup_failure_returns_zero(self):
        """清理失敗回傳 0"""
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "ching_tech_os.services.bot.rate_limiter.get_connection",
            return_value=mock_ctx,
        ):
            deleted = await cleanup_old_tracking()
            assert deleted == 0
