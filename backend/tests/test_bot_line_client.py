"""bot_line.client 測試。"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

import ching_tech_os.services.bot_line.client as line_client


@pytest.fixture(autouse=True)
def _reset_shared_client():
    line_client._shared_api_client = None
    yield
    line_client._shared_api_client = None


def test_get_line_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        line_client,
        "Configuration",
        lambda access_token: {"access_token": access_token},
    )
    monkeypatch.setattr(line_client.settings, "line_channel_access_token", "default-token")

    assert line_client.get_line_config("override") == {"access_token": "override"}
    assert line_client.get_line_config() == {"access_token": "default-token"}


def test_get_webhook_parser(monkeypatch: pytest.MonkeyPatch):
    called: dict[str, str] = {}

    class _Parser:
        def __init__(self, secret: str):
            called["secret"] = secret

    monkeypatch.setattr(line_client, "WebhookParser", _Parser)
    monkeypatch.setattr(line_client.settings, "line_channel_secret", "default-secret")

    parser = line_client.get_webhook_parser()
    assert isinstance(parser, _Parser)
    assert called["secret"] == "default-secret"

    line_client.get_webhook_parser("override-secret")
    assert called["secret"] == "override-secret"


def test_get_shared_api_client_singleton(monkeypatch: pytest.MonkeyPatch):
    created = []

    def _create(config):
        created.append(config)
        return {"client": config}

    monkeypatch.setattr(line_client, "get_line_config", lambda: "cfg")
    monkeypatch.setattr(line_client, "AsyncApiClient", _create)

    first = line_client._get_shared_api_client()
    second = line_client._get_shared_api_client()

    assert first is second
    assert created == ["cfg"]


@pytest.mark.asyncio
async def test_get_messaging_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(line_client, "_get_shared_api_client", lambda: "shared")
    monkeypatch.setattr(line_client, "AsyncMessagingApi", lambda client: {"api_client": client})

    result = await line_client.get_messaging_api()
    assert result == {"api_client": "shared"}


@pytest.mark.asyncio
async def test_close_line_client(monkeypatch: pytest.MonkeyPatch):
    shared = AsyncMock()
    line_client._shared_api_client = shared
    await line_client.close_line_client()
    shared.close.assert_awaited_once()
    assert line_client._shared_api_client is None

    bad_client = AsyncMock()
    bad_client.close = AsyncMock(side_effect=RuntimeError("boom"))
    line_client._shared_api_client = bad_client
    warning = Mock()
    monkeypatch.setattr(line_client.logger, "warning", warning)
    await line_client.close_line_client()
    warning.assert_called_once()
    assert line_client._shared_api_client is None
