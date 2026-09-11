"""排程執行結果推播測試（issue #182）。

涵蓋：成功推播、失敗推播帶連續次數、未設定 notify 不推、
平台開關關閉時不推、推播丟例外不影響排程與 AI Log、連續失敗計數。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ching_tech_os.services import task_scheduler


# ── 共用 mock 工具 ────────────────────────────────────────────

_NOTIFY = {
    "platform": "telegram",
    "target_id": "12345",
    "is_group": False,
    "group_id": None,
}


class _CM:
    """Mock connection context manager"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _agent_task(notify: dict | None = None) -> dict:
    config: dict = {"agent_name": "bot", "prompt": "每日盤點"}
    if notify is not None:
        config["notify"] = notify
    return {
        "id": uuid4(),
        "name": "每日盤點",
        "description": "測試排程",
        "trigger_type": "cron",
        "trigger_config": {"hour": "8", "minute": "0"},
        "executor_type": "agent",
        "executor_config": config,
        "is_enabled": True,
        "created_by": 1,
        "last_run_at": None,
        "next_run_at": None,
        "last_run_success": None,
        "last_run_error": None,
        "consecutive_failures": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


def _skill_task(notify: dict | None = None) -> dict:
    task = _agent_task(notify)
    task["executor_type"] = "skill_script"
    config: dict = {
        "skill": "test-skill",
        "script": "run.py",
        "input": '{"days": 7}',
    }
    if notify is not None:
        config["notify"] = notify
    task["executor_config"] = config
    return task


def _patch_agent_run(
    monkeypatch: pytest.MonkeyPatch,
    response: SimpleNamespace,
    create_log: AsyncMock | None = None,
) -> AsyncMock:
    """讓 _execute_agent_task 跑得動：agent 查得到、call_claude 回傳指定結果"""
    log_mock = create_log or AsyncMock()
    monkeypatch.setattr(
        "ching_tech_os.services.ai_manager.get_agent_by_name",
        AsyncMock(return_value={"model": "sonnet", "tools": None, "system_prompt": None}),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.claude_agent.call_claude",
        AsyncMock(return_value=response),
    )
    monkeypatch.setattr("ching_tech_os.services.ai_manager.create_log", log_mock)
    return log_mock


# ============================================================
# 成功 / 失敗推播
# ============================================================


@pytest.mark.asyncio
async def test_agent_success_notifies_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    """成功時推播成功訊息，AI Log 照寫"""
    task = _agent_task(_NOTIFY)
    monkeypatch.setattr(task_scheduler, "get_scheduled_task", AsyncMock(return_value=task))
    monkeypatch.setattr(task_scheduler, "update_task_run_result", AsyncMock(return_value=0))

    create_log = _patch_agent_run(
        monkeypatch, SimpleNamespace(success=True, message="庫存正常", error=None)
    )
    push = AsyncMock()
    monkeypatch.setattr(
        "ching_tech_os.services.proactive_push_service.notify_job_complete", push
    )

    await task_scheduler.execute_dynamic_task(task["id"])

    create_log.assert_awaited_once()
    push.assert_awaited_once()
    kwargs = push.call_args.kwargs
    assert kwargs["message"] == "【排程】每日盤點 完成\n庫存正常"
    assert kwargs["platform"] == "telegram"
    assert kwargs["platform_user_id"] == "12345"
    assert kwargs["is_group"] is False
    assert kwargs["group_id"] is None

    assert task_scheduler.update_task_run_result.call_args.kwargs["success"] is True


@pytest.mark.asyncio
async def test_agent_failure_notifies_with_failure_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """失敗時推播失敗訊息，帶「連續第 N 次」（前一次已失敗過一次 → 這次是第 2 次）"""
    task = _agent_task(_NOTIFY)
    monkeypatch.setattr(task_scheduler, "get_scheduled_task", AsyncMock(return_value=task))
    # DB 回傳的是「更新後」的連續失敗次數：前一次是 1，這次變 2
    monkeypatch.setattr(task_scheduler, "update_task_run_result", AsyncMock(return_value=2))

    _patch_agent_run(
        monkeypatch, SimpleNamespace(success=False, message="", error="agent boom")
    )
    push = AsyncMock()
    monkeypatch.setattr(
        "ching_tech_os.services.proactive_push_service.notify_job_complete", push
    )

    await task_scheduler.execute_dynamic_task(task["id"])

    push.assert_awaited_once()
    message = push.call_args.kwargs["message"]
    assert message.startswith("【排程失敗】每日盤點（連續第 2 次）")
    assert "agent boom" in message
    assert task_scheduler.update_task_run_result.call_args.kwargs["success"] is False


@pytest.mark.asyncio
async def test_execute_agent_task_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """_execute_agent_task 本身仍然 raise RuntimeError（execute_dynamic_task 才吞）"""
    _patch_agent_run(
        monkeypatch, SimpleNamespace(success=False, message="", error="agent boom")
    )
    with pytest.raises(RuntimeError, match="agent boom"):
        await task_scheduler._execute_agent_task(
            "每日盤點", {"agent_name": "bot", "prompt": "x"}
        )


@pytest.mark.asyncio
async def test_no_notify_config_never_pushes(monkeypatch: pytest.MonkeyPatch) -> None:
    """executor_config 沒有 notify 就不推播"""
    task = _agent_task(None)
    monkeypatch.setattr(task_scheduler, "get_scheduled_task", AsyncMock(return_value=task))
    monkeypatch.setattr(task_scheduler, "update_task_run_result", AsyncMock(return_value=0))

    _patch_agent_run(monkeypatch, SimpleNamespace(success=True, message="ok", error=None))
    push = AsyncMock()
    monkeypatch.setattr(
        "ching_tech_os.services.proactive_push_service.notify_job_complete", push
    )

    await task_scheduler.execute_dynamic_task(task["id"])

    push.assert_not_awaited()


@pytest.mark.parametrize(
    "notify",
    [
        {"target_id": "12345"},  # 缺 platform
        {"platform": "slack", "target_id": "12345"},  # 不支援的平台
        {"platform": None, "target_id": "12345"},
        {"platform": "telegram"},  # 缺 target
        "not-a-dict",
    ],
)
def test_notify_target_rejects_incomplete_config(notify) -> None:
    """推播設定不完整或平台值無效時視同沒設定"""
    assert task_scheduler._notify_target({"notify": notify}, "每日盤點") is None
    assert task_scheduler._notify_target({}, "每日盤點") is None
    assert task_scheduler._notify_target(None, "每日盤點") is None


@pytest.mark.parametrize("field", ["target_id", "group_id"])
def test_notify_target_accepts_either_target(field: str) -> None:
    """target_id 或 group_id 任一個有值就成立（負控制：上一個測試不是永遠回 None）"""
    notify = {"platform": "line", field: "abc"}
    assert task_scheduler._notify_target({"notify": notify}, "每日盤點") == notify


def test_notify_target_warns_with_task_name(caplog: pytest.LogCaptureFixture) -> None:
    """平台無效與缺目標兩種情況都要在 warning 裡指名是哪個排程"""
    with caplog.at_level("WARNING"):
        task_scheduler._notify_target(
            {"notify": {"platform": "slack", "target_id": "1"}}, "每日盤點"
        )
        task_scheduler._notify_target({"notify": {"platform": "line"}}, "每日盤點")

    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 2
    assert all("每日盤點" in w for w in warnings)
    assert "platform" in warnings[0]
    assert "target_id" in warnings[1]


def test_notify_message_truncated_to_4000() -> None:
    """推播訊息截斷到 4000 字"""
    text = task_scheduler._format_notify_message("t", True, "x" * 9000, 0)
    assert len(text) == 4000


# ============================================================
# 平台開關關閉
# ============================================================


@pytest.mark.asyncio
async def test_push_disabled_platform_does_not_send(monkeypatch: pytest.MonkeyPatch) -> None:
    """平台主動推播開關關掉時，notify_job_complete 內部就短路，不會真的送出"""
    from ching_tech_os.services import proactive_push_service

    task = _agent_task(_NOTIFY)
    monkeypatch.setattr(task_scheduler, "get_scheduled_task", AsyncMock(return_value=task))
    monkeypatch.setattr(task_scheduler, "update_task_run_result", AsyncMock(return_value=0))
    _patch_agent_run(monkeypatch, SimpleNamespace(success=True, message="ok", error=None))

    monkeypatch.setattr(
        proactive_push_service, "_is_push_enabled", AsyncMock(return_value=False)
    )
    push_line = AsyncMock()
    push_telegram = AsyncMock()
    monkeypatch.setattr(proactive_push_service, "_push_line", push_line)
    monkeypatch.setattr(proactive_push_service, "_push_telegram", push_telegram)

    await task_scheduler.execute_dynamic_task(task["id"])

    proactive_push_service._is_push_enabled.assert_awaited_once_with("telegram")
    push_line.assert_not_awaited()
    push_telegram.assert_not_awaited()


@pytest.mark.asyncio
async def test_push_enabled_platform_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    """開關開啟時走到實際推播（負控制：確認上一個測試不是因為路徑沒走到才沒送）"""
    from ching_tech_os.services import proactive_push_service

    task = _agent_task(_NOTIFY)
    monkeypatch.setattr(task_scheduler, "get_scheduled_task", AsyncMock(return_value=task))
    monkeypatch.setattr(task_scheduler, "update_task_run_result", AsyncMock(return_value=0))
    _patch_agent_run(monkeypatch, SimpleNamespace(success=True, message="ok", error=None))

    monkeypatch.setattr(
        proactive_push_service, "_is_push_enabled", AsyncMock(return_value=True)
    )
    push_telegram = AsyncMock()
    monkeypatch.setattr(proactive_push_service, "_push_telegram", push_telegram)

    await task_scheduler.execute_dynamic_task(task["id"])

    push_telegram.assert_awaited_once_with("12345", "【排程】每日盤點 完成\nok")


# ============================================================
# 推播丟例外
# ============================================================


@pytest.mark.asyncio
async def test_push_exception_does_not_break_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """推播服務丟例外時，排程照樣算成功、AI Log 照寫、例外不外流"""
    task = _agent_task(_NOTIFY)
    monkeypatch.setattr(task_scheduler, "get_scheduled_task", AsyncMock(return_value=task))
    update = AsyncMock(return_value=0)
    monkeypatch.setattr(task_scheduler, "update_task_run_result", update)

    create_log = _patch_agent_run(
        monkeypatch, SimpleNamespace(success=True, message="ok", error=None)
    )
    monkeypatch.setattr(
        "ching_tech_os.services.proactive_push_service.notify_job_complete",
        AsyncMock(side_effect=RuntimeError("push down")),
    )

    await task_scheduler.execute_dynamic_task(task["id"])

    create_log.assert_awaited_once()
    update.assert_awaited_once()
    assert update.call_args.kwargs["success"] is True


@pytest.mark.asyncio
async def test_success_notify_error_does_not_rerecord_as_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """成功推播在 try 之外：推播路徑丟例外也不能把已記成功的任務改記成失敗"""
    task = _agent_task(_NOTIFY)
    monkeypatch.setattr(task_scheduler, "get_scheduled_task", AsyncMock(return_value=task))
    update = AsyncMock(return_value=0)
    monkeypatch.setattr(task_scheduler, "update_task_run_result", update)
    _patch_agent_run(monkeypatch, SimpleNamespace(success=True, message="ok", error=None))

    # _notify_result 自己的 try/except 之外再破一次（例如 helper 本身出錯）
    monkeypatch.setattr(
        task_scheduler, "_notify_result", AsyncMock(side_effect=RuntimeError("boom"))
    )

    with pytest.raises(RuntimeError, match="boom"):
        await task_scheduler.execute_dynamic_task(task["id"])

    # 只記一次，且是成功；沒有被 except 分支改寫成失敗
    update.assert_awaited_once()
    assert update.call_args.kwargs["success"] is True


# ============================================================
# Skill Script：AI Log + 推播
# ============================================================


def _patch_skill_run(result: dict):
    mock_sm = MagicMock()
    mock_sm.get_skill = AsyncMock(return_value=MagicMock(requires_app=None))
    mock_sm.has_scripts = AsyncMock(return_value=True)
    mock_sm.get_script_path = AsyncMock(return_value="/fake/path.py")
    mock_sm.get_skill_dir = AsyncMock(return_value=Path("/fake/skill"))
    mock_sm.get_skill_env_overrides = MagicMock(return_value={})

    runner = MagicMock()
    runner.execute_path = AsyncMock(return_value=result)

    return (
        patch("ching_tech_os.skills.get_skill_manager", return_value=mock_sm),
        patch("ching_tech_os.skills.script_runner.ScriptRunner", return_value=runner),
    )


@pytest.mark.asyncio
async def test_skill_script_writes_ai_log_and_notifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skill Script 模式也寫 ai_logs（context_type=scheduler_script）並推播"""
    task = _skill_task(_NOTIFY)
    monkeypatch.setattr(task_scheduler, "get_scheduled_task", AsyncMock(return_value=task))
    monkeypatch.setattr(task_scheduler, "update_task_run_result", AsyncMock(return_value=0))

    create_log = AsyncMock()
    monkeypatch.setattr("ching_tech_os.services.ai_manager.create_log", create_log)
    push = AsyncMock()
    monkeypatch.setattr(
        "ching_tech_os.services.proactive_push_service.notify_job_complete", push
    )

    sm_patch, runner_patch = _patch_skill_run(
        {"success": True, "output": "腳本輸出", "error": "", "duration_ms": 42}
    )
    with sm_patch, runner_patch:
        await task_scheduler.execute_dynamic_task(task["id"])

    create_log.assert_awaited_once()
    log = create_log.call_args[0][0]
    assert log.context_type == "scheduler_script"
    assert log.context_id == "每日盤點"
    # input 本身已是 JSON 字串，不應再被 json.dumps 包一層引號
    assert log.input_prompt == 'test-skill/run.py {"days": 7}'
    assert log.raw_response == "腳本輸出"
    assert log.success is True
    assert log.duration_ms == 42

    push.assert_awaited_once()
    assert push.call_args.kwargs["message"] == "【排程】每日盤點 完成\n腳本輸出"


@pytest.mark.asyncio
async def test_skill_script_failure_logs_and_notifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skill Script 失敗時 ai_logs 記 success=False，推播帶連續次數"""
    task = _skill_task(_NOTIFY)
    monkeypatch.setattr(task_scheduler, "get_scheduled_task", AsyncMock(return_value=task))
    monkeypatch.setattr(task_scheduler, "update_task_run_result", AsyncMock(return_value=3))

    create_log = AsyncMock()
    monkeypatch.setattr("ching_tech_os.services.ai_manager.create_log", create_log)
    push = AsyncMock()
    monkeypatch.setattr(
        "ching_tech_os.services.proactive_push_service.notify_job_complete", push
    )

    sm_patch, runner_patch = _patch_skill_run(
        {"success": False, "output": "", "error": "script boom", "duration_ms": 7}
    )
    with sm_patch, runner_patch:
        await task_scheduler.execute_dynamic_task(task["id"])

    log = create_log.call_args[0][0]
    assert log.success is False
    assert log.error_message == "script boom"

    assert push.call_args.kwargs["message"].startswith(
        "【排程失敗】每日盤點（連續第 3 次）"
    )


@pytest.mark.asyncio
async def test_skill_script_ai_log_failure_does_not_break_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ai_logs 寫入失敗只 warning，排程仍算成功"""
    task = _skill_task(None)
    monkeypatch.setattr(task_scheduler, "get_scheduled_task", AsyncMock(return_value=task))
    update = AsyncMock(return_value=0)
    monkeypatch.setattr(task_scheduler, "update_task_run_result", update)
    monkeypatch.setattr(
        "ching_tech_os.services.ai_manager.create_log",
        AsyncMock(side_effect=RuntimeError("db down")),
    )

    sm_patch, runner_patch = _patch_skill_run(
        {"success": True, "output": "ok", "error": "", "duration_ms": 1}
    )
    with sm_patch, runner_patch:
        await task_scheduler.execute_dynamic_task(task["id"])

    assert update.call_args.kwargs["success"] is True


# ============================================================
# ai_logs 欄位長度
# ============================================================


@pytest.mark.asyncio
async def test_context_id_truncated_to_64(monkeypatch: pytest.MonkeyPatch) -> None:
    """排程名稱最長 128 字，但 AiLogCreate.context_id 上限 64，兩種模式都要截斷"""
    long_name = "排" * 100

    # Agent 模式
    create_log = _patch_agent_run(
        monkeypatch, SimpleNamespace(success=True, message="ok", error=None)
    )
    await task_scheduler._execute_agent_task(
        long_name, {"agent_name": "bot", "prompt": "x"}
    )
    assert create_log.call_args[0][0].context_id == long_name[:64]

    # Skill Script 模式
    script_log = AsyncMock()
    monkeypatch.setattr("ching_tech_os.services.ai_manager.create_log", script_log)
    sm_patch, runner_patch = _patch_skill_run(
        {"success": True, "output": "ok", "error": "", "duration_ms": 1}
    )
    with sm_patch, runner_patch:
        await task_scheduler._execute_skill_script_task(
            long_name, {"skill": "s", "script": "r.py", "input": ""}
        )
    assert script_log.call_args[0][0].context_id == long_name[:64]


# ============================================================
# 連續失敗計數
# ============================================================


@pytest.mark.asyncio
async def test_update_task_run_result_increments_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """失敗時 consecutive_failures + 1，回傳更新後的次數"""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=2)
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    task_id = uuid4()
    failures = await task_scheduler.update_task_run_result(
        task_id, success=False, error="boom"
    )

    assert failures == 2
    sql, *params = conn.fetchval.call_args[0]
    assert "consecutive_failures = CASE" in sql
    assert "consecutive_failures + 1" in sql
    assert "RETURNING consecutive_failures" in sql
    assert params[1] is False
    assert params[2] == "boom"
    assert params[3] == task_id


@pytest.mark.asyncio
async def test_update_task_run_result_resets_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """成功時 consecutive_failures 歸零"""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    failures = await task_scheduler.update_task_run_result(uuid4(), success=True)

    assert failures == 0
    sql, *params = conn.fetchval.call_args[0]
    assert "WHEN $2 THEN 0" in sql
    assert params[1] is True
    assert params[2] is None


@pytest.mark.asyncio
async def test_update_task_run_result_missing_row_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """排程已被刪除（沒有 row）時回傳 0，不拋例外"""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    monkeypatch.setattr(task_scheduler, "get_connection", lambda: _CM(conn))

    assert await task_scheduler.update_task_run_result(uuid4(), success=False) == 0
