"""message/login_record/bot_settings 與相關 API 測試。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ching_tech_os.api import login_records as login_records_api
from ching_tech_os.api import message_events, messages as messages_api
from ching_tech_os.models.login_record import DeviceInfo, DeviceType, GeoLocation, LoginRecordFilter
from ching_tech_os.models.message import MarkReadRequest, MessageFilter, MessageSeverity, MessageSource
from ching_tech_os.services import bot_settings, login_record, message


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_message_service_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    now = _now()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[
        {"id": 11},  # log_message
        {  # get_message
            "id": 11,
            "created_at": now,
            "severity": "info",
            "source": "system",
            "category": "app",
            "title": "t",
            "content": "c",
            "metadata": '{"x":1}',
            "user_id": 1,
            "session_id": None,
            "is_read": False,
        },
        None,  # get_message not found
        {"total": 2},  # search_messages count
        {"count": 3},  # get_unread_count(user)
        {"count": 4},  # get_unread_count(all)
    ])
    conn.fetch = AsyncMock(side_effect=[
        [  # search_messages rows
            {"id": 1, "created_at": now, "severity": "warning", "source": "security", "category": "auth", "title": "a", "is_read": False},
            {"id": 2, "created_at": now, "severity": "info", "source": "system", "category": "app", "title": "b", "is_read": True},
        ],
        [  # get_messages_grouped_by_date
            {"id": 3, "created_at": now, "severity": "info", "source": "system", "category": "app", "title": "today", "is_read": False},
            {"id": 4, "created_at": now - timedelta(days=1), "severity": "info", "source": "system", "category": "app", "title": "yesterday", "is_read": False},
            {"id": 5, "created_at": now - timedelta(days=2), "severity": "info", "source": "system", "category": "app", "title": "earlier", "is_read": True},
        ],
    ])
    conn.execute = AsyncMock(side_effect=["UPDATE 2", "UPDATE 1", "UPDATE 3"])
    monkeypatch.setattr(message, "get_connection", lambda: _CM(conn))

    mid = await message.log_message(MessageSeverity.INFO, MessageSource.SYSTEM, "title", metadata={"x": 1})
    assert mid == 11
    detail = await message.get_message(11)
    assert detail is not None and detail.metadata["x"] == 1
    assert await message.get_message(999) is None

    result = await message.search_messages(
        MessageFilter(
            severity=[MessageSeverity.INFO],
            source=[MessageSource.SYSTEM],
            category="app",
            user_id=1,
            search="a",
            is_read=False,
            page=1,
            limit=20,
        )
    )
    assert result.total == 2 and len(result.items) == 2
    assert await message.get_unread_count(1) == 3
    assert await message.get_unread_count() == 4
    assert await message.mark_as_read(mark_all=True, user_id=1) == 2
    assert await message.mark_as_read(ids=[1, 2]) == 1
    assert await message.mark_as_read(mark_all=True) == 3
    assert await message.mark_as_read() == 0
    grouped = await message.get_messages_grouped_by_date(user_id=1, limit=10)
    assert len(grouped["today"]) == 1 and len(grouped["yesterday"]) == 1 and len(grouped["earlier"]) == 1


@pytest.mark.asyncio
async def test_login_record_service_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    now = _now()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[
        {"id": 9},  # record_login
        {  # get_login_record
            "id": 9,
            "created_at": now,
            "user_id": 1,
            "username": "u1",
            "success": True,
            "failure_reason": None,
            "ip_address": "127.0.0.1",
            "user_agent": "ua",
            "geo_country": "TW",
            "geo_city": "Taipei",
            "geo_latitude": 25.0,
            "geo_longitude": 121.0,
            "device_fingerprint": "fp",
            "device_type": "desktop",
            "browser": "Chrome",
            "os": "Linux",
            "session_id": "s1",
        },
        None,  # get_login_record not found
        {"total": 1},  # search count
        {  # stats with user_id
            "total": 10,
            "success_count": 9,
            "failure_count": 1,
            "unique_ips": 2,
            "unique_devices": 3,
        },
        {  # stats without user_id
            "total": 20,
            "success_count": 15,
            "failure_count": 5,
            "unique_ips": 4,
            "unique_devices": 6,
        },
    ])
    conn.fetch = AsyncMock(side_effect=[
        [  # search rows
            {"id": 1, "created_at": now, "username": "u1", "success": True, "failure_reason": None, "ip_address": "127.0.0.1", "geo_country": "TW", "geo_city": "Taipei", "device_type": "desktop", "browser": "Chrome"},
        ],
        [  # recent by user_id
            {"id": 2, "created_at": now, "username": "u1", "success": False, "failure_reason": "bad", "ip_address": "127.0.0.1", "geo_country": "TW", "geo_city": "Taipei", "device_type": "desktop", "browser": "Chrome"},
        ],
        [  # recent by username
            {"id": 3, "created_at": now, "username": "u2", "success": True, "failure_reason": None, "ip_address": "127.0.0.2", "geo_country": "US", "geo_city": "NY", "device_type": "mobile", "browser": "Safari"},
        ],
        [  # recent all
            {"id": 4, "created_at": now, "username": "u3", "success": True, "failure_reason": None, "ip_address": "127.0.0.3", "geo_country": "JP", "geo_city": "Tokyo", "device_type": "desktop", "browser": "Edge"},
        ],
    ])
    monkeypatch.setattr(login_record, "get_connection", lambda: _CM(conn))

    rid = await login_record.record_login(
        username="u1",
        success=True,
        ip_address="127.0.0.1",
        user_id=1,
        user_agent="ua",
        geo=GeoLocation(country="TW", city="Taipei", latitude=25.0, longitude=121.0),
        device=DeviceInfo(device_type=DeviceType.DESKTOP, fingerprint="fp", browser="Chrome", os="Linux"),
    )
    assert rid == 9
    assert (await login_record.get_login_record(9)) is not None
    assert await login_record.get_login_record(999) is None

    result = await login_record.search_login_records(
        LoginRecordFilter(user_id=1, username="u1", success=True, ip_address="127.0.0.1", page=1, limit=20)
    )
    assert result.total == 1 and len(result.items) == 1
    assert len((await login_record.get_recent_logins(user_id=1)).items) == 1
    assert len((await login_record.get_recent_logins(username="u2")).items) == 1
    assert len((await login_record.get_recent_logins()).items) == 1
    assert (await login_record.get_login_stats(user_id=1, days=30))["total"] == 10
    assert (await login_record.get_login_stats(days=7))["total"] == 20


@pytest.mark.asyncio
async def test_bot_settings_service_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    now = _now()
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[
        [  # get_bot_credentials(line)
            {"key": "channel_secret", "value": "enc-secret"},
        ],
        [  # get_bot_credentials(line) inside status
            {"key": "channel_secret", "value": "enc-secret"},
        ],
        [  # updated_at rows for status
            {"key": "channel_secret", "updated_at": now},
        ],
        [  # get_bot_credentials(telegram)
            {"key": "bot_token", "value": "raw-bot-token"},
        ],
    ])
    conn.execute = AsyncMock(side_effect=["UPSERT", "UPSERT", "DELETE 2"])
    monkeypatch.setattr(bot_settings, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(bot_settings, "is_encrypted", lambda v: v.startswith("enc-"))
    monkeypatch.setattr(bot_settings, "decrypt_credential", lambda v: v.replace("enc-", "dec-"))
    monkeypatch.setattr(bot_settings, "encrypt_credential", lambda v: f"enc::{v}")
    monkeypatch.setattr(bot_settings.settings, "line_channel_access_token", "env-line-token")
    monkeypatch.setattr(bot_settings.settings, "telegram_webhook_secret", "env-webhook")
    monkeypatch.setattr(bot_settings.settings, "telegram_admin_chat_id", "12345")

    creds = await bot_settings.get_bot_credentials("line")
    assert creds["channel_secret"] == "dec-secret"
    assert creds["channel_access_token"] == "env-line-token"
    status = await bot_settings.get_bot_credentials_status("line")
    assert status["fields"]["channel_secret"]["source"] == "database"
    assert status["fields"]["channel_secret"]["masked_value"].startswith("****")

    await bot_settings.update_bot_credentials(
        "telegram",
        {"bot_token": "token", "webhook_secret": "wh", "invalid_key": "x"},
    )
    deleted = await bot_settings.delete_bot_credentials("telegram")
    assert deleted == 2
    assert (await bot_settings.get_telegram_credentials())["bot_token"] == "raw-bot-token"

    # helper 與錯誤分支
    assert bot_settings._mask_value("1234567890123").startswith("1234...")
    assert bot_settings._mask_value("short") == "****"
    with pytest.raises(ValueError):
        await bot_settings.get_bot_credentials("unknown")
    with pytest.raises(ValueError):
        await bot_settings.update_bot_credentials("unknown", {})
    with pytest.raises(ValueError):
        await bot_settings.delete_bot_credentials("unknown")

    monkeypatch.setattr(bot_settings, "get_bot_credentials", AsyncMock(return_value={"channel_secret": "x"}))
    assert (await bot_settings.get_line_credentials())["channel_secret"] == "x"


def test_messages_and_login_records_api_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(messages_api.router)
    app.include_router(login_records_api.router)
    client = TestClient(app)

    msg_resp = {
        "items": [],
        "total": 0,
        "page": 1,
        "limit": 20,
        "total_pages": 1,
    }
    login_list_resp = {
        "items": [],
        "total": 0,
        "page": 1,
        "limit": 20,
        "total_pages": 1,
    }
    monkeypatch.setattr(messages_api, "search_messages", AsyncMock(return_value=msg_resp))
    monkeypatch.setattr(messages_api, "get_unread_count", AsyncMock(return_value=5))
    monkeypatch.setattr(messages_api, "mark_as_read", AsyncMock(return_value=2))
    monkeypatch.setattr(messages_api, "get_message", AsyncMock(side_effect=[{
        "id": 1,
        "created_at": _now().isoformat(),
        "severity": "info",
        "source": "system",
        "category": "app",
        "title": "ok",
        "content": "hello",
        "metadata": None,
        "user_id": None,
        "session_id": None,
        "is_read": False,
    }, None]))

    monkeypatch.setattr(login_records_api, "search_login_records", AsyncMock(return_value=login_list_resp))
    monkeypatch.setattr(login_records_api, "get_recent_logins", AsyncMock(return_value={"items": []}))
    monkeypatch.setattr(login_records_api, "get_login_stats", AsyncMock(return_value={"total": 1}))
    monkeypatch.setattr(login_records_api, "get_login_record", AsyncMock(side_effect=[{
        "id": 1,
        "created_at": _now().isoformat(),
        "user_id": 1,
        "username": "u1",
        "success": True,
        "failure_reason": None,
        "ip_address": "127.0.0.1",
        "user_agent": None,
        "geo_country": None,
        "geo_city": None,
        "geo_latitude": None,
        "geo_longitude": None,
        "device_fingerprint": None,
        "device_type": None,
        "browser": None,
        "os": None,
        "session_id": None,
    }, None]))

    assert client.get("/api/messages").status_code == 200
    assert client.get("/api/messages/unread-count").status_code == 200
    assert client.post("/api/messages/mark-read", json=MarkReadRequest(ids=[1]).model_dump()).status_code == 200
    assert client.post("/api/messages/mark-read", json=MarkReadRequest().model_dump()).status_code == 400
    assert client.get("/api/messages/1").status_code == 200
    assert client.get("/api/messages/2").status_code == 404

    assert client.get("/api/login-records").status_code == 200
    assert client.get("/api/login-records/recent").status_code == 200
    assert client.get("/api/login-records/stats").status_code == 200
    assert client.get("/api/login-records/1").status_code == 200
    assert client.get("/api/login-records/2").status_code == 404


@pytest.mark.asyncio
async def test_message_events_module(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeSio:
        def __init__(self) -> None:
            self.handlers = {}
            self.enter_room = AsyncMock()
            self.leave_room = AsyncMock()
            self.emit = AsyncMock()

        def event(self, fn):
            self.handlers[fn.__name__] = fn
            return fn

    sio = _FakeSio()
    monkeypatch.setattr(message_events, "get_unread_count", AsyncMock(return_value=7))
    message_events.register_events(sio)
    assert message_events.get_sio() is sio

    await sio.handlers["join_user_room"]("sid-1", {"userId": 10})
    await sio.handlers["leave_user_room"]("sid-1", {"userId": 10})
    await sio.handlers["get_unread_count_event"]("sid-1", {"userId": 10})
    assert sio.enter_room.await_count == 1
    assert sio.leave_room.await_count == 1
    assert sio.emit.await_count >= 2

    await message_events.emit_new_message(
        message_id=1,
        severity=MessageSeverity.WARNING,
        source=MessageSource.SECURITY,
        title="warn",
        created_at=_now().isoformat(),
        user_id=10,
    )
    await message_events.emit_new_message(
        message_id=2,
        severity="info",
        source="system",
        title="ok",
        created_at=_now().isoformat(),
    )
    await message_events.emit_unread_count(user_id=10, count=3)
    await message_events.emit_unread_count()

    # _sio 未初始化
    monkeypatch.setattr(message_events, "_sio", None)
    await message_events.emit_new_message(3, "info", "system", "x", _now().isoformat())
    await message_events.emit_unread_count()
