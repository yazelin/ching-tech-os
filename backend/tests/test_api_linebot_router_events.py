"""linebot_router 事件流程測試。"""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException

from ching_tech_os.api import linebot_router
from ching_tech_os.models.auth import SessionData
from ching_tech_os.models.linebot import LineGroupUpdate, MemoryCreate, MemoryUpdate, ProjectBindingRequest


class _TextMessage:
    def __init__(self, message_id: str, text: str, quoted_message_id: str | None = None) -> None:
        self.id = message_id
        self.text = text
        self.quoted_message_id = quoted_message_id


class _ImageMessage:
    def __init__(self, message_id: str) -> None:
        self.id = message_id


class _FileMessage:
    def __init__(self, message_id: str, file_name: str, file_size: int | None = None) -> None:
        self.id = message_id
        self.file_name = file_name
        self.file_size = file_size


class _VideoMessage:
    def __init__(self, message_id: str, duration: int = 1000) -> None:
        self.id = message_id
        self.duration = duration


class _AudioMessage:
    def __init__(self, message_id: str, duration: int = 800) -> None:
        self.id = message_id
        self.duration = duration


class _Source:
    def __init__(self, user_id: str | None = None, group_id: str | None = None) -> None:
        self.user_id = user_id
        self.group_id = group_id


class _Event:
    def __init__(self, message, source, reply_token: str | None = "reply-token") -> None:
        self.message = message
        self.source = source
        self.reply_token = reply_token


class _Request:
    def __init__(self, body: bytes) -> None:
        self._body = body

    async def body(self) -> bytes:
        return self._body


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _session() -> SessionData:
    now = _now()
    return SessionData(
        username="admin",
        password="pw",
        nas_host="nas.local",
        user_id=1,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role="admin",
        app_permissions={},
    )


def _group_data(group_id=None) -> dict:
    now = _now()
    gid = group_id or uuid4()
    return {
        "id": gid,
        "name": "群組A",
        "picture_url": None,
        "platform_type": "line",
        "platform_group_id": "G1",
        "member_count": 10,
        "project_id": None,
        "project_name": None,
        "is_active": True,
        "allow_ai_response": True,
        "joined_at": now,
        "left_at": None,
        "created_at": now,
        "updated_at": now,
    }


def _user_data(user_id=None) -> dict:
    now = _now()
    uid = user_id or uuid4()
    return {
        "id": uid,
        "display_name": "使用者A",
        "picture_url": None,
        "status_message": None,
        "language": "zh-TW",
        "platform_type": "line",
        "platform_user_id": "U1",
        "user_id": 1,
        "is_friend": True,
        "created_at": now,
        "updated_at": now,
        "bound_username": "admin",
        "bound_display_name": "管理員",
    }


def _message_data(group_id=None, user_id=None) -> dict:
    now = _now()
    return {
        "id": uuid4(),
        "message_id": "m1",
        "bot_user_id": user_id or uuid4(),
        "user_display_name": "使用者A",
        "user_picture_url": None,
        "bot_group_id": group_id,
        "message_type": "text",
        "content": "hello",
        "file_id": None,
        "file_info": None,
        "is_from_bot": False,
        "ai_processed": False,
        "created_at": now,
    }


def _file_data(group_id=None, user_id=None) -> dict:
    now = _now()
    return {
        "id": uuid4(),
        "message_id": uuid4(),
        "file_type": "image",
        "file_name": "圖檔.png",
        "file_size": 123,
        "mime_type": None,
        "nas_path": "nas/圖檔.png",
        "thumbnail_path": None,
        "duration": None,
        "created_at": now,
        "bot_group_id": group_id,
        "bot_user_id": user_id,
        "user_display_name": "使用者A",
        "group_name": "群組A",
    }


def _memory_data() -> dict:
    now = _now()
    return {
        "id": uuid4(),
        "title": "記憶",
        "content": "內容",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "created_by": None,
        "created_by_name": None,
    }


