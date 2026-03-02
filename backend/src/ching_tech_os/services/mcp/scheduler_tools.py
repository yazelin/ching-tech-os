"""排程管理 MCP 工具

提供 AI Agent 管理動態排程的能力。
"""

import json
import logging

from .server import ensure_db_connection, mcp, resolve_ctos_user_id

logger = logging.getLogger("mcp_server")


async def _check_admin(ctos_user_id: int | None) -> tuple[int | None, str | None]:
    """檢查管理員權限，回傳 (user_id, error_message)"""
    uid = resolve_ctos_user_id(ctos_user_id)
    if uid is None:
        return None, "需要 ctos_user_id 來驗證權限"

    from ..user import get_user_role_and_permissions

    user_info = await get_user_role_and_permissions(uid)
    if user_info["role"] != "admin":
        return uid, "需要管理員權限才能管理排程"

    return uid, None


@mcp.tool()
async def manage_scheduled_task(
    action: str,
    name: str | None = None,
    description: str | None = None,
    trigger_type: str | None = None,
    trigger_config: str | None = None,
    executor_type: str | None = None,
    executor_config: str | None = None,
    task_id: str | None = None,
    is_enabled: bool | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """管理動態排程任務。

    action 參數：
    - create: 建立新排程（需要 name, trigger_type, trigger_config, executor_type, executor_config）
    - update: 更新排程（需要 task_id，以及要更新的欄位）
    - delete: 刪除排程（需要 task_id）
    - enable: 啟用排程（需要 task_id）
    - disable: 停用排程（需要 task_id）

    trigger_type: "cron" 或 "interval"
    trigger_config: JSON 字串，cron 範例 {"hour": "8", "minute": "0"}，interval 範例 {"hours": 1}
    executor_type: "agent" 或 "skill_script"
    executor_config: JSON 字串，agent 範例 {"agent_name": "bot", "prompt": "執行每日報告"}，
                     skill_script 範例 {"skill": "my-skill", "script": "run.py"}
    """
    await ensure_db_connection()

    uid, err = await _check_admin(ctos_user_id)
    if err:
        return json.dumps({"success": False, "error": err}, ensure_ascii=False)

    from ..task_scheduler import (
        create_scheduled_task,
        delete_scheduled_task,
        get_scheduled_task,
        register_dynamic_job,
        toggle_scheduled_task,
        unregister_dynamic_job,
        update_scheduled_task,
    )
    from uuid import UUID

    try:
        if action == "create":
            if not all([name, trigger_type, trigger_config, executor_type, executor_config]):
                return json.dumps({
                    "success": False,
                    "error": "create 需要 name, trigger_type, trigger_config, executor_type, executor_config",
                }, ensure_ascii=False)

            data = {
                "name": name,
                "description": description,
                "trigger_type": trigger_type,
                "trigger_config": json.loads(trigger_config),
                "executor_type": executor_type,
                "executor_config": json.loads(executor_config),
                "is_enabled": is_enabled if is_enabled is not None else True,
            }
            task = await create_scheduled_task(data, created_by=uid)
            if task["is_enabled"]:
                register_dynamic_job(task)
            return json.dumps({
                "success": True,
                "task": _format_task(task),
            }, ensure_ascii=False)

        elif action == "update":
            if not task_id:
                return json.dumps({"success": False, "error": "update 需要 task_id"}, ensure_ascii=False)

            update_data = {}
            if name is not None:
                update_data["name"] = name
            if description is not None:
                update_data["description"] = description
            if trigger_type is not None:
                update_data["trigger_type"] = trigger_type
            if trigger_config is not None:
                update_data["trigger_config"] = json.loads(trigger_config)
            if executor_type is not None:
                update_data["executor_type"] = executor_type
            if executor_config is not None:
                update_data["executor_config"] = json.loads(executor_config)
            if is_enabled is not None:
                update_data["is_enabled"] = is_enabled

            tid = UUID(task_id)
            task = await update_scheduled_task(tid, update_data)
            if not task:
                return json.dumps({"success": False, "error": "排程不存在"}, ensure_ascii=False)

            unregister_dynamic_job(tid)
            if task["is_enabled"]:
                register_dynamic_job(task)

            return json.dumps({
                "success": True,
                "task": _format_task(task),
            }, ensure_ascii=False)

        elif action == "delete":
            if not task_id:
                return json.dumps({"success": False, "error": "delete 需要 task_id"}, ensure_ascii=False)
            tid = UUID(task_id)
            unregister_dynamic_job(tid)
            deleted = await delete_scheduled_task(tid)
            return json.dumps({
                "success": deleted,
                "message": "排程已刪除" if deleted else "排程不存在",
            }, ensure_ascii=False)

        elif action == "enable":
            if not task_id:
                return json.dumps({"success": False, "error": "enable 需要 task_id"}, ensure_ascii=False)
            tid = UUID(task_id)
            task = await toggle_scheduled_task(tid, True)
            if not task:
                return json.dumps({"success": False, "error": "排程不存在"}, ensure_ascii=False)
            register_dynamic_job(task)
            return json.dumps({"success": True, "task": _format_task(task)}, ensure_ascii=False)

        elif action == "disable":
            if not task_id:
                return json.dumps({"success": False, "error": "disable 需要 task_id"}, ensure_ascii=False)
            tid = UUID(task_id)
            task = await toggle_scheduled_task(tid, False)
            if not task:
                return json.dumps({"success": False, "error": "排程不存在"}, ensure_ascii=False)
            unregister_dynamic_job(tid)
            return json.dumps({"success": True, "task": _format_task(task)}, ensure_ascii=False)

        else:
            return json.dumps({
                "success": False,
                "error": f"不支援的 action: {action}（支援: create, update, delete, enable, disable）",
            }, ensure_ascii=False)

    except Exception as e:
        logger.error("manage_scheduled_task 失敗: %s", e)
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def list_scheduled_tasks(
    is_enabled: bool | None = None,
    include_static: bool = True,
    ctos_user_id: int | None = None,
) -> str:
    """查詢排程列表（含動態排程與靜態排程）。

    is_enabled: 可選，篩選啟用(true)或停用(false)的動態排程，不傳則回傳全部。
    include_static: 是否包含系統/模組靜態排程（預設 true）。
    """
    await ensure_db_connection()

    uid, err = await _check_admin(ctos_user_id)
    if err:
        return json.dumps({"success": False, "error": err}, ensure_ascii=False)

    from ..task_scheduler import list_scheduled_tasks as _list_tasks

    try:
        # 動態排程（來自 DB）
        db_tasks = await _list_tasks(is_enabled=is_enabled)
        result_tasks = [
            {**_format_task(t), "source": "dynamic"} for t in db_tasks
        ]

        # 靜態排程（來自 APScheduler，唯讀）
        if include_static:
            result_tasks.extend(_collect_static_schedules())

        return json.dumps({
            "success": True,
            "count": len(result_tasks),
            "tasks": result_tasks,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error("list_scheduled_tasks 失敗: %s", e)
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


def _collect_static_schedules() -> list[dict]:
    """收集系統/模組靜態排程的唯讀資訊"""
    from ..scheduler import scheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    static_tasks: list[dict] = []
    try:
        for job in scheduler.get_jobs():
            if job.id.startswith("dynamic:"):
                continue

            source = "system" if ":" not in job.id else "module"
            trigger_type, trigger_config = _parse_trigger(job.trigger)

            static_tasks.append({
                "id": job.id,
                "name": job.id,
                "description": job.name or job.id,
                "trigger_type": trigger_type,
                "trigger_config": trigger_config,
                "is_enabled": True,
                "source": source,
                "next_run_at": job.next_run_time.isoformat() if job.next_run_time else None,
            })
    except Exception as e:
        logger.warning("收集靜態排程失敗: %s", e)

    return static_tasks


def _parse_trigger(trigger) -> tuple[str, dict]:
    """從 APScheduler trigger 解析類型和設定"""
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    if isinstance(trigger, CronTrigger):
        fields = {}
        for field in trigger.fields:
            expr = str(field)
            if expr != "*":
                fields[field.name] = expr
        return "cron", fields

    if isinstance(trigger, IntervalTrigger):
        total_seconds = int(trigger.interval.total_seconds())
        config = {}
        if total_seconds >= 3600:
            config["hours"] = total_seconds // 3600
            remaining = total_seconds % 3600
            if remaining >= 60:
                config["minutes"] = remaining // 60
        elif total_seconds >= 60:
            config["minutes"] = total_seconds // 60
        else:
            config["seconds"] = total_seconds
        return "interval", config

    return "cron", {}


def _format_task(task: dict) -> dict:
    """格式化排程資料供 MCP 回傳"""
    return {
        "id": str(task["id"]),
        "name": task["name"],
        "description": task.get("description"),
        "trigger_type": task["trigger_type"],
        "trigger_config": task["trigger_config"],
        "executor_type": task["executor_type"],
        "executor_config": task["executor_config"],
        "is_enabled": task["is_enabled"],
        "last_run_at": task["last_run_at"].isoformat() if task.get("last_run_at") else None,
        "last_run_success": task.get("last_run_success"),
        "last_run_error": task.get("last_run_error"),
    }
