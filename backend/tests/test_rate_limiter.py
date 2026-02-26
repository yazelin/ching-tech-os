"""Rate Limiter 單元測試"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ching_tech_os.services.bot.rate_limiter import (
    check_rate_limit,
    record_usage,
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
        # 應該是 13 字元（如 2026-02-26-14）
        assert len(key) == 13
        parts = key.split("-")
        assert len(parts) == 4
        assert len(parts[0]) == 4  # 年
        assert len(parts[1]) == 2  # 月
        assert len(parts[2]) == 2  # 日
        assert len(parts[3]) == 2  # 時

    def test_daily_key_format(self):
        """每日 key 格式為 YYYY-MM-DD"""
        key = _current_daily_key()
        assert len(key) == 10
        parts = key.split("-")
        assert len(parts) == 3


# ============================================================
# check_rate_limit() 測試
# ============================================================


class TestCheckRateLimit:
    """測試 check_rate_limit()"""

    @pytest.mark.asyncio
    async def test_rate_limit_disabled_allows_all(self):
        """停用 rate limit → 一律通過"""
        with patch(
            "ching_tech_os.services.bot.rate_limiter.settings"
        ) as mock_settings:
            mock_settings.bot_rate_limit_enabled = False
            allowed, msg = await check_rate_limit("uuid-123")
            assert allowed is True
            assert msg is None

    @pytest.mark.asyncio
    async def test_within_limits_allowed(self):
        """使用量在限額內 → 通過"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"period_type": "hourly", "message_count": 5},
                {"period_type": "daily", "message_count": 10},
            ]
        )

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.bot.rate_limiter.get_connection"
            ) as mock_get_conn,
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50
            mock_get_conn.return_value.__aenter__ = AsyncMock(
                return_value=mock_conn
            )
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

            allowed, msg = await check_rate_limit("uuid-123")
            assert allowed is True
            assert msg is None

    @pytest.mark.asyncio
    async def test_hourly_limit_exceeded(self):
        """超過每小時限額 → 拒絕"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"period_type": "hourly", "message_count": 20},
                {"period_type": "daily", "message_count": 30},
            ]
        )

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.bot.rate_limiter.get_connection"
            ) as mock_get_conn,
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50
            mock_get_conn.return_value.__aenter__ = AsyncMock(
                return_value=mock_conn
            )
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

            allowed, msg = await check_rate_limit("uuid-123")
            assert allowed is False
            assert "每小時" in msg
            assert "20" in msg

    @pytest.mark.asyncio
    async def test_daily_limit_exceeded(self):
        """超過每日限額 → 拒絕"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"period_type": "hourly", "message_count": 5},
                {"period_type": "daily", "message_count": 50},
            ]
        )

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.bot.rate_limiter.get_connection"
            ) as mock_get_conn,
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50
            mock_get_conn.return_value.__aenter__ = AsyncMock(
                return_value=mock_conn
            )
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

            allowed, msg = await check_rate_limit("uuid-123")
            assert allowed is False
            assert "每日" in msg
            assert "50" in msg

    @pytest.mark.asyncio
    async def test_no_records_allowed(self):
        """無使用記錄 → 通過"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.bot.rate_limiter.get_connection"
            ) as mock_get_conn,
        ):
            mock_settings.bot_rate_limit_enabled = True
            mock_settings.bot_rate_limit_hourly = 20
            mock_settings.bot_rate_limit_daily = 50
            mock_get_conn.return_value.__aenter__ = AsyncMock(
                return_value=mock_conn
            )
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

            allowed, msg = await check_rate_limit("uuid-123")
            assert allowed is True
            assert msg is None


# ============================================================
# record_usage() 測試
# ============================================================


class TestRecordUsage:
    """測試 record_usage()"""

    @pytest.mark.asyncio
    async def test_record_executes_upserts(self):
        """記錄使用量執行兩次 UPSERT（hourly + daily）"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        with patch(
            "ching_tech_os.services.bot.rate_limiter.get_connection"
        ) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(
                return_value=mock_conn
            )
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

            await record_usage("uuid-123")
            assert mock_conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_record_failure_does_not_raise(self):
        """記錄失敗不應拋出例外"""
        with patch(
            "ching_tech_os.services.bot.rate_limiter.get_connection"
        ) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("DB error")
            )
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

            # 不應拋出例外
            await record_usage("uuid-123")
