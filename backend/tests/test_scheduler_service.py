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
    assert conn.execute.await_count == 3  # messages + login_records + ai_logs

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
    assert len(dummy.jobs) == 8
    job_ids = {kwargs.get("id") for _, kwargs in dummy.jobs}
    assert "cleanup_old_messages" in job_ids
    assert "create_next_month_partitions" in job_ids
    assert "cleanup_expired_share_links" in job_ids
    assert "cleanup_old_bot_tracking" in job_ids
    assert "file-manager:cleanup_linebot_temp_files" in job_ids
    assert "file-manager:cleanup_media_temp_folders" in job_ids
    assert "ai-agent:cleanup_ai_images" in job_ids
    assert "ai-agent:cleanup_cli_temp_dirs" in job_ids

    scheduler.stop_scheduler()
    assert dummy.running is False


def test_start_scheduler_respects_module_enablement(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(
        scheduler,
        "get_module_registry",
        lambda: {
            "file-manager": {
                "scheduler_jobs": [
                    {"fn": "cleanup_linebot_temp_files", "trigger": "interval", "hours": 1},
                ]
            },
            "ai-agent": {
                "scheduler_jobs": [
                    {"fn": "cleanup_ai_images", "trigger": "cron", "hour": 4, "minute": 30},
                ]
            },
        },
    )
    monkeypatch.setattr(
        scheduler,
        "is_module_enabled",
        lambda module_id: module_id != "file-manager",
    )

    scheduler.start_scheduler()
    job_ids = {kwargs.get("id") for _, kwargs in dummy.jobs}
    assert "ai-agent:cleanup_ai_images" in job_ids
    assert "file-manager:cleanup_linebot_temp_files" not in job_ids
    assert "cleanup_expired_share_links" in job_ids


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


@pytest.mark.asyncio
async def test_check_telegram_webhook_health_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Telegram Bot 建立失敗時應記錄錯誤而不拋出。"""
    import sys

    monkeypatch.setattr(scheduler.settings, "telegram_bot_token", "token")

    class _TelegramModule:
        class Bot:  # noqa: D106
            def __new__(cls, token):
                raise RuntimeError("telegram 連線失敗")

    monkeypatch.setitem(sys.modules, "telegram", _TelegramModule())
    await scheduler.check_telegram_webhook_health()  # 例外分支，不應拋出


@pytest.mark.asyncio
async def test_create_next_month_partitions_non_december(monkeypatch: pytest.MonkeyPatch) -> None:
    """11 月執行時，下月為 12 月、下下月跨年，覆蓋非 12 月與跨年邊界分支。"""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="CREATE TABLE")
    monkeypatch.setattr(scheduler, "get_connection", lambda: _CM(conn))

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: D401
            return datetime(2026, 11, 15, tzinfo=tz)

    monkeypatch.setattr(scheduler, "datetime", _FixedDateTime)
    await scheduler.create_next_month_partitions()
    assert conn.execute.await_count == 3
    # 確認分區名稱為 2026_12，且結束邊界跨到 2027-01-01
    first_sql = conn.execute.await_args_list[0].args[0]
    assert "messages_2026_12" in first_sql
    assert "2027-01-01" in first_sql


@pytest.mark.asyncio
async def test_create_next_month_partitions_generic_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """非「already exists」的錯誤應走一般錯誤 log 分支且不拋出。"""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=Exception("connection lost"))
    monkeypatch.setattr(scheduler, "get_connection", lambda: _CM(conn))
    await scheduler.create_next_month_partitions()  # 不應拋出


@pytest.mark.asyncio
async def test_cleanup_linebot_temp_files_missing_dir_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """目錄不存在時跳過；listdir 失敗時記錄錯誤；無刪除時走 debug 分支。"""

    def _fake_listdir(path):
        raise OSError("讀取目錄失敗")

    # bot-images 不存在（continue 分支）、bot-files 存在但 listdir 失敗（錯誤分支）
    monkeypatch.setattr(scheduler.os.path, "exists", lambda p: p == "/tmp/bot-files")
    monkeypatch.setattr(scheduler.os, "listdir", _fake_listdir)

    await scheduler.cleanup_linebot_temp_files()  # total_deleted == 0，走 debug 分支


@pytest.mark.asyncio
async def test_cleanup_ai_images_no_expired_and_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """AI 圖片目錄只有新檔時不刪除；listdir 失敗時記錄錯誤。"""
    ai_dir = tmp_path / "linebot" / "files" / "ai-images"
    ai_dir.mkdir(parents=True)
    new_file = ai_dir / "new.jpg"
    new_file.write_bytes(b"1")

    monkeypatch.setattr(scheduler.settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(scheduler.settings, "line_files_nas_path", "linebot/files")

    await scheduler.cleanup_ai_images()  # 無過期檔案分支
    assert new_file.exists() is True

    real_listdir = os.listdir

    def _fake_listdir(path):
        if "ai-images" in str(path):
            raise OSError("讀取失敗")
        return real_listdir(path)

    monkeypatch.setattr(scheduler.os, "listdir", _fake_listdir)
    await scheduler.cleanup_ai_images()  # 例外分支，不應拋出


@pytest.mark.asyncio
async def test_cleanup_cli_temp_dirs(monkeypatch: pytest.MonkeyPatch) -> None:
    """清理 CLI 暫存目錄：跳過非目錄/使用中/新目錄，只刪超過 1 天的舊目錄。"""
    import glob as glob_module
    import shutil as shutil_module
    import sys

    current_base = "/tmp/ching-tech-os-cli-current"
    fake_dirs = [
        "/tmp/ching-tech-os-cli-notdir",  # 非目錄，跳過
        current_base,  # 使用中，跳過
        "/tmp/ching-tech-os-cli-new",  # 未過期，跳過
        "/tmp/ching-tech-os-cli-old",  # 超過 1 天，刪除
    ]
    removed: list[str] = []
    now = time.time()

    # 用假模組取代 claude_agent，避免 import 副作用（mkdtemp）
    monkeypatch.setitem(
        sys.modules,
        "ching_tech_os.services.claude_agent",
        SimpleNamespace(_WORKING_DIR_BASE=current_base),
    )
    monkeypatch.setattr(glob_module, "glob", lambda pattern: list(fake_dirs))
    monkeypatch.setattr(
        scheduler.os.path, "isdir", lambda p: p != "/tmp/ching-tech-os-cli-notdir"
    )
    monkeypatch.setattr(scheduler.os.path, "realpath", lambda p: p)
    monkeypatch.setattr(
        scheduler.os.path,
        "getmtime",
        lambda p: now - (2 * 24 * 3600) if "old" in p else now,
    )
    monkeypatch.setattr(
        shutil_module, "rmtree", lambda p, ignore_errors=False: removed.append(p)
    )

    await scheduler.cleanup_cli_temp_dirs()
    assert removed == ["/tmp/ching-tech-os-cli-old"]

    # 無過期目錄分支
    removed.clear()
    monkeypatch.setattr(glob_module, "glob", lambda pattern: [])
    await scheduler.cleanup_cli_temp_dirs()
    assert removed == []

    # glob 失敗時記錄錯誤而不拋出
    def _raise_glob(pattern):
        raise OSError("glob 失敗")

    monkeypatch.setattr(glob_module, "glob", _raise_glob)
    await scheduler.cleanup_cli_temp_dirs()


@pytest.mark.asyncio
async def test_cleanup_media_temp_folders(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """清理媒體暫存：刪除過期日期資料夾，保留新資料夾、非日期資料夾與檔案。"""
    videos_dir = tmp_path / "linebot" / "videos"
    old_dir = videos_dir / "2020-01-01"
    new_dir = videos_dir / "2099-01-01"
    not_date_dir = videos_dir / "not-a-date"
    old_dir.mkdir(parents=True)
    new_dir.mkdir()
    not_date_dir.mkdir()
    (old_dir / "a.bin").write_bytes(b"12345")
    (videos_dir / "somefile.txt").write_text("x")
    # transcriptions 目錄不存在，覆蓋「目錄不存在」分支

    monkeypatch.setattr(scheduler.settings, "ctos_mount_path", str(tmp_path))

    await scheduler.cleanup_media_temp_folders()
    assert old_dir.exists() is False
    assert new_dir.exists() is True
    assert not_date_dir.exists() is True
    assert (videos_dir / "somefile.txt").exists() is True

    # 再執行一次：無過期資料夾，走 debug 分支
    await scheduler.cleanup_media_temp_folders()


@pytest.mark.asyncio
async def test_cleanup_media_temp_folders_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """rmtree 失敗時應記錄錯誤而不拋出。"""
    videos_dir = tmp_path / "linebot" / "videos"
    old_dir = videos_dir / "2020-01-01"
    old_dir.mkdir(parents=True)

    def _raise_rmtree(path):
        raise OSError("刪除失敗")

    monkeypatch.setattr(scheduler.settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(scheduler, "shutil", SimpleNamespace(rmtree=_raise_rmtree))

    await scheduler.cleanup_media_temp_folders()  # 不應拋出
    assert old_dir.exists() is True


@pytest.mark.asyncio
async def test_cleanup_old_bot_tracking(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bot 使用量追蹤清理：有刪除、無刪除、失敗三個分支。"""
    from ching_tech_os.services.bot import rate_limiter

    monkeypatch.setattr(rate_limiter, "cleanup_old_tracking", AsyncMock(return_value=5))
    await scheduler.cleanup_old_bot_tracking()

    monkeypatch.setattr(rate_limiter, "cleanup_old_tracking", AsyncMock(return_value=0))
    await scheduler.cleanup_old_bot_tracking()

    monkeypatch.setattr(
        rate_limiter, "cleanup_old_tracking", AsyncMock(side_effect=RuntimeError("db 失敗"))
    )
    await scheduler.cleanup_old_bot_tracking()  # 失敗分支


def test_register_module_job_edge_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    """_register_module_job 的各種邊界：動態排程、缺 fn、fn 不存在、預設 interval、註冊失敗。"""

    class _DummyScheduler:
        def __init__(self):
            self.jobs: list[tuple] = []

        def add_job(self, *args, **kwargs):
            self.jobs.append((args, kwargs))

    dummy = _DummyScheduler()
    pending: list[tuple[str, dict]] = []
    monkeypatch.setattr(scheduler, "scheduler", dummy)
    monkeypatch.setattr(scheduler, "_pending_dynamic_module_jobs", pending)

    # 動態排程：含 executor_type，應加入 pending 清單而不註冊
    scheduler._register_module_job("law", {"executor_type": "ai_prompt", "name": "job-a"})
    assert pending == [("law", {"executor_type": "ai_prompt", "name": "job-a"})]
    assert dummy.jobs == []

    # 缺少 fn 欄位
    scheduler._register_module_job("law", {"trigger": "interval"})
    assert dummy.jobs == []

    # fn 不是可呼叫的模組函式
    scheduler._register_module_job("law", {"fn": "no_such_function"})
    assert dummy.jobs == []

    # interval 未指定任何時間參數，應套用預設 hours=1
    scheduler._register_module_job("law", {"fn": "cleanup_ai_images", "trigger": "interval"})
    assert len(dummy.jobs) == 1
    _, kwargs = dummy.jobs[0]
    assert kwargs["id"] == "law:cleanup_ai_images"

    # add_job 失敗時記錄警告而不拋出
    class _BadScheduler:
        def add_job(self, *args, **kwargs):
            raise RuntimeError("註冊失敗")

    monkeypatch.setattr(scheduler, "scheduler", _BadScheduler())
    scheduler._register_module_job("law", {"fn": "cleanup_ai_images", "trigger": "cron", "hour": 3})


@pytest.mark.asyncio
async def test_start_scheduler_processes_dynamic_module_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """啟動排程器時，模組宣告的動態排程應寫入 DB：已存在跳過、新任務建立、失敗記錯誤。"""
    import asyncio

    from ching_tech_os.services import task_scheduler

    class _DummyScheduler:
        def __init__(self):
            self.jobs: list[tuple] = []
            self.running = False

        def add_job(self, *args, **kwargs):
            self.jobs.append((args, kwargs))

        def start(self):
            self.running = True

    dummy = _DummyScheduler()
    pending: list[tuple[str, dict]] = []
    monkeypatch.setattr(scheduler, "scheduler", dummy)
    monkeypatch.setattr(scheduler, "_pending_dynamic_module_jobs", pending)
    monkeypatch.setattr(
        scheduler,
        "get_module_registry",
        lambda: {
            "law": {
                "scheduler_jobs": [
                    {"executor_type": "ai_prompt", "name": "existing-job"},
                    {"executor_type": "ai_prompt", "name": "new-job", "trigger": "cron", "hour": 2},
                    {"executor_type": "ai_prompt", "name": "bad-job"},
                ]
            }
        },
    )
    monkeypatch.setattr(scheduler, "is_module_enabled", lambda _module_id: True)

    list_mock = AsyncMock(return_value=[{"name": "existing-job"}])
    create_mock = AsyncMock(side_effect=[{"id": "x"}, RuntimeError("db down")])
    load_mock = AsyncMock()
    monkeypatch.setattr(task_scheduler, "list_scheduled_tasks", list_mock)
    monkeypatch.setattr(task_scheduler, "create_scheduled_task", create_mock)
    monkeypatch.setattr(task_scheduler, "load_dynamic_tasks", load_mock)

    scheduler.start_scheduler()
    assert dummy.running is True

    # 等待 start_scheduler 內部建立的 _load 背景任務完成
    background = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    await asyncio.gather(*background)

    list_mock.assert_awaited_once()
    assert create_mock.await_count == 2  # new-job 成功、bad-job 失敗
    created_names = [call.args[0]["name"] for call in create_mock.await_args_list]
    assert created_names == ["new-job", "bad-job"]
    load_mock.assert_awaited_once()
    assert pending == []  # 處理完應清空


@pytest.mark.asyncio
async def test_start_scheduler_dynamic_load_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """載入動態排程失敗時應記錄錯誤，不影響排程器啟動。"""
    import asyncio

    from ching_tech_os.services import task_scheduler

    class _DummyScheduler:
        def add_job(self, *args, **kwargs):
            return None

        def start(self):
            return None

    monkeypatch.setattr(scheduler, "scheduler", _DummyScheduler())
    monkeypatch.setattr(scheduler, "_pending_dynamic_module_jobs", [])
    monkeypatch.setattr(scheduler, "get_module_registry", lambda: {})
    monkeypatch.setattr(
        task_scheduler, "load_dynamic_tasks", AsyncMock(side_effect=RuntimeError("載入失敗"))
    )

    scheduler.start_scheduler()

    background = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    await asyncio.gather(*background)  # 例外應被 _load 內部吞掉