@pytest.mark.asyncio
async def test_process_event_dispatch_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    MessageEvent = type("MessageEvent", (), {})
    JoinEvent = type("JoinEvent", (), {})
    LeaveEvent = type("LeaveEvent", (), {})
    FollowEvent = type("FollowEvent", (), {})
    UnfollowEvent = type("UnfollowEvent", (), {})

    monkeypatch.setattr(linebot_router, "MessageEvent", MessageEvent)
    monkeypatch.setattr(linebot_router, "JoinEvent", JoinEvent)
    monkeypatch.setattr(linebot_router, "LeaveEvent", LeaveEvent)
    monkeypatch.setattr(linebot_router, "FollowEvent", FollowEvent)
    monkeypatch.setattr(linebot_router, "UnfollowEvent", UnfollowEvent)

    process_message_event = AsyncMock()
    process_join_event = AsyncMock()
    process_leave_event = AsyncMock()
    process_follow_event = AsyncMock()
    process_unfollow_event = AsyncMock()
    monkeypatch.setattr(linebot_router, "process_message_event", process_message_event)
    monkeypatch.setattr(linebot_router, "process_join_event", process_join_event)
    monkeypatch.setattr(linebot_router, "process_leave_event", process_leave_event)
    monkeypatch.setattr(linebot_router, "process_follow_event", process_follow_event)
    monkeypatch.setattr(linebot_router, "process_unfollow_event", process_unfollow_event)

    await linebot_router.process_event(MessageEvent())
    await linebot_router.process_event(JoinEvent())
    await linebot_router.process_event(LeaveEvent())
    await linebot_router.process_event(FollowEvent())
    await linebot_router.process_event(UnfollowEvent())
    await linebot_router.process_event(object())
    process_message_event.assert_awaited_once()
    process_join_event.assert_awaited_once()
    process_leave_event.assert_awaited_once()
    process_follow_event.assert_awaited_once()
    process_unfollow_event.assert_awaited_once()

    monkeypatch.setattr(linebot_router, "process_message_event", AsyncMock(side_effect=RuntimeError("boom")))
    await linebot_router.process_event(MessageEvent())


