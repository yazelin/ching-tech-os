"""AI Log 依用戶篩選（migration 029）測試。

涵蓋：model 欄位、create_log 的 INSERT 參數、每個呼叫端帶入的 user_id 來源、
get_logs／get_log_stats 的 where 子句（user_id=5 與 user_id=0 兩種語意）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.models.ai import AiLogCreate, AiLogFilter, AiLogListItem, AiLogResponse
from ching_tech_os.services import ai_manager


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log_row(**over) -> dict:
    row = {
        "id": uuid4(),
        "agent_id": None,
        "prompt_id": None,
        "context_type": "web-chat",
        "context_id": "c1",
        "input_prompt": "in",
        "system_prompt": None,
        "allowed_tools": None,
        "raw_response": "ok",
        "parsed_response": None,
        "model": "m",
        "success": True,
        "error_message": None,
        "duration_ms": 1,
        "input_tokens": 1,
        "output_tokens": 2,
        "user_id": 7,
        "created_at": _now(),
    }
    row.update(over)
    return row


# ============================================================
# 1. Model 欄位
# ============================================================


def test_ai_log_create_has_optional_user_id() -> None:
    assert AiLogCreate(input_prompt="x").user_id is None
    assert AiLogCreate(input_prompt="x", user_id=5).user_id == 5


def test_ai_log_response_and_list_item_have_user_fields() -> None:
    detail = AiLogResponse(
        id=uuid4(),
        agent_id=None,
        prompt_id=None,
        context_type=None,
        context_id=None,
        input_prompt="in",
        raw_response=None,
        parsed_response=None,
        model=None,
        success=True,
        error_message=None,
        duration_ms=None,
        input_tokens=None,
        output_tokens=None,
        created_at=_now(),
    )
    assert detail.user_id is None and detail.username is None

    item = AiLogListItem(
        id=uuid4(),
        agent_id=None,
        agent_name=None,
        context_type=None,
        success=True,
        duration_ms=None,
        input_tokens=None,
        output_tokens=None,
        created_at=_now(),
        user_id=9,
        username="alice",
    )
    assert item.user_id == 9 and item.username == "alice"


def test_ai_log_filter_has_user_id() -> None:
    assert AiLogFilter().user_id is None
    assert AiLogFilter(user_id=0).user_id == 0


# ============================================================
# 2. create_log 帶入 user_id
# ============================================================


@pytest.mark.asyncio
async def test_create_log_passes_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_log_row(user_id=42))
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    result = await ai_manager.create_log(AiLogCreate(input_prompt="in", user_id=42))

    sql = conn.fetchrow.await_args.args[0]
    assert "user_id" in sql
    # user_id 是最後一個 INSERT 參數
    assert conn.fetchrow.await_args.args[-1] == 42
    assert result["user_id"] == 42


@pytest.mark.asyncio
async def test_create_log_user_id_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_log_row(user_id=None))
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.create_log(AiLogCreate(input_prompt="in"))
    assert conn.fetchrow.await_args.args[-1] is None


# ============================================================
# 3. 讀端：LEFT JOIN users 取 username、where 子句
# ============================================================


@pytest.mark.asyncio
async def test_get_logs_selects_username(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"total": 1})
    conn.fetch = AsyncMock(return_value=[
        {
            "id": uuid4(),
            "agent_id": None,
            "agent_name": None,
            "context_type": "web-chat",
            "model": "m",
            "input_prompt": "p",
            "allowed_tools": None,
            "parsed_response": None,
            "success": True,
            "duration_ms": 1,
            "input_tokens": 1,
            "output_tokens": 2,
            "user_id": 7,
            "username": "alice",
            "created_at": _now(),
        }
    ])
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    items, total = await ai_manager.get_logs(AiLogFilter(), page=1, page_size=10)

    list_sql = conn.fetch.await_args.args[0]
    assert "LEFT JOIN users u ON l.user_id = u.id" in list_sql
    assert "u.username" in list_sql
    assert total == 1
    assert items[0]["user_id"] == 7 and items[0]["username"] == "alice"


@pytest.mark.asyncio
async def test_get_log_detail_selects_username(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_log_row(agent_name=None, username="bob"))
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    detail = await ai_manager.get_log(uuid4())

    sql = conn.fetchrow.await_args.args[0]
    assert "LEFT JOIN users u ON l.user_id = u.id" in sql
    assert "u.username" in sql
    assert detail["username"] == "bob"


@pytest.mark.asyncio
async def test_get_logs_filters_by_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"total": 0})
    conn.fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.get_logs(AiLogFilter(user_id=5), page=1, page_size=10)

    count_call = conn.fetchrow.await_args
    assert "l.user_id = $1" in count_call.args[0]
    assert count_call.args[1] == 5


@pytest.mark.asyncio
async def test_get_logs_user_id_zero_means_null(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"total": 0})
    conn.fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.get_logs(AiLogFilter(user_id=0), page=1, page_size=10)

    count_call = conn.fetchrow.await_args
    assert "l.user_id IS NULL" in count_call.args[0]
    # 不應該把 0 當成參數送出去（只有 limit/offset 會進 fetch）
    assert len(count_call.args) == 1


@pytest.mark.asyncio
async def test_get_log_stats_filters_by_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "total_calls": 2,
        "success_count": 1,
        "failure_count": 1,
        "avg_duration_ms": 5.0,
        "total_input_tokens": 1,
        "total_output_tokens": 2,
    })
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.get_log_stats(user_id=5)
    call = conn.fetchrow.await_args
    assert "user_id = $1" in call.args[0]
    assert call.args[1] == 5


@pytest.mark.asyncio
async def test_get_log_stats_user_id_zero_means_null(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "total_calls": 0,
        "success_count": 0,
        "failure_count": 0,
        "avg_duration_ms": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    })
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.get_log_stats(user_id=0)
    call = conn.fetchrow.await_args
    assert "user_id IS NULL" in call.args[0]
    assert len(call.args) == 1
