"""proactive_push_service 單元測試。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ching_tech_os.services import proactive_push_service as svc


class _CM:
    """模擬 async context manager for get_connection"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_):
        return None


# ── _is_push_enabled ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_is_push_enabled_true(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"value": "true"})
    monkeypatch.setattr(svc, "get_connection", lambda: _CM(conn))

    assert await svc._is_push_enabled("line") is True


@pytest.mark.asyncio
async def test_is_push_enabled_false(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"value": "false"})
    monkeypatch.setattr(svc, "get_connection", lambda: _CM(conn))

    assert await svc._is_push_enabled("telegram") is False


@pytest.mark.asyncio
async def test_is_push_enabled_missing_row_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺少記錄時：Line 預設 False、Telegram 預設 True"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    monkeypatch.setattr(svc, "get_connection", lambda: _CM(conn))

    assert await svc._is_push_enabled("line") is False
    assert await svc._is_push_enabled("telegram") is True
    assert await svc._is_push_enabled("unknown") is False  # 未知平台預設 False


@pytest.mark.asyncio
async def test_is_push_enabled_db_exception_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB 例外時靜默處理，回傳預設值"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=RuntimeError("db error"))
    monkeypatch.setattr(svc, "get_connection", lambda: _CM(conn))

    assert await svc._is_push_enabled("line") is False
    assert await svc._is_push_enabled("telegram") is True


# ── notify_job_complete ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notify_disabled_skips_push(monkeypatch: pytest.MonkeyPatch) -> None:
    """推送停用時不呼叫任何推送函式"""
    monkeypatch.setattr(svc, "_is_push_enabled", AsyncMock(return_value=False))
    push_line = AsyncMock()
    monkeypatch.setattr(svc, "_push_line", push_line)
    push_telegram = AsyncMock()
    monkeypatch.setattr(svc, "_push_telegram", push_telegram)

    await svc.notify_job_complete("line", "U123", False, None, "msg")

    push_line.assert_not_called()
    push_telegram.assert_not_called()


@pytest.mark.asyncio
async def test_notify_no_target_skips_push(monkeypatch: pytest.MonkeyPatch) -> None:
    """target 為空（is_group=False 且 platform_user_id 空）時跳過"""
    monkeypatch.setattr(svc, "_is_push_enabled", AsyncMock(return_value=True))
    push_line = AsyncMock()
    monkeypatch.setattr(svc, "_push_line", push_line)

    await svc.notify_job_complete("line", "", False, None, "msg")

    push_line.assert_not_called()


@pytest.mark.asyncio
async def test_notify_line_personal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Line 個人對話：target = platform_user_id"""
    monkeypatch.setattr(svc, "_is_push_enabled", AsyncMock(return_value=True))
    push_line = AsyncMock()
    monkeypatch.setattr(svc, "_push_line", push_line)

    await svc.notify_job_complete("line", "U999", False, None, "hello")

    push_line.assert_awaited_once_with("U999", "hello")


@pytest.mark.asyncio
async def test_notify_line_group_uses_group_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Line 群組對話：target = group_id"""
    monkeypatch.setattr(svc, "_is_push_enabled", AsyncMock(return_value=True))
    push_line = AsyncMock()
    monkeypatch.setattr(svc, "_push_line", push_line)

    await svc.notify_job_complete("line", "U999", True, "CGROUP123", "hello group")

    push_line.assert_awaited_once_with("CGROUP123", "hello group")


@pytest.mark.asyncio
async def test_notify_telegram(monkeypatch: pytest.MonkeyPatch) -> None:
    """Telegram 個人對話推送"""
    monkeypatch.setattr(svc, "_is_push_enabled", AsyncMock(return_value=True))
    push_telegram = AsyncMock()
    monkeypatch.setattr(svc, "_push_telegram", push_telegram)

    await svc.notify_job_complete("telegram", "850654509", False, None, "tg msg")

    push_telegram.assert_awaited_once_with("850654509", "tg msg")


@pytest.mark.asyncio
async def test_notify_unsupported_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """不支援的平台：靜默忽略，不拋例外"""
    monkeypatch.setattr(svc, "_is_push_enabled", AsyncMock(return_value=True))

    await svc.notify_job_complete("discord", "user1", False, None, "msg")  # 不應拋例外


@pytest.mark.asyncio
async def test_notify_push_exception_is_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    """推送函式拋例外時靜默處理，不往外拋"""
    monkeypatch.setattr(svc, "_is_push_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(svc, "_push_line", AsyncMock(side_effect=RuntimeError("network error")))

    await svc.notify_job_complete("line", "U123", False, None, "msg")  # 不應拋例外


# ── _push_telegram ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_push_telegram_no_token() -> None:
    """bot_token 未設定時靜默跳過"""
    with patch("ching_tech_os.services.bot_settings.get_bot_credentials", AsyncMock(return_value={})):
        await svc._push_telegram("chat123", "msg")  # 不應拋例外