@pytest.mark.asyncio
async def test_process_message_event_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linebot_router, "TextMessageContent", _TextMessage)
    monkeypatch.setattr(linebot_router, "ImageMessageContent", _ImageMessage)
    monkeypatch.setattr(linebot_router, "FileMessageContent", _FileMessage)

    get_user_profile = AsyncMock(return_value={"displayName": "U"})
    get_group_profile = AsyncMock(return_value={"groupName": "G"})
    get_or_create_user = AsyncMock(return_value=uuid4())
    get_or_create_group = AsyncMock(return_value=uuid4())
    save_message = AsyncMock(return_value=uuid4())
    process_media_message = AsyncMock()
    check_line_access = AsyncMock(return_value=(True, None))
    handle_text_message = AsyncMock()
    reply_text = AsyncMock()

    monkeypatch.setattr(linebot_router, "get_user_profile", get_user_profile)
    monkeypatch.setattr(linebot_router, "get_group_profile", get_group_profile)
    monkeypatch.setattr(linebot_router, "get_or_create_user", get_or_create_user)
    monkeypatch.setattr(linebot_router, "get_or_create_group", get_or_create_group)
    monkeypatch.setattr(linebot_router, "save_message", save_message)
    monkeypatch.setattr(linebot_router, "process_media_message", process_media_message)
    monkeypatch.setattr(linebot_router, "check_line_access", check_line_access)
    monkeypatch.setattr(linebot_router, "handle_text_message", handle_text_message)
    monkeypatch.setattr(linebot_router, "reply_text", reply_text)
    monkeypatch.setattr(linebot_router, "is_binding_code_format", AsyncMock(return_value=False))
    monkeypatch.setattr(linebot_router, "verify_binding_code", AsyncMock(return_value=(True, "ok")))

    # 無 user_id 直接返回
    await linebot_router.process_message_event(
        _Event(
            message=_TextMessage("m-no-user", "hello"),
            source=SimpleNamespace(),
        )
    )
    save_message.assert_not_called()

    # 個人對話：綁定碼流程
    save_message.reset_mock()
    monkeypatch.setattr(linebot_router, "is_binding_code_format", AsyncMock(return_value=True))
    await linebot_router.process_message_event(
        _Event(
            message=_TextMessage("m-bind", "123456"),
            source=_Source(user_id="U1"),
        )
    )
    reply_text.assert_awaited()
    save_message.assert_not_called()

    # 個人對話：未綁定拒絕
    reply_text.reset_mock()
    handle_text_message.reset_mock()
    save_message.reset_mock()
    monkeypatch.setattr(linebot_router, "is_binding_code_format", AsyncMock(return_value=False))
    monkeypatch.setattr(linebot_router, "check_line_access", AsyncMock(return_value=(False, "user_not_bound")))
    await linebot_router.process_message_event(
        _Event(
            message=_TextMessage("m-deny", "hello"),
            source=_Source(user_id="U1"),
        )
    )
    save_message.assert_awaited_once()
    reply_text.assert_awaited_once()
    handle_text_message.assert_not_called()

    # 群組對話：允許，觸發 AI
    save_message.reset_mock()
    handle_text_message.reset_mock()
    monkeypatch.setattr(linebot_router, "check_line_access", AsyncMock(return_value=(True, None)))
    await linebot_router.process_message_event(
        _Event(
            message=_TextMessage("m-allow", "@bot hi", quoted_message_id="q1"),
            source=_Source(user_id="U1", group_id="G1"),
        )
    )
    save_message.assert_awaited_once()
    handle_text_message.assert_awaited_once()
    assert handle_text_message.await_args.kwargs["line_group_id"] == get_or_create_group.return_value

    # 媒體訊息：交由 process_media_message
    process_media_message.reset_mock()
    await linebot_router.process_message_event(
        _Event(
            message=_ImageMessage("m-img"),
            source=_Source(user_id="U1", group_id="G1"),
        )
    )
    process_media_message.assert_awaited_once()

    process_media_message.reset_mock()
    await linebot_router.process_message_event(
        _Event(
            message=_FileMessage("m-file", "video.mp4", 123),
            source=_Source(user_id="U1", group_id="G1"),
        )
    )
    process_media_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_media_and_user_group_events(monkeypatch: pytest.MonkeyPatch) -> None:
    save_file_record = AsyncMock()
    monkeypatch.setattr(linebot_router, "download_and_save_file", AsyncMock(return_value="groups/g1/videos/x.mp4"))
    monkeypatch.setattr(linebot_router, "save_file_record", save_file_record)

    await linebot_router.process_media_message(
        message_id="m1",
        message_uuid=uuid4(),
        message_type="file",
        line_group_id="G1",
        line_user_id="U1",
        file_name="movie.mp4",
        file_size=100,
        duration=10,
    )
    assert save_file_record.await_args.kwargs["file_type"] == "video"

    monkeypatch.setattr(linebot_router, "download_and_save_file", AsyncMock(side_effect=RuntimeError("fail")))
    await linebot_router.process_media_message(
        message_id="m2",
        message_uuid=uuid4(),
        message_type="image",
        line_group_id="G1",
        line_user_id="U1",
    )

    join = AsyncMock()
    leave = AsyncMock()
    get_user_profile = AsyncMock(return_value={"displayName": "U"})
    get_or_create_user = AsyncMock(return_value=uuid4())
    update_friend = AsyncMock()
    monkeypatch.setattr(linebot_router, "handle_join_event", join)
    monkeypatch.setattr(linebot_router, "handle_leave_event", leave)
    monkeypatch.setattr(linebot_router, "get_user_profile", get_user_profile)
    monkeypatch.setattr(linebot_router, "get_or_create_user", get_or_create_user)
    monkeypatch.setattr(linebot_router, "update_user_friend_status", update_friend)

    await linebot_router.process_join_event(SimpleNamespace(source=_Source(group_id="G1")))
    await linebot_router.process_leave_event(SimpleNamespace(source=_Source(group_id="G1")))
    await linebot_router.process_follow_event(SimpleNamespace(source=_Source(user_id="U1")))
    await linebot_router.process_unfollow_event(SimpleNamespace(source=_Source(user_id="U1")))
    await linebot_router.process_join_event(SimpleNamespace(source=SimpleNamespace()))
    await linebot_router.process_leave_event(SimpleNamespace(source=SimpleNamespace()))
    await linebot_router.process_follow_event(SimpleNamespace(source=SimpleNamespace()))
    await linebot_router.process_unfollow_event(SimpleNamespace(source=SimpleNamespace()))

    join.assert_awaited_once()
    leave.assert_awaited_once()
    assert update_friend.await_count == 2


