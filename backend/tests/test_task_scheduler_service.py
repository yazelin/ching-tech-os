"""排程管理 Service 層測試。

涵蓋 CRUD、執行引擎、APScheduler 註冊/移除、動態載入。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest


# ── 共用 mock 工具 ────────────────────────────────────────────


def _make_task_row(
    name: str = "test-task",
    trigger_type: str = "cron",
    executor_type: str = "agent",
    is_enabled: bool = True,
) -> dict:
    """產生模擬的 DB task row"""
    return {
        "id": uuid4(),
        "name": name,
        "description": "測試排程",
        "trigger_type": trigger_type,
        "trigger_config": {"hour": "8", "minute": "0"} if trigger_type == "cron" else {"hours": 1},
        "executor_type": executor_type,
        "executor_config": (
            {"agent_name": "bot", "prompt": "test"} if executor_type == "agent"
            else {"skill": "test-skill", "script": "run.py", "input": ""}
        ),
        "is_enabled": is_enabled,
        "created_by": 1,
        "last_run_at": None,
        "next_run_at": None,
        "last_run_success": None,
        "last_run_error": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


class _DictRecord(dict):
    """模擬 asyncpg Record（同時支援 dict() 和 key 存取）"""
    pass


class _CM:
    """Mock connection context manager"""
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


# ============================================================
# CRUD 測試
# ============================================================


@pytest.mark.asyncio
async def test_create_scheduled_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試建立排程"""
    from ching_tech_os.services import task_scheduler

    row = _make_task_row()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_DictRecord(row))
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    result = await task_scheduler.create_scheduled_task(
        {"name": "new-task", "trigger_type": "cron", "trigger_config": {"hour": "9"},
         "executor_type": "agent", "executor_config": {"agent_name": "bot", "prompt": "hi"}}
    )
    conn.fetchrow.assert_awaited_once()
    assert "INSERT INTO scheduled_tasks" in conn.fetchrow.call_args[0][0]


@pytest.mark.asyncio
async def test_list_scheduled_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試查詢排程列表"""
    from ching_tech_os.services import task_scheduler

    rows = [_DictRecord(_make_task_row(f"task-{i}")) for i in range(3)]
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    result = await task_scheduler.list_scheduled_tasks()
    assert len(result) == 3

    # 測試 is_enabled 篩選
    await task_scheduler.list_scheduled_tasks(is_enabled=True)
    assert "is_enabled" in conn.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_get_scheduled_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試查詢單一排程"""
    from ching_tech_os.services import task_scheduler

    task_id = uuid4()
    row = _make_task_row()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_DictRecord(row))
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    result = await task_scheduler.get_scheduled_task(task_id)
    assert result is not None


@pytest.mark.asyncio
async def test_get_scheduled_task_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試查詢不存在的排程"""
    from ching_tech_os.services import task_scheduler

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    result = await task_scheduler.get_scheduled_task(uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_delete_scheduled_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試刪除排程"""
    from ching_tech_os.services import task_scheduler

    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 1")
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    result = await task_scheduler.delete_scheduled_task(uuid4())
    assert result is True


@pytest.mark.asyncio
async def test_delete_scheduled_task_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試刪除不存在的排程"""
    from ching_tech_os.services import task_scheduler

    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 0")
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    result = await task_scheduler.delete_scheduled_task(uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_toggle_scheduled_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試切換啟用狀態"""
    from ching_tech_os.services import task_scheduler

    row = _make_task_row()
    row["is_enabled"] = False
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_DictRecord(row))
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    result = await task_scheduler.toggle_scheduled_task(uuid4(), False)
    assert result is not None
    assert result["is_enabled"] is False


@pytest.mark.asyncio
async def test_update_task_run_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試更新執行結果"""
    from ching_tech_os.services import task_scheduler

    conn = AsyncMock()
    conn.execute = AsyncMock()
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    await task_scheduler.update_task_run_result(uuid4(), success=True)
    conn.execute.assert_awaited_once()
    sql = conn.execute.call_args[0][0]
    assert "last_run_at" in sql
    assert "last_run_success" in sql


# ============================================================
# 執行引擎測試
# ============================================================


@pytest.mark.asyncio
async def test_execute_agent_task_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試 Agent 模式執行成功"""
    from ching_tech_os.services import task_scheduler

    task = _make_task_row(executor_type="agent")
    task_id = task["id"]

    monkeypatch.setattr(
        task_scheduler, "get_scheduled_task",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        task_scheduler, "update_task_run_result",
        AsyncMock(),
    )

    mock_agent = {
        "model": "sonnet",
        "tools": None,
        "system_prompt": {"content": "test prompt"},
    }
    mock_response = SimpleNamespace(success=True, message="ok", error=None)

    with patch("ching_tech_os.services.task_scheduler.get_connection"):
        monkeypatch.setattr(
            "ching_tech_os.services.ai_manager.get_agent_by_name",
            AsyncMock(return_value=mock_agent),
        )
        monkeypatch.setattr(
            "ching_tech_os.services.claude_agent.call_claude",
            AsyncMock(return_value=mock_response),
        )

        await task_scheduler.execute_dynamic_task(task_id)

    task_scheduler.update_task_run_result.assert_awaited_once()
    args = task_scheduler.update_task_run_result.call_args
    assert args[1]["success"] is True


