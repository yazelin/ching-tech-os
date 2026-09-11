"""動態排程任務管理服務

提供排程的 CRUD 操作、APScheduler 註冊/移除、以及排程任務執行邏輯。
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..database import get_connection

logger = logging.getLogger(__name__)


# ============================================================
# CRUD 操作
# ============================================================


async def create_scheduled_task(data: dict, created_by: int | None = None) -> dict:
    """建立排程任務"""
    task_id = uuid4()
    now = datetime.now(timezone.utc)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO scheduled_tasks
                (id, name, description, trigger_type, trigger_config,
                 executor_type, executor_config, is_enabled, created_by,
                 created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7::jsonb, $8, $9, $10, $11)
            RETURNING *
            """,
            task_id,
            data["name"],
            data.get("description"),
            data["trigger_type"],
            _to_json(data["trigger_config"]),
            data["executor_type"],
            _to_json(data["executor_config"]),
            data.get("is_enabled", True),
            created_by,
            now,
            now,
        )
        return dict(row)


async def list_scheduled_tasks(
    is_enabled: bool | None = None,
) -> list[dict]:
    """查詢排程列表"""
    async with get_connection() as conn:
        if is_enabled is not None:
            rows = await conn.fetch(
                "SELECT * FROM scheduled_tasks WHERE is_enabled = $1 ORDER BY created_at DESC",
                is_enabled,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM scheduled_tasks ORDER BY created_at DESC"
            )
        return [dict(r) for r in rows]


async def get_scheduled_task(task_id: UUID) -> dict | None:
    """查詢單一排程"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM scheduled_tasks WHERE id = $1", task_id
        )
        return dict(row) if row else None


async def update_scheduled_task(task_id: UUID, data: dict) -> dict | None:
    """更新排程（僅更新提供的欄位）"""
    # 過濾掉 None 值
    fields = {k: v for k, v in data.items() if v is not None}
    if not fields:
        return await get_scheduled_task(task_id)

    fields["updated_at"] = datetime.now(timezone.utc)

    # 動態組裝 SET 子句
    set_parts = []
    params = []
    idx = 1
    for key, value in fields.items():
        if key in ("trigger_config", "executor_config"):
            set_parts.append(f"{key} = ${idx}::jsonb")
            params.append(_to_json(value))
        else:
            set_parts.append(f"{key} = ${idx}")
            params.append(value)
        idx += 1

    params.append(task_id)
    sql = f"UPDATE scheduled_tasks SET {', '.join(set_parts)} WHERE id = ${idx} RETURNING *"

    async with get_connection() as conn:
        row = await conn.fetchrow(sql, *params)
        return dict(row) if row else None


async def delete_scheduled_task(task_id: UUID) -> bool:
    """刪除排程"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM scheduled_tasks WHERE id = $1", task_id
        )
        return result == "DELETE 1"


async def toggle_scheduled_task(task_id: UUID, is_enabled: bool) -> dict | None:
    """切換啟用狀態"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE scheduled_tasks
            SET is_enabled = $1, updated_at = $2
            WHERE id = $3
            RETURNING *
            """,
            is_enabled,
            datetime.now(timezone.utc),
            task_id,
        )
        return dict(row) if row else None


async def update_task_run_result(
    task_id: UUID, success: bool, error: str | None = None
) -> int:
    """更新排程執行結果，回傳更新後的連續失敗次數

    成功時 consecutive_failures 歸零，失敗時 +1。
    """
    async with get_connection() as conn:
        value = await conn.fetchval(
            """
            UPDATE scheduled_tasks
            SET last_run_at = $1,
                last_run_success = $2,
                last_run_error = $3,
                consecutive_failures = CASE
                    WHEN $2 THEN 0
                    ELSE consecutive_failures + 1
                END,
                updated_at = $1
            WHERE id = $4
            RETURNING consecutive_failures
            """,
            datetime.now(timezone.utc),
            success,
            error,
            task_id,
        )
        return int(value) if value is not None else 0


# ============================================================
# APScheduler 註冊/移除
# ============================================================


