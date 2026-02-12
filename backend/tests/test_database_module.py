"""database 模組單元測試。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from ching_tech_os import database


@pytest.fixture(autouse=True)
def reset_db_pool() -> None:
    """每個測試前後重置全域連線池狀態。"""
    database._pool = None
    yield
    database._pool = None


@pytest.mark.asyncio
async def test_setup_json_codec_registers_json_and_jsonb() -> None:
    conn = AsyncMock()

    await database._setup_json_codec(conn)

    assert conn.set_type_codec.await_count == 2
    first_call = conn.set_type_codec.await_args_list[0]
    second_call = conn.set_type_codec.await_args_list[1]
    assert first_call.args[0] == "jsonb"
    assert second_call.args[0] == "json"


@pytest.mark.asyncio
async def test_init_db_pool_uses_expected_pool_options(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = AsyncMock()
    mock_create_pool = AsyncMock(return_value=pool)
    monkeypatch.setattr(database.asyncpg, "create_pool", mock_create_pool)

    await database.init_db_pool()

    assert database._pool is pool
    kwargs = mock_create_pool.await_args.kwargs
    assert kwargs["min_size"] == 2
    assert kwargs["max_size"] == 10
    assert kwargs["init"] is database._setup_json_codec


@pytest.mark.asyncio
async def test_close_db_pool_closes_pool_and_clears_global() -> None:
    pool = AsyncMock()
    database._pool = pool

    await database.close_db_pool()

    pool.close.assert_awaited_once()
    assert database._pool is None


def test_get_pool_raises_when_uninitialized() -> None:
    with pytest.raises(RuntimeError, match="Database pool not initialized"):
        database.get_pool()


@pytest.mark.asyncio
async def test_get_connection_yields_acquired_connection() -> None:
    conn = object()

    class _AcquireCM:
        async def __aenter__(self) -> Any:
            return conn

        async def __aexit__(self, *_: Any) -> None:
            return None

    class _Pool:
        def acquire(self) -> _AcquireCM:
            return _AcquireCM()

    database._pool = _Pool()  # type: ignore[assignment]

    async with database.get_connection() as got:
        assert got is conn