@pytest.mark.asyncio
async def test_webhook_and_message_event_extra_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    # webhook: invalid signature
    monkeypatch.setattr(linebot_router, "verify_webhook_signature", AsyncMock(return_value=(False, None, None)))
    with pytest.raises(HTTPException) as invalid_exc:
        await linebot_router.webhook(
            request=_Request(b'{"events": []}'),
            background_tasks=BackgroundTasks(),
            x_line_signature="sig",
        )
    assert invalid_exc.value.status_code == 400

    # webhook: parser error
    monkeypatch.setattr(linebot_router, "verify_webhook_signature", AsyncMock(return_value=(True, None, "secret")))

    class _BadParser:
        def parse(self, *_args, **_kwargs):
            raise ValueError("bad body")

    monkeypatch.setattr(linebot_router, "get_webhook_parser", lambda _secret: _BadParser())
    with pytest.raises(HTTPException) as parse_exc:
        await linebot_router.webhook(
            request=_Request(b"not-json"),
            background_tasks=BackgroundTasks(),
            x_line_signature="sig",
        )
    assert parse_exc.value.status_code == 400

    # webhook: success add tasks
    class _OkParser:
        def parse(self, *_args, **_kwargs):
            return [object(), object()]

    monkeypatch.setattr(linebot_router, "get_webhook_parser", lambda _secret: _OkParser())
    tasks = BackgroundTasks()
    result = await linebot_router.webhook(
        request=_Request(b'{"events": []}'),
        background_tasks=tasks,
        x_line_signature="sig",
    )
    assert result == {"status": "ok"}
    assert len(tasks.tasks) == 2

    monkeypatch.setattr(linebot_router, "TextMessageContent", _TextMessage)
    monkeypatch.setattr(linebot_router, "VideoMessageContent", _VideoMessage)
    monkeypatch.setattr(linebot_router, "AudioMessageContent", _AudioMessage)
    monkeypatch.setattr(linebot_router, "FileMessageContent", _FileMessage)
    monkeypatch.setattr(linebot_router, "ImageMessageContent", _ImageMessage)
    monkeypatch.setattr(linebot_router, "reply_text", AsyncMock(side_effect=RuntimeError("reply fail")))
    monkeypatch.setattr(linebot_router, "is_binding_code_format", AsyncMock(return_value=True))
    monkeypatch.setattr(linebot_router, "verify_binding_code", AsyncMock(return_value=(True, "ok")))
    monkeypatch.setattr(linebot_router, "get_user_profile", AsyncMock(return_value={"displayName": "U"}))
    monkeypatch.setattr(linebot_router, "get_group_profile", AsyncMock(return_value={"groupName": "G"}))
    monkeypatch.setattr(linebot_router, "get_or_create_user", AsyncMock(return_value=uuid4()))
    monkeypatch.setattr(linebot_router, "get_or_create_group", AsyncMock(return_value=uuid4()))
    save_message = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(linebot_router, "save_message", save_message)
    monkeypatch.setattr(linebot_router, "process_media_message", AsyncMock())
    monkeypatch.setattr(linebot_router, "check_line_access", AsyncMock(return_value=(True, None)))
    monkeypatch.setattr(linebot_router, "handle_text_message", AsyncMock())

    # 綁定碼回覆失敗分支（不應拋例外）
    await linebot_router.process_message_event(
        _Event(
            message=_TextMessage("m-bind", "123456"),
            source=_Source(user_id="U1"),
        )
    )
    save_message.assert_not_called()

    # group_not_allowed 靜默分支
    monkeypatch.setattr(linebot_router, "is_binding_code_format", AsyncMock(return_value=False))
    monkeypatch.setattr(linebot_router, "check_line_access", AsyncMock(return_value=(False, "group_not_allowed")))
    await linebot_router.process_message_event(
        _Event(
            message=_TextMessage("m-deny-group", "hello"),
            source=_Source(user_id="U1", group_id="G1"),
        )
    )
    assert linebot_router.handle_text_message.await_count == 0

    monkeypatch.setattr(linebot_router, "check_line_access", AsyncMock(return_value=(False, "user_not_bound")))
    await linebot_router.process_message_event(
        _Event(
            message=_TextMessage("m-deny-personal", "hello"),
            source=_Source(user_id="U1"),
        )
    )

    # video/audio/unknown 類型
    await linebot_router.process_message_event(
        _Event(message=_VideoMessage("m-video"), source=_Source(user_id="U1", group_id="G1"))
    )
    await linebot_router.process_message_event(
        _Event(message=_AudioMessage("m-audio"), source=_Source(user_id="U1", group_id="G1"))
    )
    await linebot_router.process_message_event(
        _Event(message=SimpleNamespace(id="m-unknown"), source=_Source(user_id="U1", group_id="G1"))
    )
    assert linebot_router.process_media_message.await_count >= 2


