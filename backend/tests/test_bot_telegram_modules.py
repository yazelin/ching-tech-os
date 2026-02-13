"""bot_telegram 模組測試。"""

from __future__ import annotations

import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services.bot_telegram import adapter, media, polling


class _FakePTBBot:
    def __init__(self, token=None, request=None) -> None:
        self.token = token
        self.request = request
        self.sent = []
        self._me = SimpleNamespace(username="ctos_bot")

    async def get_me(self):
        return self._me

    async def send_message(self, **kwargs):
        self.sent.append(("text", kwargs))
        return SimpleNamespace(message_id=101)

    async def send_photo(self, **kwargs):
        self.sent.append(("photo", kwargs))
        return SimpleNamespace(message_id=102)

    async def send_document(self, **kwargs):
        self.sent.append(("doc", kwargs))
        return SimpleNamespace(message_id=103)

    async def edit_message_text(self, **kwargs):
        self.sent.append(("edit", kwargs))

    async def delete_message(self, **kwargs):
        self.sent.append(("delete", kwargs))

    async def get_file(self, _fid):
        async def _download():
            return b"binary"

        return SimpleNamespace(download_as_bytearray=_download)


class _FakeAsyncClient:
    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, _url):
        class _Resp:
            content = b"file-bytes"

            def raise_for_status(self):
                return None

        return _Resp()


@pytest.mark.asyncio
async def test_telegram_adapter_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "Bot", _FakePTBBot)
    monkeypatch.setattr(adapter.httpx, "AsyncClient", _FakeAsyncClient)

    ad = adapter.TelegramBotAdapter(token="t1")
    assert ad.bot_username is None
    await ad.ensure_bot_info()
    assert ad.bot_username == "ctos_bot"

    sent1 = await ad.send_text("123", "hello", reply_to="9")
    sent2 = await ad.send_image("123", "https://img", reply_to="10")
    sent3 = await ad.send_file("123", "https://f", "a.txt", reply_to="11")
    batch = await ad.send_messages("123", ["a", "b"])
    assert sent1.message_id == "101"
    assert sent2.message_id == "102"
    assert sent3.message_id == "103"
    assert len(batch) == 2

    await ad.edit_message("123", "101", "new")
    await ad.delete_message("123", "101")
    await ad.send_progress("123", "p")
    await ad.update_progress("123", "101", "u")
    await ad.finish_progress("123", "101")

    # finish_progress 例外分支
    async def _boom(*_args, **_kwargs):
        raise RuntimeError("x")

    monkeypatch.setattr(ad, "delete_message", _boom)
    await ad.finish_progress("123", "101")


@pytest.mark.asyncio
async def test_telegram_media_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    # 路徑生成
    p1 = media._generate_telegram_nas_path("image", 1, "c1", True, ext=".jpg")
    p2 = media._generate_telegram_nas_path("file", 2, "u1", False, file_name="../a.txt", ext=".txt")
    assert "telegram/groups/c1/images/" in p1
    assert "2_.._a.txt" in p2

    bot = _FakePTBBot()
    message_photo = SimpleNamespace(
        message_id=11,
        photo=[SimpleNamespace(file_id="f1", file_size=123)],
    )
    message_doc = SimpleNamespace(
        message_id=12,
        document=SimpleNamespace(file_id="d1", file_name="doc.PDF", file_size=456, mime_type="application/pdf"),
    )

    monkeypatch.setattr(media, "save_to_nas", AsyncMock(return_value=True))
    monkeypatch.setattr(media, "save_file_record", AsyncMock(return_value=None))

    ok_photo = await media.download_telegram_photo(bot, message_photo, "m-1", "c1", True)
    assert ok_photo is not None and ok_photo.endswith(".jpg")
    ok_doc = await media.download_telegram_document(bot, message_doc, "m-2", "u1", False)
    assert ok_doc is not None and "doc.PDF" in ok_doc

    # 無媒體
    assert await media.download_telegram_photo(bot, SimpleNamespace(photo=[]), "m", "c", True) is None
    assert await media.download_telegram_document(bot, SimpleNamespace(document=None), "m", "c", True) is None

    # 儲存失敗
    monkeypatch.setattr(media, "save_to_nas", AsyncMock(return_value=False))
    assert await media.download_telegram_photo(bot, message_photo, "m-1", "c1", True) is None

    # 下載例外
    class _ErrBot(_FakePTBBot):
        async def get_file(self, _fid):
            raise RuntimeError("download fail")

    assert await media.download_telegram_document(_ErrBot(), message_doc, "m-2", "u1", False) is None


@pytest.mark.asyncio
async def test_telegram_polling_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    # token 空值 -> 直接返回
    monkeypatch.setattr(polling.settings, "telegram_bot_token", "")
    await polling.run_telegram_polling()

    # 有 token，跑一輪更新後停止
    monkeypatch.setattr(polling.settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(polling.settings, "telegram_admin_chat_id", "123")

    fake_adapter = SimpleNamespace(
        ensure_bot_info=AsyncMock(),
        bot=SimpleNamespace(
            get_me=AsyncMock(return_value=SimpleNamespace(username="ctos_bot")),
            send_message=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(polling, "TelegramBotAdapter", lambda token: fake_adapter)
    monkeypatch.setattr(polling, "_notify_admin_startup", AsyncMock())

    class _PollBot:
        def __init__(self, token=None, request=None) -> None:
            self.calls = 0

        async def delete_webhook(self):
            return None

        async def get_updates(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return [SimpleNamespace(update_id=7)]
            raise asyncio.CancelledError()

    import telegram

    monkeypatch.setattr(telegram, "Bot", _PollBot)
    monkeypatch.setattr(polling, "handle_update", AsyncMock(return_value=None))

    created = []

    def _fake_create_task(coro):
        created.append(coro)
        coro.close()
        return SimpleNamespace()

    monkeypatch.setattr(asyncio, "create_task", _fake_create_task)
    await polling.run_telegram_polling()
    assert len(created) == 1

    # _safe_handle_update 例外分支
    monkeypatch.setattr(polling, "handle_update", AsyncMock(side_effect=RuntimeError("x")))
    await polling._safe_handle_update(SimpleNamespace(update_id=99), fake_adapter)

    # _notify_admin_startup: 無 admin chat
    monkeypatch.setattr(polling.settings, "telegram_admin_chat_id", "")
    await polling._notify_admin_startup(fake_adapter)

    # _notify_admin_startup: 發送成功 / 失敗
    monkeypatch.setattr(polling.settings, "telegram_admin_chat_id", "123")
    await polling._notify_admin_startup(fake_adapter)
    fake_adapter.bot.send_message = AsyncMock(side_effect=RuntimeError("send fail"))
    await polling._notify_admin_startup(fake_adapter)