def _make_job_id(task_id: UUID) -> str:
    """產生動態排程的 Job ID"""
    return f"dynamic:{task_id}"


def _build_trigger(trigger_type: str, trigger_config: dict):
    """從設定建立 APScheduler trigger"""
    if trigger_type == "cron":
        cron_fields = {
            k: v
            for k, v in trigger_config.items()
            if k in ("minute", "hour", "day", "month", "day_of_week")
        }
        return CronTrigger(**cron_fields)
    else:
        interval_fields = {
            k: v
            for k, v in trigger_config.items()
            if k in ("weeks", "days", "hours", "minutes", "seconds")
        }
        if not interval_fields:
            interval_fields = {"hours": 1}
        return IntervalTrigger(**interval_fields)


def register_dynamic_job(task: dict) -> None:
    """將排程定義註冊到 APScheduler"""
    from .scheduler import scheduler

    job_id = _make_job_id(task["id"])
    trigger = _build_trigger(task["trigger_type"], task["trigger_config"])

    scheduler.add_job(
        _execute_dynamic_task_wrapper,
        trigger,
        args=[task["id"]],
        id=job_id,
        name=task["name"],
        replace_existing=True,
        max_instances=1,
    )
    logger.info("已註冊動態排程: %s (%s)", task["name"], job_id)


def unregister_dynamic_job(task_id: UUID) -> None:
    """從 APScheduler 移除排程"""
    from .scheduler import scheduler

    job_id = _make_job_id(task_id)
    try:
        scheduler.remove_job(job_id)
        logger.info("已移除動態排程: %s", job_id)
    except Exception:
        # job 可能不存在（已停用或從未註冊）
        logger.debug("移除動態排程 %s 失敗（可能不存在）", job_id)


def get_dynamic_job_next_run(task_id: UUID) -> datetime | None:
    """取得動態排程的下次執行時間"""
    from .scheduler import scheduler

    job_id = _make_job_id(task_id)
    job = scheduler.get_job(job_id)
    if job and job.next_run_time:
        return job.next_run_time
    return None


# ============================================================
# 排程任務執行
# ============================================================


async def execute_dynamic_task(task_id: UUID) -> None:
    """執行動態排程任務（根據 executor_type 分派）"""
    task = await get_scheduled_task(task_id)
    if not task:
        logger.error("動態排程任務不存在: %s", task_id)
        return

    executor_type = task["executor_type"]
    executor_config = task["executor_config"]

    logger.info("開始執行動態排程: %s (type=%s)", task["name"], executor_type)

    # 排程建立者作為 ctos_user_id 的 fallback（繼承管理員權限）
    fallback_user_id = task.get("created_by")

    notify = _notify_target(executor_config, task["name"])
    succeeded = False
    result_text = ""

    try:
        if executor_type == "agent":
            result_text = await _execute_agent_task(
                task["name"], executor_config, fallback_user_id
            )
        elif executor_type == "skill_script":
            result_text = await _execute_skill_script_task(
                task["name"], executor_config, fallback_user_id
            )
        else:
            raise ValueError(f"未知的 executor_type: {executor_type}")

        await update_task_run_result(task_id, success=True)
        succeeded = True
        logger.info("動態排程執行成功: %s", task["name"])

    except Exception as e:
        error_msg = str(e)[:1000]
        failures = await update_task_run_result(task_id, success=False, error=error_msg)
        logger.error("動態排程執行失敗: %s - %s", task["name"], error_msg)
        await _notify_result(notify, task["name"], False, error_msg, failures)

    # 成功推播放在 try 之外：推播或組訊息出錯不該把已記成功的任務改記成失敗
    if succeeded:
        await _notify_result(notify, task["name"], True, result_text)


