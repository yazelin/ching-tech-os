"""permissions 模組延伸測試。"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from ching_tech_os.models.auth import SessionData
from ching_tech_os.services import permissions


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _session(role: str = "user", app_permissions: dict[str, bool] | None = None) -> SessionData:
    now = datetime.now()
    return SessionData(
        username="u1",
        password="pw",
        nas_host="h",
        user_id=1,
        role=role,
        app_permissions=app_permissions or {},
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_user_app_permissions_db_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[
        None,  # not found
        {"role": "admin", "preferences": {}},
        {"role": "user", "preferences": {"permissions": {"apps": {"terminal": True}}}},
    ])
    monkeypatch.setattr(permissions, "get_connection", lambda: _CM(conn))

    not_found = await permissions.get_user_app_permissions(1)
    assert not_found["file-manager"] is True
    admin_perms = await permissions.get_user_app_permissions(2)
    assert all(admin_perms.values()) is True
    user_perms = await permissions.get_user_app_permissions(3)
    assert user_perms["terminal"] is True

    assert permissions.get_user_app_permissions_sync("admin", None)["terminal"] is True
    assert permissions.get_user_app_permissions_sync(
        "user",
        {"preferences": {"permissions": {"apps": {"terminal": True}}}},
    )["terminal"] is True


def test_mcp_tool_permission_paths() -> None:
    all_tools = [
        "mcp__ching-tech-os__search_knowledge",
        "mcp__ching-tech-os__search_nas_files",
        "mcp__ching-tech-os__create_share_link",
    ]
    # admin 全放行
    assert permissions.get_mcp_tools_for_user("admin", None, all_tools) == all_tools

    # user 依 app 權限過濾（share_link 不需權限）
    perms = {"apps": {"knowledge-base": True, "file-manager": False}}
    filtered = permissions.get_mcp_tools_for_user("user", perms, all_tools)
    assert "mcp__ching-tech-os__search_knowledge" in filtered
    assert "mcp__ching-tech-os__search_nas_files" not in filtered
    assert "mcp__ching-tech-os__create_share_link" in filtered

    assert permissions.check_tool_permission("mcp__ching-tech-os__search_knowledge", "user", perms) is True
    assert permissions.check_tool_permission("mcp__ching-tech-os__search_nas_files", "user", perms) is False
    assert permissions.check_tool_permission("create_share_link", "user", perms) is True
    assert permissions.check_tool_permission("any", "admin", None) is True


@pytest.mark.asyncio
async def test_project_member_and_async_knowledge_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    # 無參數
    assert await permissions.is_project_member(None, None) is False

    # DB 查詢 true / false
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=[1, None, RuntimeError("db down")])
    monkeypatch.setattr(permissions, "get_connection", lambda: _CM(conn))
    pid = "123e4567-e89b-12d3-a456-426614174000"
    assert await permissions.is_project_member(1, pid) is True
    assert await permissions.is_project_member(1, pid) is False
    assert await permissions.is_project_member(1, pid) is False  # exception -> False

    # async 權限（project scope）
    monkeypatch.setattr(permissions, "is_project_member", AsyncMock(side_effect=[True, False]))
    assert await permissions.check_knowledge_permission_async("user", "u1", None, None, "project", "read", user_id=1, project_id=pid) is True
    assert await permissions.check_knowledge_permission_async("user", "u1", None, None, "project", "write", user_id=1, project_id=pid) is True
    assert await permissions.check_knowledge_permission_async("user", "u1", None, None, "project", "delete", user_id=1, project_id=pid) is False


@pytest.mark.asyncio
async def test_require_app_permission_checker(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = permissions.require_app_permission("terminal")

    # admin 直接通過
    s_admin = _session("admin")
    assert (await checker(s_admin)).role == "admin"

    # session cache 命中
    s_cache = _session("user", app_permissions={"terminal": True})
    assert (await checker(s_cache)).username == "u1"

    # cache 空，走 has_app_permission
    monkeypatch.setattr(permissions, "has_app_permission", lambda _r, _p, _a: True)
    s_calc = _session("user", app_permissions={})
    assert (await checker(s_calc)).username == "u1"

    # 無權限
    monkeypatch.setattr(permissions, "has_app_permission", lambda _r, _p, _a: False)
    with pytest.raises(HTTPException) as e1:
        await checker(_session("user", app_permissions={}))
    assert e1.value.status_code == 403 and "終端機" in e1.value.detail