@pytest.mark.asyncio
async def test_execute_agent_task_agent_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試 Agent 不存在的情境"""
    from ching_tech_os.services import task_scheduler

    task = _make_task_row(executor_type="agent")
    task_id = task["id"]

    monkeypatch.setattr(
        task_scheduler, "get_scheduled_task",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        task_scheduler, "update_task_run_result",
        AsyncMock(),
    )

    with patch("ching_tech_os.services.task_scheduler.get_connection"):
        monkeypatch.setattr(
            "ching_tech_os.services.ai_manager.get_agent_by_name",
            AsyncMock(return_value=None),
        )

        await task_scheduler.execute_dynamic_task(task_id)

    # 應該記錄為失敗
    args = task_scheduler.update_task_run_result.call_args
    assert args[1]["success"] is False
    assert "不存在" in (args[1].get("error") or "")


@pytest.mark.asyncio
async def test_execute_skill_script_task_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試 Skill Script 模式執行成功"""
    from ching_tech_os.services import task_scheduler

    task = _make_task_row(executor_type="skill_script")
    task_id = task["id"]

    monkeypatch.setattr(
        task_scheduler, "get_scheduled_task",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        task_scheduler, "update_task_run_result",
        AsyncMock(),
    )

    with patch("ching_tech_os.services.task_scheduler.get_connection"):
        monkeypatch.setattr(
            "ching_tech_os.services.mcp.skill_script_tools.run_skill_script",
            AsyncMock(return_value=json.dumps({"success": True})),
        )

        await task_scheduler.execute_dynamic_task(task_id)

    args = task_scheduler.update_task_run_result.call_args
    assert args[1]["success"] is True


# ============================================================
# APScheduler 註冊/移除測試
# ============================================================


def test_register_dynamic_job_cron(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試 cron 類型的排程註冊"""
    from ching_tech_os.services import task_scheduler

    mock_scheduler = MagicMock()
    monkeypatch.setattr("ching_tech_os.services.task_scheduler.scheduler", mock_scheduler, raising=False)
    # 需要 mock scheduler 的 import
    monkeypatch.setattr("ching_tech_os.services.scheduler.scheduler", mock_scheduler)

    task = _make_task_row(trigger_type="cron")
    task_scheduler.register_dynamic_job(task)

    mock_scheduler.add_job.assert_called_once()
    call_kwargs = mock_scheduler.add_job.call_args
    assert call_kwargs.kwargs["id"] == f"dynamic:{task['id']}"
    assert call_kwargs.kwargs["replace_existing"] is True
    assert call_kwargs.kwargs["max_instances"] == 1


def test_register_dynamic_job_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試 interval 類型的排程註冊"""
    from ching_tech_os.services import task_scheduler

    mock_scheduler = MagicMock()
    monkeypatch.setattr("ching_tech_os.services.task_scheduler.scheduler", mock_scheduler, raising=False)
    monkeypatch.setattr("ching_tech_os.services.scheduler.scheduler", mock_scheduler)

    task = _make_task_row(trigger_type="interval")
    task_scheduler.register_dynamic_job(task)

    mock_scheduler.add_job.assert_called_once()


def test_unregister_dynamic_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試排程移除"""
    from ching_tech_os.services import task_scheduler

    mock_scheduler = MagicMock()
    monkeypatch.setattr("ching_tech_os.services.scheduler.scheduler", mock_scheduler)

    task_id = uuid4()
    task_scheduler.unregister_dynamic_job(task_id)

    mock_scheduler.remove_job.assert_called_once_with(f"dynamic:{task_id}")


def test_unregister_nonexistent_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試移除不存在的排程不會拋出例外"""
    from ching_tech_os.services import task_scheduler

    mock_scheduler = MagicMock()
    mock_scheduler.remove_job.side_effect = Exception("not found")
    monkeypatch.setattr("ching_tech_os.services.scheduler.scheduler", mock_scheduler)

    # 不應拋出
    task_scheduler.unregister_dynamic_job(uuid4())


def test_make_job_id() -> None:
    """測試 Job ID 格式"""
    from ching_tech_os.services.task_scheduler import _make_job_id

    task_id = uuid4()
    assert _make_job_id(task_id) == f"dynamic:{task_id}"


# ============================================================
# 動態載入測試
# ============================================================


@pytest.mark.asyncio
async def test_load_dynamic_tasks_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試從 DB 載入動態排程"""
    from ching_tech_os.services import task_scheduler

    tasks = [_make_task_row(f"task-{i}") for i in range(3)]
    monkeypatch.setattr(
        task_scheduler, "list_scheduled_tasks",
        AsyncMock(return_value=tasks),
    )
    monkeypatch.setattr(
        task_scheduler, "register_dynamic_job",
        MagicMock(),
    )

    loaded = await task_scheduler.load_dynamic_tasks()
    assert loaded == 3
    assert task_scheduler.register_dynamic_job.call_count == 3


@pytest.mark.asyncio
async def test_load_dynamic_tasks_db_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試 DB 連線失敗時不拋出例外"""
    from ching_tech_os.services import task_scheduler

    monkeypatch.setattr(
        task_scheduler, "list_scheduled_tasks",
        AsyncMock(side_effect=RuntimeError("DB down")),
    )

    loaded = await task_scheduler.load_dynamic_tasks()
    assert loaded == 0  # 不應拋出例外


@pytest.mark.asyncio
async def test_load_dynamic_tasks_partial_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試部分排程註冊失敗"""
    from ching_tech_os.services import task_scheduler

    tasks = [_make_task_row(f"task-{i}") for i in range(3)]
    monkeypatch.setattr(
        task_scheduler, "list_scheduled_tasks",
        AsyncMock(return_value=tasks),
    )

    call_count = 0

    def mock_register(task):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("register failed")

    monkeypatch.setattr(task_scheduler, "register_dynamic_job", mock_register)

    loaded = await task_scheduler.load_dynamic_tasks()
    assert loaded == 2  # 2 成功，1 失敗
