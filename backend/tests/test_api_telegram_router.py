"""telegram_router API 測試。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from ching_tech_os.api import telegram_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(telegram_router.router)
    return TestClient(app)


def test_get_adapter_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telegram_router, "_adapter", None)
    monkeypatch.setattr(telegram_router.settings, "telegram_bot_token", "")
    with pytest.raises(HTTPException) as exc:
        telegram_router._get_adapter()
    assert exc.value.status_code == 503

    created = []

    class _FakeAdapter:
        def __init__(self, token: str) -> None:
            created.append(token)
            self.bot = SimpleNamespace()

    monkeypatch.setattr(telegram_router.settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(telegram_router, "TelegramBotAdapter", _FakeAdapter)
    first = telegram_router._get_adapter()
    second = telegram_router._get_adapter()
    assert first is second
    assert created == ["bot-token"]


def test_telegram_webhook_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()

    monkeypatch.setattr(telegram_router.settings, "telegram_webhook_secret", "secret")
    resp_403 = client.post("/webhook", json={"update_id": 1})
    assert resp_403.status_code == 403

    fake_adapter = SimpleNamespace(bot=SimpleNamespace())
    monkeypatch.setattr(telegram_router, "_get_adapter", lambda: fake_adapter)
    monkeypatch.setattr(telegram_router.settings, "telegram_webhook_secret", "")
    monkeypatch.setattr(telegram_router, "handle_update", AsyncMock())
    monkeypatch.setattr(telegram_router.Update, "de_json", lambda body, _bot: {"body": body})

    ok = client.post("/webhook", json={"update_id": 2})
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"

    monkeypatch.setattr(
        telegram_router.Update,
        "de_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad body")),
    )
    bad = client.post("/webhook", json={"update_id": 3})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_setup_telegram_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telegram_router.settings, "telegram_bot_token", "")
    await telegram_router.setup_telegram_webhook()

    fake_bot = SimpleNamespace(
        set_webhook=AsyncMock(return_value=True),
        get_me=AsyncMock(return_value=SimpleNamespace(username="ctos_bot")),
        send_message=AsyncMock(return_value=None),
    )
    fake_adapter = SimpleNamespace(
        ensure_bot_info=AsyncMock(return_value=None),
        bot=fake_bot,
    )
    notify_mock = AsyncMock()

    monkeypatch.setattr(telegram_router.settings, "telegram_bot_token", "token")
    monkeypatch.setattr(telegram_router.settings, "telegram_webhook_secret", "hook-secret")
    monkeypatch.setattr(telegram_router.settings, "public_url", "https://example.com")
    monkeypatch.setattr(telegram_router, "_get_adapter", lambda: fake_adapter)
    monkeypatch.setattr(telegram_router, "_notify_admin_startup", notify_mock)

    await telegram_router.setup_telegram_webhook()
    fake_adapter.ensure_bot_info.assert_awaited_once()
    fake_bot.set_webhook.assert_awaited_once()
    assert fake_bot.set_webhook.await_args.kwargs["secret_token"] == "hook-secret"
    notify_mock.assert_awaited_once()

    notify_mock.reset_mock()
    fake_bot.set_webhook = AsyncMock(return_value=False)
    await telegram_router.setup_telegram_webhook()
    notify_mock.assert_awaited_once()

    notify_mock.reset_mock()
    fake_bot.set_webhook = AsyncMock(side_effect=RuntimeError("boom"))
    await telegram_router.setup_telegram_webhook()
    notify_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_admin_startup_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_bot = SimpleNamespace(
        get_me=AsyncMock(return_value=SimpleNamespace(username="ctos_bot")),
        send_message=AsyncMock(return_value=None),
    )
    fake_adapter = SimpleNamespace(bot=fake_bot)

    monkeypatch.setattr(telegram_router.settings, "telegram_admin_chat_id", "")
    await telegram_router._notify_admin_startup(fake_adapter)
    fake_bot.send_message.assert_not_called()

    monkeypatch.setattr(telegram_router.settings, "telegram_admin_chat_id", "123")
    await telegram_router._notify_admin_startup(fake_adapter)
    fake_bot.send_message.assert_awaited_once()

    fake_bot.send_message = AsyncMock(side_effect=RuntimeError("send failed"))
    await telegram_router._notify_admin_startup(fake_adapter)
