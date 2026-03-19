"""月度 Token 用量上限測試"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ching_tech_os.services.bot.rate_limiter import (
    check_monthly_tokens,
    record_token_usage,
    _current_monthly_key,
)


# ============================================================
# 輔助 mock
# ============================================================


def _make_conn_mock(token_count: int | None = 0):
    """建立模擬 DB 連線"""
    row = {"message_count": token_count} if token_count is not None else None

    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    conn.execute = AsyncMock()

    # asyncpg transaction context manager
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)

    # connection context manager
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)

    return ctx, conn


# ============================================================
# TestCurrentMonthlyKey
# ============================================================


class TestCurrentMonthlyKey:
    """monthly key 格式測試"""

    def test_format(self):
        """格式為 YYYY-MM"""
        key = _current_monthly_key()
        assert len(key) == 7
        parts = key.split("-")
        assert len(parts) == 2
        assert len(parts[0]) == 4
        assert len(parts[1]) == 2


# ============================================================
# TestCheckMonthlyTokens
# ============================================================


class TestCheckMonthlyTokens:
    """月度 token 額度檢查"""

    @pytest.mark.asyncio
    async def test_no_limit_configured(self):
        """沒有設定上限（0）→ allow"""
        allowed, msg = await check_monthly_tokens("user-1", monthly_limit=0)
        assert allowed is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_negative_limit(self):
        """負數上限 → allow"""
        allowed, msg = await check_monthly_tokens("user-1", monthly_limit=-1)
        assert allowed is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_under_limit(self):
        """未超額 → allow"""
        ctx, conn = _make_conn_mock(token_count=1000)
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            allowed, msg = await check_monthly_tokens("user-1", monthly_limit=500000)
            assert allowed is True
            assert msg is None

    @pytest.mark.asyncio
    async def test_at_limit(self):
        """剛好達到上限 → reject"""
        ctx, conn = _make_conn_mock(token_count=500000)
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            allowed, msg = await check_monthly_tokens("user-1", monthly_limit=500000)
            assert allowed is False
            assert msg is not None

    @pytest.mark.asyncio
    async def test_over_limit(self):
        """超額 → reject"""
        ctx, conn = _make_conn_mock(token_count=600000)
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            allowed, msg = await check_monthly_tokens("user-1", monthly_limit=500000)
            assert allowed is False
            assert "500,000" in msg

    @pytest.mark.asyncio
    async def test_no_existing_record(self):
        """沒有使用紀錄（row=None）→ allow"""
        ctx, conn = _make_conn_mock(token_count=None)
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            allowed, msg = await check_monthly_tokens("user-1", monthly_limit=500000)
            assert allowed is True

    @pytest.mark.asyncio
    async def test_custom_message(self):
        """自訂超額訊息，支援 {limit} 和 {count} 變數"""
        ctx, conn = _make_conn_mock(token_count=600000)
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            allowed, msg = await check_monthly_tokens(
                "user-1",
                monthly_limit=500000,
                custom_message="額度已滿 limit={limit} count={count}",
            )
            assert allowed is False
            assert "500000" in msg
            assert "600000" in msg

    @pytest.mark.asyncio
    async def test_db_error_failopen(self):
        """DB 錯誤 → fail-open"""
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("db down"))
        ctx.__aexit__ = AsyncMock(return_value=None)
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            allowed, msg = await check_monthly_tokens("user-1", monthly_limit=500000)
            assert allowed is True
            assert msg is None


# ============================================================
# TestRecordTokenUsage
# ============================================================


class TestRecordTokenUsage:
    """token 用量記錄"""

    @pytest.mark.asyncio
    async def test_record_tokens(self):
        """記錄 token 用量（UPSERT monthly_tokens）"""
        ctx, conn = _make_conn_mock()
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            await record_token_usage("user-1", input_tokens=1000, output_tokens=200)
            conn.execute.assert_called_once()
            sql = conn.execute.call_args[0][0]
            assert "monthly_tokens" in sql
            # 第三個參數是 total tokens = 1200
            assert conn.execute.call_args[0][3] == 1200

    @pytest.mark.asyncio
    async def test_record_zero_tokens_skipped(self):
        """token 為 0 → 不記錄"""
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection") as mock_gc:
            await record_token_usage("user-1", input_tokens=0, output_tokens=0)
            mock_gc.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_none_tokens_skipped(self):
        """token 為 None → 不記錄"""
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection") as mock_gc:
            await record_token_usage("user-1", input_tokens=None, output_tokens=None)
            mock_gc.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_only_input(self):
        """只有 input_tokens → 正常記錄"""
        ctx, conn = _make_conn_mock()
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            await record_token_usage("user-1", input_tokens=500, output_tokens=None)
            conn.execute.assert_called_once()
            assert conn.execute.call_args[0][3] == 500

    @pytest.mark.asyncio
    async def test_record_db_error_silent(self):
        """DB 錯誤 → 靜默失敗"""
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("db down"))
        ctx.__aexit__ = AsyncMock(return_value=None)
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            # 不應拋出例外
            await record_token_usage("user-1", input_tokens=1000, output_tokens=200)
