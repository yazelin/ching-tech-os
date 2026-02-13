"""linebot_router 事件流程測試。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.api import linebot_router


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


class _Source:
    def __init__(self, user_id: str | None = None, group_id: str | None = None) -> None:
        self.user_id = user_id
        self.group_id = group_id


class _Event:
    def __init__(self, message, source, reply_token: str | None = "reply-token") -> None:
        self.message = message
        self.source = source
        self.reply_token = reply_token


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
