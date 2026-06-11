"""MCP 知識工具條目層級權限測試（_check_item_access）"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services.mcp import knowledge_tools
from ching_tech_os.models.knowledge import (
    KnowledgeResponse,
    KnowledgeSource,
    KnowledgeTags,
)


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _kb(
    scope: str = "global",
    owner: str | None = None,
    is_public: bool = False,
) -> KnowledgeResponse:
    return KnowledgeResponse(
        id="kb-9",
        title="t",
        type="note",
        category="technical",
        scope=scope,
        owner=owner,
        is_public=is_public,
        tags=KnowledgeTags(),
        source=KnowledgeSource(),
        related=[],
        attachments=[],
        author="a",
        created_at=date.today(),
        updated_at=date.today(),
        content="c",
    )


def _user_conn(monkeypatch, username="yazelin", role="user", preferences=None):
    conn = SimpleNamespace(
        fetchrow=AsyncMock(
            return_value={
                "username": username,
                "role": role,
                "preferences": preferences,
            }
        )
    )
    monkeypatch.setattr(knowledge_tools, "get_connection", lambda: _ConnCtx(conn))
    return conn


@pytest.mark.asyncio
async def test_unbound_user_access() -> None:
    # 未綁定：global + is_public 可讀
    assert await knowledge_tools._check_item_access(
        _kb(scope="global", is_public=True), None, "read"
    ) is None

    # 未綁定：global 非公開不可讀
    err = await knowledge_tools._check_item_access(
        _kb(scope="global", is_public=False), None, "read"
    )
    assert "找不到" in err

    # 未綁定：personal 不可讀（不洩漏存在）
    err = await knowledge_tools._check_item_access(
        _kb(scope="personal", owner="jayho"), None, "read"
    )
    assert "找不到" in err

    # 未綁定：不可寫
    err = await knowledge_tools._check_item_access(
        _kb(scope="global", is_public=True), None, "write"
    )
    assert "綁定" in err


@pytest.mark.asyncio
async def test_bound_user_personal_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _user_conn(monkeypatch, username="yazelin")

    # 非 owner 讀 personal：找不到（不洩漏）
    err = await knowledge_tools._check_item_access(
        _kb(scope="personal", owner="jayho"), 7, "read"
    )
    assert "找不到" in err

    # 非 owner 寫/刪 personal：權限錯誤
    err = await knowledge_tools._check_item_access(
        _kb(scope="personal", owner="jayho"), 7, "write"
    )
    assert "權限" in err
    err = await knowledge_tools._check_item_access(
        _kb(scope="personal", owner="jayho"), 7, "delete"
    )
    assert "權限" in err

    # owner 全可
    _user_conn(monkeypatch, username="jayho")
    for action in ("read", "write", "delete"):
        assert await knowledge_tools._check_item_access(
            _kb(scope="personal", owner="jayho"), 7, action
        ) is None


@pytest.mark.asyncio
async def test_bound_user_global_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    _user_conn(monkeypatch, username="yazelin")

    # global：可讀
    assert await knowledge_tools._check_item_access(_kb(scope="global"), 7, "read") is None

    # global：無 global_write 不可寫
    err = await knowledge_tools._check_item_access(_kb(scope="global"), 7, "write")
    assert "權限" in err

    # admin：全可
    _user_conn(monkeypatch, username="boss", role="admin")
    assert await knowledge_tools._check_item_access(
        _kb(scope="personal", owner="jayho"), 7, "delete"
    ) is None


@pytest.mark.asyncio
async def test_unknown_bound_user(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value=None))
    monkeypatch.setattr(knowledge_tools, "get_connection", lambda: _ConnCtx(conn))

    err = await knowledge_tools._check_item_access(
        _kb(scope="personal", owner="jayho"), 99, "read"
    )
    assert "找不到" in err