async def _execute_agent_task(
    task_name: str, config: dict, fallback_user_id: int | None = None
) -> str:
    """執行 Agent 模式排程，回傳 Agent 的回應內容（供推播使用）"""
    import time

    from .ai_manager import create_log, get_agent_by_name
    from .claude_agent import call_claude
    from ..models.ai import AiLogCreate

    agent_name = config["agent_name"]
    prompt = config["prompt"]
    ctos_user_id = config.get("ctos_user_id") or fallback_user_id

    agent = await get_agent_by_name(agent_name)
    if not agent:
        raise ValueError(f"Agent 不存在: {agent_name}")

    # 組裝 system_prompt
    system_prompt = None
    if agent.get("system_prompt") and agent["system_prompt"].get("content"):
        system_prompt = agent["system_prompt"]["content"]

    # 取得 Agent 設定
    model = agent.get("model", "sonnet")
    tools = agent.get("tools")

    start_time = time.time()
    response = await asyncio.wait_for(
        call_claude(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            ctos_user_id=ctos_user_id,
        ),
        timeout=180,
    )
    duration_ms = int((time.time() - start_time) * 1000)

    # 記錄 AI Log
    try:
        log_data = AiLogCreate(
            agent_id=agent.get("id"),
            context_type="scheduler",
            context_id=task_name[:64],  # AiLogCreate.context_id max_length=64
            input_prompt=prompt,
            system_prompt=system_prompt,
            allowed_tools=tools,
            raw_response=response.message,
            parsed_response={"source": "scheduler", "task_name": task_name},
            model=model,
            success=response.success,
            error_message=response.error,
            duration_ms=duration_ms,
            input_tokens=getattr(response, "input_tokens", None),
            output_tokens=getattr(response, "output_tokens", None),
            # 排程沒有互動使用者，記建立者（executor_config 明寫的優先）
            user_id=ctos_user_id,
        )
        await create_log(log_data)
    except Exception as e:
        logger.warning("排程 AI Log 記錄失敗: %s", e)

    if not response.success:
        raise RuntimeError(f"Agent 執行失敗: {response.error or response.message}")

    return response.message or ""


async def _execute_skill_script_task(
    task_name: str, config: dict, fallback_user_id: int | None = None
) -> str:
    """執行 Skill Script 模式排程（系統權限，跳過使用者權限檢查）

    回傳 script 的輸出內容（供推播使用），並寫一筆 ai_logs 留痕。
    """
    from ..models.ai import AiLogCreate
    from ..skills import get_skill_manager
    from ..skills.script_runner import ScriptRunner
    from .ai_manager import create_log

    skill = config["skill"]
    script = config["script"]
    input_data = config.get("input", "")

    sm = get_skill_manager()

    # 驗證 skill 和 script 存在
    skill_obj = await sm.get_skill(skill)
    if not skill_obj:
        raise RuntimeError(f"Skill not found: {skill}")
    if not await sm.has_scripts(skill):
        raise RuntimeError(f"Skill '{skill}' has no scripts")
    script_path = await sm.get_script_path(skill, script)
    if not script_path:
        raise RuntimeError(f"Script not found: {skill}/{script}")

    skill_dir = await sm.get_skill_dir(skill)
    if not skill_dir:
        raise RuntimeError(f"Skill directory not found: {skill}")

    # 取得環境變數覆寫
    env_overrides = sm.get_skill_env_overrides(skill_obj)

    # 排程任務 = 系統行為，直接執行不檢查使用者權限
    runner = ScriptRunner(skill_dir.parent)
    result = await runner.execute_path(
        script_path, skill, input=input_data, env_overrides=env_overrides
    )

    # execute_path 回傳 dict: {success, output, error, duration_ms}
    success = bool(result.get("success", False))
    output = result.get("output") or ""
    error = result.get("error") or None

    # 記錄 AI Log（與 Agent 模式一致，失敗只 warning 不影響排程結果）
    try:
        log_data = AiLogCreate(
            context_type="scheduler_script",
            context_id=task_name[:64],  # AiLogCreate.context_id max_length=64
            # input_data 本身已是 JSON 字串，不再編碼一次
            input_prompt=f"{skill}/{script} {input_data}",
            raw_response=output,
            parsed_response={
                "source": "scheduler_script",
                "task_name": task_name,
                "skill": skill,
                "script": script,
            },
            success=success,
            error_message=error,
            duration_ms=result.get("duration_ms"),
            # 排程沒有互動使用者，記 scheduled_tasks.created_by
            user_id=fallback_user_id,
        )
        await create_log(log_data)
    except Exception as e:
        logger.warning("排程 Script AI Log 記錄失敗: %s", e)

    if not success:
        raise RuntimeError(f"Skill Script 執行失敗: {error or output}")

    return output


