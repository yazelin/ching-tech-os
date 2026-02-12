"""排程服務測試。"""

from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services import scheduler


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_cleanup_old_messages_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["DELETE 2", "DELETE 3"])
    monkeypatch.setattr(scheduler, "get_connection", lambda: _CM(conn))

    await scheduler.cleanup_old_messages()
    assert conn.execute.await_count == 2

    async def _raise():
        raise RuntimeError("db failed")

    class _BadCM:
        async def __aenter__(self):
            await _raise()

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(scheduler, "get_connection", lambda: _BadCM())
    await scheduler.cleanup_old_messages()  # 不應拋出


@pytest.mark.asyncio
async def test_create_next_month_partitions_and_already_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="CREATE TABLE")
    monkeypatch.setattr(scheduler, "get_connection", lambda: _CM(conn))

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: D401
            return datetime(2026, 12, 26, tzinfo=tz)

    monkeypatch.setattr(scheduler, "datetime", _FixedDateTime)
    await scheduler.create_next_month_partitions()
    assert conn.execute.await_count == 2

    conn2 = AsyncMock()
    conn2.execute = AsyncMock(side_effect=Exception("already exists"))
    monkeypatch.setattr(scheduler, "get_connection", lambda: _CM(conn2))
    await scheduler.create_next_month_partitions()  # 已存在分支


@pytest.mark.asyncio
async def test_cleanup_expired_share_links(monkeypatch: pytest.MonkeyPatch) -> None:
    from ching_tech_os.services import share as share_service

    monkeypatch.setattr(share_service, "cleanup_expired_links", AsyncMock(return_value=2))
    await scheduler.cleanup_expired_share_links()

    monkeypatch.setattr(share_service, "cleanup_expired_links", AsyncMock(return_value=0))
    await scheduler.cleanup_expired_share_links()

    monkeypatch.setattr(share_service, "cleanup_expired_links", AsyncMock(side_effect=RuntimeError("oops")))
    await scheduler.cleanup_expired_share_links()  # 失敗分支


@pytest.mark.asyncio
async def test_cleanup_linebot_temp_files(monkeypatch: pytest.MonkeyPatch) -> None:
    now = time.time()
    fake_files = {
        "/tmp/bot-images": ["old.png", "new.png"],
        "/tmp/bot-files": ["old.pdf"],
    }
    deleted: list[str] = []

    monkeypatch.setattr(scheduler.os.path, "exists", lambda p: p in fake_files)
    monkeypatch.setattr(scheduler.os, "listdir", lambda p: fake_files[p])
    monkeypatch.setattr(scheduler.os.path, "join", os.path.join)
    monkeypatch.setattr(scheduler.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(
        scheduler.os.path,
        "getmtime",
        lambda p: now - 7200 if "old" in p else now,
    )
    monkeypatch.setattr(scheduler.os, "unlink", lambda p: deleted.append(p))

    await scheduler.cleanup_linebot_temp_files()
    assert any("old.png" in p for p in deleted)
    assert any("old.pdf" in p for p in deleted)
    assert all("new.png" not in p for p in deleted)


@pytest.mark.asyncio
async def test_cleanup_ai_images(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    ai_dir = tmp_path / "linebot" / "files" / "ai-images"
    ai_dir.mkdir(parents=True)
    old_file = ai_dir / "old.jpg"
    new_file = ai_dir / "new.jpg"
    old_file.write_bytes(b"1")
    new_file.write_bytes(b"2")
    old_ts = time.time() - (40 * 24 * 3600)
    new_ts = time.time()
    os.utime(old_file, (old_ts, old_ts))
    os.utime(new_file, (new_ts, new_ts))

    monkeypatch.setattr(scheduler.settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(scheduler.settings, "line_files_nas_path", "linebot/files")
    await scheduler.cleanup_ai_images()
    assert old_file.exists() is False
    assert new_file.exists() is True

    monkeypatch.setattr(scheduler.settings, "ctos_mount_path", str(tmp_path / "missing"))
    monkeypatch.setattr(scheduler.settings, "line_files_nas_path", "linebot/files")
    await scheduler.cleanup_ai_images()


def test_start_and_stop_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    class _DummyScheduler:
        def __init__(self):
            self.jobs: list[tuple] = []
            self.running = False

        def add_job(self, *args, **kwargs):
            self.jobs.append((args, kwargs))

        def start(self):
            self.running = True

        def shutdown(self):
            self.running = False

    dummy = _DummyScheduler()
    monkeypatch.setattr(scheduler, "scheduler", dummy)

    scheduler.start_scheduler()
    assert dummy.running is True
    assert len(dummy.jobs) == 5

    scheduler.stop_scheduler()
    assert dummy.running is False


@pytest.mark.asyncio
async def test_check_telegram_webhook_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler.settings, "telegram_bot_token", "token")
    monkeypatch.setattr(scheduler.settings, "public_url", "https://example.com")
    monkeypatch.setattr(scheduler.settings, "telegram_webhook_secret", "secret")

    class _WebhookInfo:
        def __init__(self, pending=0, error_date=None, error_msg=None) -> None:
            self.pending_update_count = pending
            self.last_error_date = error_date
            self.last_error_message = error_msg

    bot = SimpleNamespace(
        get_webhook_info=AsyncMock(return_value=_WebhookInfo(pending=2, error_msg="bad")),
        delete_webhook=AsyncMock(),
        set_webhook=AsyncMock(),
    )

    class _TelegramModule:
        class Bot:  # noqa: D106
            def __new__(cls, token):  # noqa: D401
                assert token == "token"
                return bot

    import sys

    monkeypatch.setitem(sys.modules, "telegram", _TelegramModule())
    await scheduler.check_telegram_webhook_health()
    bot.delete_webhook.assert_awaited_once()
    bot.set_webhook.assert_awaited_once()

    # 正常狀態分支
    bot2 = SimpleNamespace(
        get_webhook_info=AsyncMock(return_value=_WebhookInfo(pending=0, error_msg=None)),
        delete_webhook=AsyncMock(),
        set_webhook=AsyncMock(),
    )

    class _TelegramModule2:
        class Bot:  # noqa: D106
            def __new__(cls, token):
                assert token == "token"
                return bot2

    monkeypatch.setitem(sys.modules, "telegram", _TelegramModule2())
    await scheduler.check_telegram_webhook_health()
    bot2.delete_webhook.assert_not_awaited()
    bot2.set_webhook.assert_not_awaited()

    monkeypatch.setattr(scheduler.settings, "telegram_bot_token", "")
    await scheduler.check_telegram_webhook_health()  # 直接 return 分支
