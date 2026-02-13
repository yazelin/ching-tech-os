"""bot_settings API 測試。"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from ching_tech_os.api import bot_settings as bot_settings_api
from ching_tech_os.models.auth import SessionData


def _session(role: str = "admin") -> SessionData:
    now = datetime.now()
    return SessionData(
        username="admin",
        password="pw",
        nas_host="h",
        user_id=1,
        role=role,
        app_permissions={},
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


def _app_with_admin() -> TestClient:
    app = FastAPI()
    app.include_router(bot_settings_api.router)
    app.dependency_overrides[bot_settings_api.get_current_session] = lambda: _session("admin")
    return TestClient(app)


@pytest.mark.asyncio
async def test_admin_and_platform_validation() -> None:
    assert (await bot_settings_api.require_admin(_session("admin"))).role == "admin"
    with pytest.raises(HTTPException) as e1:
        await bot_settings_api.require_admin(_session("user"))
    assert e1.value.status_code == 403

    assert bot_settings_api._validate_platform("line") == "line"
    with pytest.raises(HTTPException) as e2:
        bot_settings_api._validate_platform("unknown")
    assert e2.value.status_code == 400


def test_bot_settings_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app_with_admin()

    monkeypatch.setattr(bot_settings_api, "get_bot_credentials_status", AsyncMock(return_value={
        "platform": "line",
        "fields": {
            "channel_secret": {
                "has_value": True,
                "masked_value": "abcd...1234",
                "source": "database",
                "updated_at": None,
            }
        },
    }))
    monkeypatch.setattr(bot_settings_api, "update_bot_credentials", AsyncMock(return_value=None))
    monkeypatch.setattr(bot_settings_api, "delete_bot_credentials", AsyncMock(return_value=2))
    monkeypatch.setattr(bot_settings_api, "_test_line_connection", AsyncMock(return_value={"success": True, "message": "ok"}))
    monkeypatch.setattr(bot_settings_api, "_test_telegram_connection", AsyncMock(return_value={"success": True, "message": "ok"}))
    monkeypatch.setattr(bot_settings_api, "get_bot_credentials", AsyncMock(return_value={"channel_access_token": "x", "bot_token": "y"}))

    assert client.get("/api/admin/bot-settings/line").status_code == 200
    assert client.put("/api/admin/bot-settings/line", json={"channel_secret": "x"}).status_code == 200
    assert client.delete("/api/admin/bot-settings/line").status_code == 200
    assert client.post("/api/admin/bot-settings/line/test").status_code == 200
    assert client.post("/api/admin/bot-settings/telegram/test").status_code == 200

    # 空 body / 平台錯誤
    assert client.put("/api/admin/bot-settings/line", json={}).status_code == 400
    assert client.get("/api/admin/bot-settings/unknown").status_code == 400

    # test_connection 例外分支
    monkeypatch.setattr(bot_settings_api, "get_bot_credentials", AsyncMock(side_effect=RuntimeError("boom")))
    resp = client.post("/api/admin/bot-settings/line/test")
    assert resp.status_code == 200 and resp.json()["success"] is False


@pytest.mark.asyncio
async def test_line_and_telegram_connection_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        def __init__(self, code: int, payload: dict, text: str = "") -> None:
            self.status_code = code
            self._payload = payload
            self.text = text

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, response):
            self.response = response

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return self.response

    # line: token 缺失
    missing = await bot_settings_api._test_line_connection({})
    assert missing.success is False

    # line: 成功 / 失敗
    monkeypatch.setattr(
        __import__("httpx"),
        "AsyncClient",
        lambda: _Client(_Resp(200, {"displayName": "CTOS"})),
    )
    ok = await bot_settings_api._test_line_connection({"channel_access_token": "tok"})
    assert ok.success is True and "CTOS" in ok.message

    monkeypatch.setattr(
        __import__("httpx"),
        "AsyncClient",
        lambda: _Client(_Resp(401, {}, text="unauthorized")),
    )
    fail = await bot_settings_api._test_line_connection({"channel_access_token": "tok"})
    assert fail.success is False and "401" in fail.message

    # telegram: token 缺失
    missing_tg = await bot_settings_api._test_telegram_connection({})
    assert missing_tg.success is False

    # telegram: success / failed
    monkeypatch.setattr(
        __import__("httpx"),
        "AsyncClient",
        lambda: _Client(_Resp(200, {"ok": True, "result": {"first_name": "CT", "username": "ct_bot"}})),
    )
    ok_tg = await bot_settings_api._test_telegram_connection({"bot_token": "tok"})
    assert ok_tg.success is True and "@ct_bot" in ok_tg.message

    monkeypatch.setattr(
        __import__("httpx"),
        "AsyncClient",
        lambda: _Client(_Resp(500, {"ok": False}, text="err")),
    )
    bad_tg = await bot_settings_api._test_telegram_connection({"bot_token": "tok"})
    assert bad_tg.success is False and "500" in bad_tg.message
