"""Regression test for #255: get_login_stats() 天數區間查詢。

修正前 services/login_record.py 用 ($n || ' days')::INTERVAL 把 days
(int) 串成字串再轉型,asyncpg 會回 DataError: expected str, got int。
修正後改用 make_interval(days => $n),$n 全程維持 int 型別。
"""

from __future__ import annotations

import inspect

import pytest
from unittest.mock import AsyncMock

from ching_tech_os.services import login_record


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def test_login_stats_sql_uses_make_interval_not_string_concat() -> None:
    """原始碼不得再出現 ($n || ' days')::INTERVAL 這種字串拼接寫法。"""
    source = inspect.getsource(login_record.get_login_stats)
    assert "|| ' days'" not in source
    assert "::INTERVAL" not in source
    assert "make_interval(days =>" in source


@pytest.mark.asyncio
async def test_get_login_stats_without_user_id_passes_int_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """days 必須以 int 直接傳給 asyncpg,不能先轉成字串。"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "total": 20,
            "success_count": 15,
            "failure_count": 5,
            "unique_ips": 4,
            "unique_devices": 6,
        }
    )
    monkeypatch.setattr(login_record, "get_connection", lambda: _CM(conn))

    result = await login_record.get_login_stats(days=30)

    assert result == {
        "total": 20,
        "success_count": 15,
        "failure_count": 5,
        "unique_ips": 4,
        "unique_devices": 6,
        "days": 30,
    }

    conn.fetchrow.assert_awaited_once()
    sql, *params = conn.fetchrow.await_args.args
    assert "make_interval(days => $1)" in sql
    assert "|| ' days'" not in sql
    assert "::INTERVAL" not in sql
    assert params == [30]
    assert isinstance(params[0], int)


@pytest.mark.asyncio
async def test_get_login_stats_with_user_id_passes_int_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """帶 user_id 的分支同樣要用 make_interval 並保持 days 為 int。"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "total": 10,
            "success_count": 9,
            "failure_count": 1,
            "unique_ips": 2,
            "unique_devices": 3,
        }
    )
    monkeypatch.setattr(login_record, "get_connection", lambda: _CM(conn))

    result = await login_record.get_login_stats(user_id=1, days=30)

    assert result["days"] == 30
    conn.fetchrow.assert_awaited_once()
    sql, *params = conn.fetchrow.await_args.args
    assert "make_interval(days => $2)" in sql
    assert "|| ' days'" not in sql
    assert "::INTERVAL" not in sql
    assert params == [1, 30]
    assert isinstance(params[1], int)
