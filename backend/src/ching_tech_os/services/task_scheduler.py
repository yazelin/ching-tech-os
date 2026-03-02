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
) -> None:
    """更新排程執行結果"""
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE scheduled_tasks
            SET last_run_at = $1,
                last_run_success = $2,
                last_run_error = $3,
                updated_at = $1
            WHERE id = $4
            """,
            datetime.now(timezone.utc),
            success,
            error,
            task_id,
        )


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

    try:
        if executor_type == "agent":
            await _execute_agent_task(task["name"], executor_config)
        elif executor_type == "skill_script":
            await _execute_skill_script_task(task["name"], executor_config)
        else:
            raise ValueError(f"未知的 executor_type: {executor_type}")

        await update_task_run_result(task_id, success=True)
        logger.info("動態排程執行成功: %s", task["name"])

    except Exception as e:
        error_msg = str(e)[:1000]
        await update_task_run_result(task_id, success=False, error=error_msg)
        logger.error("動態排程執行失敗: %s - %s", task["name"], error_msg)


async def _execute_agent_task(task_name: str, config: dict) -> None:
    """執行 Agent 模式排程"""
    from .ai_manager import get_agent_by_name
    from .claude_agent import call_claude

    agent_name = config["agent_name"]
    prompt = config["prompt"]
    ctos_user_id = config.get("ctos_user_id")

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

    if not response.success:
        raise RuntimeError(f"Agent 執行失敗: {response.error or response.message}")


async def _execute_skill_script_task(task_name: str, config: dict) -> None:
    """執行 Skill Script 模式排程"""
    from .mcp.skill_script_tools import run_skill_script

    skill = config["skill"]
    script = config["script"]
    input_data = config.get("input", "")
    ctos_user_id = config.get("ctos_user_id")

    result = await run_skill_script(
        skill=skill,
        script=script,
        input=input_data,
        ctos_user_id=ctos_user_id,
    )

    # run_skill_script 回傳 JSON 字串
    import json

    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict) and not parsed.get("success", True):
            raise RuntimeError(f"Skill Script 執行失敗: {parsed.get('error', result)}")
    except (json.JSONDecodeError, TypeError):
        pass  # 非 JSON 回傳視為成功


def _execute_dynamic_task_wrapper(task_id: UUID) -> None:
    """APScheduler 回呼包裝器（同步 → 非同步橋接）"""
    import asyncio

    loop = asyncio.get_event_loop()
    loop.create_task(execute_dynamic_task(task_id))


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