@pytest.mark.asyncio
async def test_process_media_audio_and_image_reclassify(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linebot_router, "download_and_save_file", AsyncMock(return_value="nas/path"))
    save_file_record = AsyncMock()
    monkeypatch.setattr(linebot_router, "save_file_record", save_file_record)

    await linebot_router.process_media_message(
        message_id="m-audio",
        message_uuid=uuid4(),
        message_type="file",
        line_group_id="G1",
        line_user_id="U1",
        file_name="voice.mp3",
        file_size=100,
    )
    await linebot_router.process_media_message(
        message_id="m-image",
        message_uuid=uuid4(),
        message_type="file",
        line_group_id="G1",
        line_user_id="U1",
        file_name="photo.jpg",
        file_size=200,
    )

    assert save_file_record.await_args_list[0].kwargs["file_type"] == "audio"
    assert save_file_record.await_args_list[1].kwargs["file_type"] == "image"


@pytest.mark.asyncio
async def test_linebot_router_admin_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    group_id = uuid4()
    user_id = uuid4()
    file_id = uuid4()

    group = _group_data(group_id)
    user = _user_data(user_id)
    message = _message_data(group_id=group_id, user_id=user_id)
    file_info = _file_data(group_id=group_id, user_id=user_id)

    monkeypatch.setattr(linebot_router, "list_groups", AsyncMock(return_value=([group], 1)))
    list_groups_resp = await linebot_router.api_list_groups(session=session)
    assert list_groups_resp.total == 1

    monkeypatch.setattr(linebot_router, "get_group_by_id", AsyncMock(return_value=group))
    get_group_resp = await linebot_router.api_get_group(group_id=group_id, session=session)
    assert get_group_resp.id == group_id
    monkeypatch.setattr(linebot_router, "get_group_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_get_group(group_id=group_id, session=session)

    monkeypatch.setattr(linebot_router, "bind_group_to_project", AsyncMock(return_value=True))
    bind_resp = await linebot_router.api_bind_project(
        group_id=group_id,
        request=ProjectBindingRequest(project_id=uuid4()),
        session=session,
    )
    assert bind_resp["status"] == "ok"
    monkeypatch.setattr(linebot_router, "bind_group_to_project", AsyncMock(return_value=False))
    with pytest.raises(HTTPException):
        await linebot_router.api_bind_project(
            group_id=group_id,
            request=ProjectBindingRequest(project_id=uuid4()),
            session=session,
        )

    monkeypatch.setattr(linebot_router, "unbind_group_from_project", AsyncMock(return_value=True))
    unbind_resp = await linebot_router.api_unbind_project(group_id=group_id, session=session)
    assert unbind_resp["status"] == "ok"
    monkeypatch.setattr(linebot_router, "unbind_group_from_project", AsyncMock(return_value=False))
    with pytest.raises(HTTPException):
        await linebot_router.api_unbind_project(group_id=group_id, session=session)

    monkeypatch.setattr(
        linebot_router,
        "delete_group",
        AsyncMock(return_value={"group_name": "群組A", "deleted_messages": 3}),
    )
    delete_group_resp = await linebot_router.api_delete_group(group_id=group_id, session=session)
    assert delete_group_resp["deleted_messages"] == 3
    monkeypatch.setattr(linebot_router, "delete_group", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_delete_group(group_id=group_id, session=session)

    monkeypatch.setattr(linebot_router, "list_users", AsyncMock(return_value=([user], 1)))
    list_users_resp = await linebot_router.api_list_users(session=session)
    assert list_users_resp.total == 1

    monkeypatch.setattr(linebot_router, "get_user_by_id", AsyncMock(return_value=user))
    get_user_resp = await linebot_router.api_get_user(user_id=user_id, session=session)
    assert get_user_resp.id == user_id
    monkeypatch.setattr(linebot_router, "get_user_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_get_user(user_id=user_id, session=session)

    monkeypatch.setattr(linebot_router, "list_messages", AsyncMock(return_value=([message], 1)))
    list_message_resp = await linebot_router.api_list_messages(session=session, page=2, page_size=10)
    assert list_message_resp.page == 2

    monkeypatch.setattr(linebot_router, "list_files", AsyncMock(return_value=([file_info], 1)))
    list_group_files_resp = await linebot_router.api_list_group_files(group_id=group_id, session=session)
    assert list_group_files_resp.total == 1
    list_files_resp = await linebot_router.api_list_files(session=session, page=2, page_size=5)
    assert list_files_resp.total == 1

    monkeypatch.setattr(linebot_router, "get_file_by_id", AsyncMock(return_value=file_info))
    get_file_resp = await linebot_router.api_get_file(file_id=file_id, session=session)
    assert get_file_resp.file_name == "圖檔.png"
    monkeypatch.setattr(linebot_router, "get_file_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_get_file(file_id=file_id, session=session)

    monkeypatch.setattr(linebot_router, "get_file_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_download_file(file_id=file_id, session=session)

    monkeypatch.setattr(linebot_router, "get_file_by_id", AsyncMock(return_value={"file_type": "image"}))
    with pytest.raises(HTTPException):
        await linebot_router.api_download_file(file_id=file_id, session=session)

    monkeypatch.setattr(
        linebot_router,
        "get_file_by_id",
        AsyncMock(return_value={"nas_path": "nas/a.jpg", "file_type": "image"}),
    )
    monkeypatch.setattr(linebot_router, "read_file_from_nas", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_download_file(file_id=file_id, session=session)

    monkeypatch.setattr(
        linebot_router,
        "get_file_by_id",
        AsyncMock(return_value={"nas_path": "nas/聲音檔.m4a", "file_type": "audio", "mime_type": None, "file_name": None}),
    )
    monkeypatch.setattr(linebot_router, "read_file_from_nas", AsyncMock(return_value=b"abc"))
    download_resp = await linebot_router.api_download_file(file_id=file_id, session=session)
    assert download_resp.media_type == "audio/m4a"
    assert "filename*=UTF-8''" in download_resp.headers["Content-Disposition"]

    monkeypatch.setattr(linebot_router, "delete_file", AsyncMock(return_value=True))
    delete_file_resp = await linebot_router.api_delete_file(file_id=file_id, session=session)
    assert delete_file_resp["status"] == "ok"
    monkeypatch.setattr(linebot_router, "delete_file", AsyncMock(return_value=False))
    with pytest.raises(HTTPException):
        await linebot_router.api_delete_file(file_id=file_id, session=session)

    now = _now()
    monkeypatch.setattr(linebot_router, "generate_binding_code", AsyncMock(return_value=("123456", now)))
    code_resp = await linebot_router.api_generate_binding_code(session=session, platform_type="line")
    assert code_resp.code == "123456"

    monkeypatch.setattr(
        linebot_router,
        "get_binding_status",
        AsyncMock(
            return_value={
                "is_bound": True,
                "line_display_name": "LineUser",
                "line_picture_url": None,
                "bound_at": now,
                "line": {"is_bound": True, "display_name": "LineUser", "picture_url": None, "bound_at": now},
                "telegram": {"is_bound": False, "display_name": None, "picture_url": None, "bound_at": None},
            }
        ),
    )
    status_resp = await linebot_router.api_get_binding_status(session=session)
    assert status_resp.is_bound is True

    monkeypatch.setattr(linebot_router, "unbind_line_user", AsyncMock(return_value=False))
    with pytest.raises(HTTPException):
        await linebot_router.api_unbind_line(session=session, platform_type="line")

    monkeypatch.setattr(linebot_router, "unbind_line_user", AsyncMock(return_value=True))
    assert "Line" in (await linebot_router.api_unbind_line(session=session, platform_type="line"))["message"]
    assert "Telegram" in (await linebot_router.api_unbind_line(session=session, platform_type="telegram"))["message"]
    assert "所有平台" in (await linebot_router.api_unbind_line(session=session, platform_type=None))["message"]

    monkeypatch.setattr(linebot_router, "get_group_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_update_group(group_id=group_id, update=LineGroupUpdate(allow_ai_response=True), session=session)

    monkeypatch.setattr(
        linebot_router,
        "get_group_by_id",
        AsyncMock(side_effect=[group, group]),
    )
    monkeypatch.setattr(linebot_router, "update_group_settings", AsyncMock(return_value=False))
    with pytest.raises(HTTPException):
        await linebot_router.api_update_group(group_id=group_id, update=LineGroupUpdate(allow_ai_response=True), session=session)

    monkeypatch.setattr(
        linebot_router,
        "get_group_by_id",
        AsyncMock(side_effect=[group, group]),
    )
    monkeypatch.setattr(linebot_router, "update_group_settings", AsyncMock(return_value=True))
    update_resp = await linebot_router.api_update_group(
        group_id=group_id,
        update=LineGroupUpdate(allow_ai_response=True),
        session=session,
    )
    assert update_resp.id == group_id

    monkeypatch.setattr(
        linebot_router,
        "get_group_by_id",
        AsyncMock(side_effect=[group, group]),
    )
    no_change_resp = await linebot_router.api_update_group(
        group_id=group_id,
        update=LineGroupUpdate(),
        session=session,
    )
    assert no_change_resp.id == group_id

    monkeypatch.setattr(linebot_router, "list_users_with_binding", AsyncMock(return_value=([user], 1)))
    users_binding_resp = await linebot_router.api_list_users_with_binding(session=session)
    assert users_binding_resp.total == 1


@pytest.mark.asyncio
async def test_linebot_router_memory_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    group_id = uuid4()
    user_id = uuid4()
    memory_id = uuid4()
    group = _group_data(group_id)
    user = _user_data(user_id)
    memory_data = _memory_data()

    bot_line_module = importlib.import_module("ching_tech_os.services.bot_line")

    monkeypatch.setattr(linebot_router, "get_group_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_list_group_memories(group_id=group_id, session=session)

    monkeypatch.setattr(linebot_router, "get_group_by_id", AsyncMock(return_value=group))
    monkeypatch.setattr(bot_line_module, "list_group_memories", AsyncMock(return_value=([memory_data], 1)))
    list_group_mem = await linebot_router.api_list_group_memories(group_id=group_id, session=session)
    assert list_group_mem.total == 1

    monkeypatch.setattr(linebot_router, "get_group_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_create_group_memory(
            group_id=group_id,
            memory=MemoryCreate(title="t", content="c"),
            session=session,
        )

    monkeypatch.setattr(linebot_router, "get_group_by_id", AsyncMock(return_value=group))
    monkeypatch.setattr(bot_line_module, "get_line_user_by_ctos_user", AsyncMock(return_value={"id": uuid4()}))
    monkeypatch.setattr(bot_line_module, "create_group_memory", AsyncMock(return_value=memory_data))
    create_group_mem = await linebot_router.api_create_group_memory(
        group_id=group_id,
        memory=MemoryCreate(title="t", content="c"),
        session=session,
    )
    assert create_group_mem.title == "記憶"

    monkeypatch.setattr(linebot_router, "get_user_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_list_user_memories(user_id=user_id, session=session)

    monkeypatch.setattr(linebot_router, "get_user_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(bot_line_module, "list_user_memories", AsyncMock(return_value=([memory_data], 1)))
    list_user_mem = await linebot_router.api_list_user_memories(user_id=user_id, session=session)
    assert list_user_mem.total == 1

    monkeypatch.setattr(linebot_router, "get_user_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_create_user_memory(
            user_id=user_id,
            memory=MemoryCreate(title="t", content="c"),
            session=session,
        )

    monkeypatch.setattr(linebot_router, "get_user_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(bot_line_module, "create_user_memory", AsyncMock(return_value=memory_data))
    create_user_mem = await linebot_router.api_create_user_memory(
        user_id=user_id,
        memory=MemoryCreate(title="t", content="c"),
        session=session,
    )
    assert create_user_mem.content == "內容"

    monkeypatch.setattr(bot_line_module, "update_memory", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await linebot_router.api_update_memory(
            memory_id=memory_id,
            memory=MemoryUpdate(title="new"),
            session=session,
        )

    monkeypatch.setattr(bot_line_module, "update_memory", AsyncMock(return_value=memory_data))
    update_mem = await linebot_router.api_update_memory(
        memory_id=memory_id,
        memory=MemoryUpdate(title="new"),
        session=session,
    )
    assert update_mem.id == memory_data["id"]

    monkeypatch.setattr(bot_line_module, "delete_memory", AsyncMock(return_value=False))
    with pytest.raises(HTTPException):
        await linebot_router.api_delete_memory(memory_id=memory_id, session=session)

    monkeypatch.setattr(bot_line_module, "delete_memory", AsyncMock(return_value=True))
    delete_mem = await linebot_router.api_delete_memory(memory_id=memory_id, session=session)
    assert delete_mem["status"] == "ok"
