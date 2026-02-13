"""bot_line.trigger 非同步流程測試。"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

import ching_tech_os.services.bot_line.trigger as trigger


class _CM:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_is_bot_message_true_false():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[{"is_from_bot": True}, {"is_from_bot": False}, None])

    with patch("ching_tech_os.services.bot_line.trigger.get_connection", return_value=_CM(conn)):
        assert await trigger.is_bot_message("m1") is True
        assert await trigger.is_bot_message("m2") is False
        assert await trigger.is_bot_message("m3") is False


@pytest.mark.asyncio
async def test_reset_conversation_success_and_fail(monkeypatch: pytest.MonkeyPatch):
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["UPDATE 1", "UPDATE 0"])
    info = Mock()
    monkeypatch.setattr(trigger.logger, "info", info)

    with patch("ching_tech_os.services.bot_line.trigger.get_connection", return_value=_CM(conn)):
        assert await trigger.reset_conversation("U1") is True
        assert await trigger.reset_conversation("U2") is False

    info.assert_called_once()