# ============================================================
# 執行結果推播
# ============================================================

# 推播訊息長度上限（LINE 單則上限 5000 字，留餘裕）
_NOTIFY_MAX_LEN = 4000


# 支援推播的平台（與 proactive_push_service 一致）
_NOTIFY_PLATFORMS = ("line", "telegram")


def _notify_target(config: dict | None, task_name: str = "") -> dict | None:
    """從 executor_config 取出推播設定

    格式：``notify: {platform, target_id, is_group, group_id}``。
    沒設定就回傳 None，維持不推播的既有行為；設了但內容不完整則另外寫 warning。
    """
    notify = (config or {}).get("notify")
    if not isinstance(notify, dict):
        return None
    platform = notify.get("platform")
    if platform not in _NOTIFY_PLATFORMS:
        logger.warning(
            "排程 %s 的推播設定 platform 無效（%r，需為 %s），略過推播",
            task_name,
            platform,
            " / ".join(_NOTIFY_PLATFORMS),
        )
        return None
    if not (notify.get("target_id") or notify.get("group_id")):
        logger.warning(
            "排程 %s 的推播設定缺少 target_id / group_id，略過推播", task_name
        )
        return None
    return notify


def _format_notify_message(
    task_name: str, success: bool, body: str | None, failures: int
) -> str:
    """組裝推播訊息（成功與失敗分開）"""
    if success:
        text = f"【排程】{task_name} 完成\n{body or ''}"
    else:
        text = f"【排程失敗】{task_name}（連續第 {failures} 次）\n{body or ''}"
    return text[:_NOTIFY_MAX_LEN]


async def _notify_result(
    notify: dict | None,
    task_name: str,
    success: bool,
    body: str | None,
    failures: int = 0,
) -> None:
    """把排程結果推回指定對話（推播失敗只 warning，不影響排程結果）"""
    if not notify:
        return

    try:
        from . import proactive_push_service

        message = _format_notify_message(task_name, success, body, failures)
        await proactive_push_service.notify_job_complete(
            platform=notify["platform"],
            platform_user_id=notify.get("target_id") or "",
            is_group=bool(notify.get("is_group")),
            group_id=notify.get("group_id"),
            message=message,
        )
    except Exception as e:
        logger.warning("排程結果推播失敗（%s）: %s", task_name, e)


async def _execute_dynamic_task_wrapper(task_id: UUID) -> None:
    """APScheduler 回呼包裝器

    AsyncIOScheduler 原生支援 async 函式，直接 await 即可。
    """
    await execute_dynamic_task(task_id)


# ============================================================
# 啟動時載入
# ============================================================


async def load_dynamic_tasks() -> int:
    """從 DB 載入所有啟用的動態排程並註冊到 APScheduler

    回傳成功載入的排程數量。
    """
    try:
        tasks = await list_scheduled_tasks(is_enabled=True)
        loaded = 0
        for task in tasks:
            try:
                register_dynamic_job(task)
                loaded += 1
            except Exception as e:
                logger.error(
                    "載入動態排程 %s 失敗: %s", task.get("name", task["id"]), e
                )
        logger.info("已載入 %d/%d 筆動態排程", loaded, len(tasks))
        return loaded
    except Exception as e:
        logger.error("載入動態排程失敗（DB 連線問題）: %s", e)
        return 0


# ============================================================
# 工具函式
# ============================================================


def _to_json(data) -> dict:
    """確保 JSONB 參數為 dict（asyncpg 自訂 codec 會處理序列化）"""
    import json

    if isinstance(data, str):
        return json.loads(data)
    return data
