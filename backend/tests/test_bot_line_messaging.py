"""bot_line.messaging 測試。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from linebot.v3.messaging import TextMessage, TextMessageV2

from ching_tech_os.services.bot_line import messaging


class _FakeApi:
    def __init__(self) -> None:
        self.reply_calls = []
        self.push_calls = []
        self.reply_error = None
        self.push_error = None

    async def reply_message(self, req):
        self.reply_calls.append(req)
        if self.reply_error:
            raise self.reply_error
        return SimpleNamespace(sent_messages=[SimpleNamespace(id="r1"), SimpleNamespace(id="r2")])

    async def push_message(self, req):
        self.push_calls.append(req)
        if self.push_error:
            raise self.push_error
        return SimpleNamespace(sent_messages=[SimpleNamespace(id="p1"), SimpleNamespace(id="p2")])


@pytest.mark.asyncio
async def test_reply_and_create_text_message(monkeypatch: pytest.MonkeyPatch) -> None:
    api = _FakeApi()
    monkeypatch.setattr(messaging, "get_messaging_api", AsyncMock(return_value=api))

    msg_id = await messaging.reply_text("token", "hello")
    assert msg_id == "r1"

    mentioned = messaging.create_text_message_with_mention("hi", mention_user_id="U-1")
    plain = messaging.create_text_message_with_mention("hi", mention_user_id=None)
    assert isinstance(mentioned, TextMessageV2)
    assert isinstance(plain, TextMessage)

    # reply_text 失敗
    api.reply_error = RuntimeError("reply failed")
    assert await messaging.reply_text("token", "hello") is None


@pytest.mark.asyncio
async def test_reply_messages_and_push_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    api = _FakeApi()
    monkeypatch.setattr(messaging, "get_messaging_api", AsyncMock(return_value=api))

    empty = await messaging.reply_messages("token", [])
    assert empty == []

    sent_ids = await messaging.reply_messages(
        "token",
        [TextMessage(text="a"), TextMessage(text="b"), TextMessage(text="c"), TextMessage(text="d"), TextMessage(text="e"), TextMessage(text="f")],
    )
    assert sent_ids == ["r1", "r2"]
    assert len(api.reply_calls[-1].messages) == 5

    api.reply_error = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        await messaging.reply_messages("token", [TextMessage(text="x")])

    api.reply_error = None
    push_text_id, push_text_err = await messaging.push_text("U-1", "hello")
    assert push_text_id == "p1"
    assert push_text_err is None

    push_image_id, push_image_err = await messaging.push_image("U-1", "https://img")
    assert push_image_id == "p1"
    assert push_image_err is None

    ids, err = await messaging.push_messages("U-1", [TextMessage(text=f"m{i}") for i in range(7)])
    assert len(ids) == 4  # 兩批，每批 fake 回 2 個
    assert err is None

    # push_text / push_image 無 sent_messages
    async def _empty_push(_req):
        return SimpleNamespace(sent_messages=[])

    api.push_message = _empty_push
    no_id, no_err = await messaging.push_text("U-1", "x")
    assert no_id is None and "未知錯誤" in (no_err or "")
    no_img_id, no_img_err = await messaging.push_image("U-1", "https://img")
    assert no_img_id is None and "未知錯誤" in (no_img_err or "")

    # push_messages 部分成功與完全失敗
    class _PartialApi(_FakeApi):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def push_message(self, req):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(sent_messages=[SimpleNamespace(id="ok1")])
            raise RuntimeError("quota limit")

    partial_api = _PartialApi()
    monkeypatch.setattr(messaging, "get_messaging_api", AsyncMock(return_value=partial_api))
    partial_ids, partial_err = await messaging.push_messages(
        "U-1",
        [TextMessage(text=f"m{i}") for i in range(6)],
    )
    assert partial_ids == ["ok1"]
    assert "部分訊息發送失敗" in (partial_err or "")

    class _FailApi(_FakeApi):
        async def push_message(self, req):
            raise RuntimeError("forbidden 403")

    fail_api = _FailApi()
    monkeypatch.setattr(messaging, "get_messaging_api", AsyncMock(return_value=fail_api))
    fail_ids, fail_err = await messaging.push_messages("U-1", [TextMessage(text="x")])
    assert fail_ids == []
    assert fail_err == "沒有推播權限"


def test_parse_line_error() -> None:
    assert messaging._parse_line_error(RuntimeError("quota limit")) == "已達本月推播上限"
    assert messaging._parse_line_error(RuntimeError("429 too many requests")) == "發送頻率過高，請稍後再試"
    assert messaging._parse_line_error(RuntimeError("forbidden 403")) == "沒有推播權限"
    assert messaging._parse_line_error(RuntimeError("400 user not found")) == "用戶已封鎖機器人或不存在"
    assert messaging._parse_line_error(RuntimeError("image url invalid")) == "圖片網址無法存取"
    assert "發送失敗" in messaging._parse_line_error(RuntimeError("other"))
