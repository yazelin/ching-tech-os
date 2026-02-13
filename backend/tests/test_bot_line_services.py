"""bot_line 服務模組測試。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.services.bot_line import admin, binding, group_manager, message_store, user_manager, webhook


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_admin_services(monkeypatch: pytest.MonkeyPatch) -> None:
    gid = uuid4()
    uid = uuid4()

    # list_groups
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=2)
    conn.fetch = AsyncMock(return_value=[{"id": gid, "name": "g"}])
    monkeypatch.setattr(admin, "get_connection", lambda: _CM(conn))
    rows, total = await admin.list_groups(is_active=True, project_id=gid, platform_type="line")
    assert total == 2 and rows[0]["name"] == "g"

    # list_messages
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch = AsyncMock(return_value=[{"id": uuid4(), "content": "hello"}])
    monkeypatch.setattr(admin, "get_connection", lambda: _CM(conn))
    rows, total = await admin.list_messages(line_group_id=None, line_user_id=uid, platform_type="line")
    assert total == 1 and rows[0]["content"] == "hello"

    # list_users / get by id
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch = AsyncMock(return_value=[{"id": uid, "display_name": "u"}])
    conn.fetchrow = AsyncMock(side_effect=[{"id": gid, "name": "g1"}, None, {"id": uid, "display_name": "u1"}, None])
    conn.execute = AsyncMock(side_effect=["UPDATE 1", "UPDATE 1", "UPDATE 1"])
    monkeypatch.setattr(admin, "get_connection", lambda: _CM(conn))
    users, total = await admin.list_users(platform_type="line")
    assert total == 1 and users[0]["display_name"] == "u"
    assert (await admin.get_group_by_id(gid))["name"] == "g1"
    assert await admin.get_group_by_id(uuid4()) is None
    assert (await admin.get_user_by_id(uid))["display_name"] == "u1"
    assert await admin.get_user_by_id(uuid4()) is None
    assert await admin.bind_group_to_project(gid, uuid4()) is True
    assert await admin.unbind_group_from_project(gid) is True
    assert await admin.update_group_settings(gid, True) is True

    # delete_group: 不存在 + 存在
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[None, {"id": gid, "name": "群組", "message_count": 3}])
    conn.execute = AsyncMock(return_value="DELETE 1")
    monkeypatch.setattr(admin, "get_connection", lambda: _CM(conn))
    assert await admin.delete_group(gid) is None
    deleted = await admin.delete_group(gid)
    assert deleted["deleted_messages"] == 3

    # list_users_with_binding
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch = AsyncMock(return_value=[{"id": uid, "bound_username": "u"}])
    monkeypatch.setattr(admin, "get_connection", lambda: _CM(conn))
    users, total = await admin.list_users_with_binding(platform_type="telegram")
    assert total == 1 and users[0]["bound_username"] == "u"


@pytest.mark.asyncio
async def test_binding_services(monkeypatch: pytest.MonkeyPatch) -> None:
    line_user_uuid = uuid4()

    # generate_binding_code
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="OK")
    monkeypatch.setattr(binding, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(binding.random, "randint", lambda _a, _b: 123456)
    code, _expires = await binding.generate_binding_code(1, "line")
    assert code == "123456"

    # verify_binding_code: code invalid
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    monkeypatch.setattr(binding, "get_connection", lambda: _CM(conn))
    ok, msg = await binding.verify_binding_code(line_user_uuid, "000000")
    assert ok is False and "無效" in msg

    # verify_binding_code: line user not found
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[
        {"id": 1, "user_id": 100},
        None,
    ])
    monkeypatch.setattr(binding, "get_connection", lambda: _CM(conn))
    ok, msg = await binding.verify_binding_code(line_user_uuid, "111111")
    assert ok is False and "找不到" in msg

    # verify_binding_code: Line 已綁定其他帳號
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[
        {"id": 1, "user_id": 100},  # code
        {"platform_user_id": "U1", "display_name": "A", "platform_type": "line"},  # line user
        {"id": line_user_uuid},  # has binding
        {"user_id": 999},  # existing_user
    ])
    monkeypatch.setattr(binding, "get_connection", lambda: _CM(conn))
    ok, msg = await binding.verify_binding_code(line_user_uuid, "222222")
    assert ok is False and "已綁定其他 CTOS 帳號" in msg

    # verify_binding_code: CTOS 已綁定其他同平台
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[
        {"id": 1, "user_id": 100},
        {"platform_user_id": "U1", "display_name": "A", "platform_type": "telegram"},
        None,  # line user 尚未綁定
        {"id": uuid4()},  # existing same platform
    ])
    monkeypatch.setattr(binding, "get_connection", lambda: _CM(conn))
    ok, msg = await binding.verify_binding_code(line_user_uuid, "333333")
    assert ok is False and "Telegram" in msg

    # verify_binding_code: success
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[
        {"id": 1, "user_id": 100},
        {"platform_user_id": "U1", "display_name": "A", "platform_type": "line"},
        None,  # line user 尚未綁定
        None,  # ctos 尚未綁定其他 line
    ])
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(binding, "get_connection", lambda: _CM(conn))
    ok, msg = await binding.verify_binding_code(line_user_uuid, "444444")
    assert ok is True and "綁定成功" in msg

    # unbind_line_user
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["UPDATE 0", "UPDATE 1"])
    monkeypatch.setattr(binding, "get_connection", lambda: _CM(conn))
    assert await binding.unbind_line_user(1, "line") is False
    assert await binding.unbind_line_user(1, None) is True

    # get_binding_status
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {"platform_type": "line", "display_name": "L", "picture_url": "p", "bound_at": None},
        {"platform_type": "telegram", "display_name": "T", "picture_url": None, "bound_at": None},
    ])
    monkeypatch.setattr(binding, "get_connection", lambda: _CM(conn))
    status = await binding.get_binding_status(1)
    assert status["is_bound"] is True and status["line"]["is_bound"] is True and status["telegram"]["is_bound"] is True

    assert await binding.is_binding_code_format("123456") is True
    assert await binding.is_binding_code_format("12ab56") is False

    # check_line_access
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[
        None,  # user not bound
        {"user_id": 10},  # user bound
        {"allow_ai_response": False},  # group blocked
        {"user_id": 10},  # user bound
        {"allow_ai_response": True},  # group allow
    ])
    monkeypatch.setattr(binding, "get_connection", lambda: _CM(conn))
    assert await binding.check_line_access(line_user_uuid) == (False, "user_not_bound")
    assert await binding.check_line_access(line_user_uuid, uuid4()) == (False, "group_not_allowed")
    assert await binding.check_line_access(line_user_uuid, uuid4()) == (True, None)


@pytest.mark.asyncio
async def test_group_and_user_managers(monkeypatch: pytest.MonkeyPatch) -> None:
    gid = uuid4()
    uid = uuid4()

    # group_manager.get_or_create_group：已存在/新建
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[{"id": gid}, None, {"id": gid}])
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(group_manager, "get_connection", lambda: _CM(conn))
    got = await group_manager.get_or_create_group("C1", {"groupName": "g"})
    assert got == gid
    created = await group_manager.get_or_create_group("C2", None)
    assert created == gid

    # group profile success / fail
    api = SimpleNamespace(
        get_group_summary=AsyncMock(return_value=SimpleNamespace(group_name="g", picture_url="u")),
        get_group_member_count=AsyncMock(return_value=SimpleNamespace(count=3)),
    )
    monkeypatch.setattr(group_manager, "get_messaging_api", AsyncMock(return_value=api))
    profile = await group_manager.get_group_profile("C1")
    assert profile["memberCount"] == 3
    monkeypatch.setattr(group_manager, "get_messaging_api", AsyncMock(side_effect=RuntimeError("x")))
    assert await group_manager.get_group_profile("C1") is None

    # handle join/leave & external id
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetchrow = AsyncMock(side_effect=[{"platform_group_id": "C99"}, None])
    monkeypatch.setattr(group_manager, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(group_manager, "get_group_profile", AsyncMock(return_value={"groupName": "g"}))
    monkeypatch.setattr(group_manager, "get_or_create_group", AsyncMock(return_value=gid))
    await group_manager.handle_join_event("C1")
    await group_manager.handle_leave_event("C1")
    assert await group_manager.get_line_group_external_id(gid) == "C99"
    assert await group_manager.get_line_group_external_id(uuid4()) is None

    # user_manager.get_line_user_record
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[{"id": uid, "display_name": "u"}, None])
    monkeypatch.setattr(user_manager, "get_connection", lambda: _CM(conn))
    assert (await user_manager.get_line_user_record("U1"))["display_name"] == "u"
    assert await user_manager.get_line_user_record("U2") is None

    # get_or_create_user 已存在與新建
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[{"id": uid}, None, {"id": uid}])
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(user_manager, "get_connection", lambda: _CM(conn))
    assert await user_manager.get_or_create_user("U1", {"displayName": "u"}) == uid
    assert await user_manager.get_or_create_user("U2", None, True) == uid

    # update_user_friend_status
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(user_manager, "get_connection", lambda: _CM(conn))
    assert await user_manager.update_user_friend_status("U1", True) is True

    # user/group profile API
    api = SimpleNamespace(
        get_profile=AsyncMock(return_value=SimpleNamespace(display_name="u", picture_url="p", status_message="s")),
        get_group_member_profile=AsyncMock(return_value=SimpleNamespace(display_name="m", picture_url="p2")),
    )
    monkeypatch.setattr(user_manager, "get_messaging_api", AsyncMock(return_value=api))
    assert (await user_manager.get_user_profile("U1"))["displayName"] == "u"
    assert (await user_manager.get_group_member_profile("C1", "U1"))["displayName"] == "m"
    monkeypatch.setattr(user_manager, "get_messaging_api", AsyncMock(side_effect=RuntimeError("x")))
    assert await user_manager.get_user_profile("U1") is None
    assert await user_manager.get_group_member_profile("C1", "U1") is None


@pytest.mark.asyncio
async def test_message_store_and_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    uid = uuid4()
    gid = uuid4()
    mid = uuid4()

    # save_message（群組）
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": mid})
    monkeypatch.setattr(message_store, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(message_store, "get_group_member_profile", AsyncMock(return_value={"displayName": "u"}))
    monkeypatch.setattr(message_store, "get_user_profile", AsyncMock(return_value={"displayName": "u"}))
    monkeypatch.setattr(message_store, "get_or_create_user", AsyncMock(return_value=uid))
    monkeypatch.setattr(message_store, "get_group_profile", AsyncMock(return_value={"groupName": "g"}))
    monkeypatch.setattr(message_store, "get_or_create_group", AsyncMock(return_value=gid))
    saved = await message_store.save_message("m1", "U1", "C1", "text", "hello")
    assert saved == mid

    # save_message（個人 + from bot）
    saved2 = await message_store.save_message("m2", "U1", None, "text", "hello", is_from_bot=True)
    assert saved2 == mid

    # mark_message_ai_processed
    await message_store.mark_message_ai_processed(mid)
    conn.execute.assert_awaited()

    # get_or_create_bot_user: 已存在 / 新建
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[{"id": uid}, None, {"id": uid}])
    conn.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(message_store, "get_connection", lambda: _CM(conn))
    assert await message_store.get_or_create_bot_user() == uid
    assert await message_store.get_or_create_bot_user() == uid

    # save_bot_response: 群組 / 個人 / fallback
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": mid})
    monkeypatch.setattr(message_store, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(message_store, "get_or_create_bot_user", AsyncMock(return_value=uid))
    monkeypatch.setattr(message_store, "get_or_create_user", AsyncMock(return_value=uid))
    assert await message_store.save_bot_response(gid, "ok") == mid
    assert await message_store.save_bot_response(None, "ok", responding_to_line_user_id="U1") == mid
    assert await message_store.save_bot_response(None, "ok") == mid

    # get_message_content_by_line_message_id
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[{"content": "x", "message_type": "text", "display_name": "u", "is_from_bot": False}, None])
    monkeypatch.setattr(message_store, "get_connection", lambda: _CM(conn))
    assert (await message_store.get_message_content_by_line_message_id("m1"))["content"] == "x"
    assert await message_store.get_message_content_by_line_message_id("m2") is None

    # webhook signature
    body = b'{"x":1}'
    monkeypatch.setattr(webhook.settings, "line_channel_secret", "secret")
    sig_ok = webhook.verify_signature(body, webhook.base64.b64encode(webhook.hmac.new(b"secret", body, webhook.hashlib.sha256).digest()).decode("utf-8"))
    assert sig_ok is True
    assert webhook.verify_signature(body, "bad-signature") is False
    assert (await webhook.verify_webhook_signature(body, "bad-signature"))[0] is False
    monkeypatch.setattr(webhook.settings, "line_channel_secret", "")
    assert webhook.verify_signature(body, "x") is False
