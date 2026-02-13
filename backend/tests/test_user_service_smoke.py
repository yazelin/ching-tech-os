"""user service smoke tests。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services import user as user_service


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _patch_conn(monkeypatch: pytest.MonkeyPatch, conn) -> None:
    monkeypatch.setattr(user_service, "get_connection", lambda: _ConnCtx(conn))


@pytest.mark.asyncio
async def test_user_basic_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(
        fetchrow=AsyncMock(side_effect=[{"id": 1}, {"id": 2, "username": "u"}, None, {"id": 3, "username": "u"}, None]),
        execute=AsyncMock(side_effect=["UPDATE 1", "UPDATE 0", "OK", "OK"]),
    )
    _patch_conn(monkeypatch, conn)

    assert await user_service.upsert_user("u") == 1
    assert (await user_service.get_user_by_username("u"))["id"] == 2
    assert await user_service.get_user_by_username("x") is None
    assert (await user_service.get_user_for_auth("u"))["id"] == 3
    assert await user_service.get_user_for_auth("x") is None
    assert await user_service.set_user_password(1, "hash") is True
    assert await user_service.set_user_password(1, "hash") is False
    await user_service.update_last_login(1)
    await user_service.clear_must_change_password(1)


@pytest.mark.asyncio
async def test_user_create_and_activate_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(
        fetchrow=AsyncMock(side_effect=[{"id": 10}, Exception("duplicate key"), {"id": 99, "username": "u"}]),
        execute=AsyncMock(side_effect=["UPDATE 1", "UPDATE 0", "UPDATE 1", "DELETE 1"]),
        fetch=AsyncMock(side_effect=[[{"id": 1}], [{"id": 2}], [{"id": 3}], [{"id": 4}]]),
    )
    _patch_conn(monkeypatch, conn)

    assert await user_service.create_user("u", "h", "U") == 10
    with pytest.raises(ValueError):
        await user_service.create_user("u", "h")
    assert await user_service.deactivate_user(1) is True
    assert await user_service.activate_user(1) is False
    assert len(await user_service.get_all_users(False)) == 1
    assert len(await user_service.get_all_users(True)) == 1
    assert len(await user_service.list_users(False)) == 1
    assert len(await user_service.list_users(True)) == 1
    assert (await user_service.get_user_by_id(9))["id"] == 99
    assert await user_service.reset_user_password(1, "h", True) is True
    assert await user_service.delete_user(1) is True


@pytest.mark.asyncio
async def test_user_preferences_and_permissions(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(
        fetchrow=AsyncMock(
            side_effect=[
                None,  # update_user_permissions not found
                {"preferences": '{"permissions":{"apps":{"a":true}}}'},  # read existing
                {"preferences": {"permissions": {"apps": {"a": True, "b": False}}}},  # update return
                {"preferences": {"theme": "light"}},  # get_user_preferences
                {"role": "admin", "preferences": {"permissions": {"apps": {"x": True}}}},  # role+perm
                None,  # role+perm missing
                {"preferences": {"theme": "blue"}},  # update_user_preferences
                None,  # update_user_preferences fallback
            ]
        ),
    )
    _patch_conn(monkeypatch, conn)

    with pytest.raises(ValueError):
        await user_service.update_user_permissions(1, {"apps": {"x": True}})
    merged = await user_service.update_user_permissions(1, {"apps": {"b": False}})
    assert merged["permissions"]["apps"]["a"] is True
    assert (await user_service.get_user_preferences(1))["theme"] == "light"
    info = await user_service.get_user_role_and_permissions(1)
    assert info["role"] == "admin"
    assert (await user_service.get_user_role_and_permissions(2))["role"] == "user"
    assert (await user_service.update_user_preferences(1, {"theme": "x"}))["theme"] == "blue"
    assert (await user_service.update_user_preferences(1, {"theme": "x"}))["theme"] == "dark"

    # _parse_preferences 分支
    assert user_service._parse_preferences(None)["theme"] == "dark"
    assert user_service._parse_preferences({"x": 1})["x"] == 1
    assert user_service._parse_preferences('{"x":2}')["x"] == 2
    assert user_service._parse_preferences("{bad}")["theme"] == "dark"


@pytest.mark.asyncio
async def test_user_update_info_and_role(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(
        fetchrow=AsyncMock(
            side_effect=[
                {"id": 1},  # exists
                {"id": 1, "username": "u"},  # updated row
                None,  # not exists
                {"id": 1},  # exists for no-update
                {"role": "admin"},  # get_user_role
                {"role": None},  # get_user_role fallback
                None,  # get_user_role missing
            ]
        )
    )
    _patch_conn(monkeypatch, conn)

    with pytest.raises(ValueError):
        await user_service.update_user_info(1, role="bad")

    assert (await user_service.update_user_info(1, display_name="D", email="E", role="admin"))["id"] == 1
    assert await user_service.update_user_info(2, display_name="D") is None

    monkeypatch.setattr(user_service, "get_user_detail", AsyncMock(return_value={"id": 1, "username": "u", "display_name": "x"}))
    assert (await user_service.update_user_info(1))["id"] == 1

    assert await user_service.get_user_role(None) == "user"
    assert await user_service.get_user_role(1) == "admin"
    assert await user_service.get_user_role(2) == "user"
    assert await user_service.get_user_role(3) == "user"
