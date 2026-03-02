"""排程管理 API

提供動態排程的 CRUD 操作，所有端點需要管理員權限。
"""

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid5, NAMESPACE_DNS

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, Depends, HTTPException, status

from ..models.scheduled_task import (
    ScheduledTask,
    ScheduledTaskCreate,
    ScheduledTaskListResponse,
    ScheduledTaskResponse,
    ScheduledTaskToggle,
    ScheduledTaskUpdate,
)
from ..models.auth import SessionData
from .auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


def _to_response(task: dict, source: str = "dynamic") -> ScheduledTaskResponse:
    """將 DB task dict 轉為 API response，自動填入 next_run_at"""
    from ..services.task_scheduler import get_dynamic_job_next_run

    next_run = get_dynamic_job_next_run(task["id"]) if source == "dynamic" else None
    data = {**task, "source": source}
    if next_run:
        data["next_run_at"] = next_run
    return ScheduledTaskResponse(**data)


# ── 列出所有排程 ─────────────────────────────────────────────


@router.get("/tasks", response_model=ScheduledTaskListResponse)
async def list_tasks(
    session: SessionData = Depends(require_admin),
) -> ScheduledTaskListResponse:
    """列出所有排程（動態 + 靜態）"""
    from ..services.task_scheduler import list_scheduled_tasks

    # 動態排程
    db_tasks = await list_scheduled_tasks()
    tasks: list[ScheduledTaskResponse] = [_to_response(t) for t in db_tasks]

    # 靜態排程（唯讀資訊）
    tasks.extend(_collect_static_schedules())

    return ScheduledTaskListResponse(tasks=tasks)


# ── 建立排程 ─────────────────────────────────────────────────


@router.post(
    "/tasks",
    response_model=ScheduledTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    body: ScheduledTaskCreate,
    session: SessionData = Depends(require_admin),
) -> ScheduledTaskResponse:
    """建立動態排程"""
    from ..services.task_scheduler import (
        create_scheduled_task,
        list_scheduled_tasks,
        register_dynamic_job,
    )

    # 檢查名稱重複
    existing = await list_scheduled_tasks()
    if any(t["name"] == body.name for t in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"排程名稱已存在: {body.name}",
        )

    task = await create_scheduled_task(
        data=body.model_dump(),
        created_by=session.user_id,
    )

    # 若啟用，同步註冊到 APScheduler
    if task["is_enabled"]:
        register_dynamic_job(task)

    return _to_response(task)


# ── 取得單一排程 ─────────────────────────────────────────────


@router.get("/tasks/{task_id}", response_model=ScheduledTaskResponse)
async def get_task(
    task_id: UUID,
    session: SessionData = Depends(require_admin),
) -> ScheduledTaskResponse:
    """取得單一排程"""
    from ..services.task_scheduler import get_scheduled_task

    task = await get_scheduled_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="排程不存在")

    return _to_response(task)


# ── 更新排程 ─────────────────────────────────────────────────


@router.put("/tasks/{task_id}", response_model=ScheduledTaskResponse)
async def update_task(
    task_id: UUID,
    body: ScheduledTaskUpdate,
    session: SessionData = Depends(require_admin),
) -> ScheduledTaskResponse:
    """更新排程"""
    from ..services.task_scheduler import (
        get_scheduled_task,
        list_scheduled_tasks,
        register_dynamic_job,
        unregister_dynamic_job,
        update_scheduled_task,
    )

    existing = await get_scheduled_task(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="排程不存在")

    # 檢查名稱重複（如果有改名稱）
    if body.name and body.name != existing["name"]:
        all_tasks = await list_scheduled_tasks()
        if any(t["name"] == body.name and t["id"] != task_id for t in all_tasks):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"排程名稱已存在: {body.name}",
            )

    update_data = body.model_dump(exclude_none=True)
    task = await update_scheduled_task(task_id, update_data)
    if not task:
        raise HTTPException(status_code=404, detail="排程不存在")

    # 重新註冊 APScheduler job（remove + add）
    unregister_dynamic_job(task_id)
    if task["is_enabled"]:
        register_dynamic_job(task)

    return _to_response(task)


# ── 刪除排程 ─────────────────────────────────────────────────


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    session: SessionData = Depends(require_admin),
) -> None:
    """刪除排程"""
    from ..services.task_scheduler import (
        delete_scheduled_task,
        get_scheduled_task,
        unregister_dynamic_job,
    )

    existing = await get_scheduled_task(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="排程不存在")

    unregister_dynamic_job(task_id)
    await delete_scheduled_task(task_id)


# ── 啟停用切換 ───────────────────────────────────────────────


@router.patch("/tasks/{task_id}/toggle", response_model=ScheduledTaskResponse)
async def toggle_task(
    task_id: UUID,
    body: ScheduledTaskToggle,
    session: SessionData = Depends(require_admin),
) -> ScheduledTaskResponse:
    """切換排程啟停用"""
    from ..services.task_scheduler import (
        get_scheduled_task,
        register_dynamic_job,
        toggle_scheduled_task,
        unregister_dynamic_job,
    )

    existing = await get_scheduled_task(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="排程不存在")

    task = await toggle_scheduled_task(task_id, body.is_enabled)
    if not task:
        raise HTTPException(status_code=404, detail="排程不存在")

    if body.is_enabled:
        register_dynamic_job(task)
    else:
        unregister_dynamic_job(task_id)

    return _to_response(task)


# ── 手動觸發 ─────────────────────────────────────────────────


@router.post(
    "/tasks/{task_id}/run",
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_task(
    task_id: UUID,
    session: SessionData = Depends(require_admin),
) -> dict:
    """手動觸發排程立即執行一次"""
    import asyncio

    from ..services.task_scheduler import execute_dynamic_task, get_scheduled_task

    task = await get_scheduled_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="排程不存在")

    # 背景執行，不等待完成
    asyncio.create_task(execute_dynamic_task(task_id))
    return {"message": f"已送出執行: {task['name']}"}


# ── 靜態排程收集 ─────────────────────────────────────────────


def _collect_static_schedules() -> list[ScheduledTaskResponse]:
    """收集核心硬編碼排程和模組排程的唯讀資訊"""
    from ..services.scheduler import scheduler

    static_tasks: list[ScheduledTaskResponse] = []

    # 從 APScheduler 取得所有 job，過濾出非動態的
    for job in scheduler.get_jobs():
        if job.id.startswith("dynamic:"):
            continue

        # 判斷 source
        source = "system" if ":" not in job.id else "module"

        # 解析 trigger 資訊
        trigger_type, trigger_config = _parse_trigger(job.trigger)

        # 用確定性 UUID（基於 job.id）避免每次呼叫產生不同 ID
        fake_id = uuid5(NAMESPACE_DNS, f"static-schedule:{job.id}")

        static_tasks.append(
            ScheduledTaskResponse(
                id=fake_id,
                name=job.id,
                description=job.name or job.id,
                trigger_type=trigger_type,
                trigger_config=trigger_config,
                executor_type="agent",  # 佔位，靜態排程不用此欄位
                executor_config={},
                is_enabled=True,
                source=source,
                next_run_at=job.next_run_time,
                created_at=job.next_run_time or datetime.now(timezone.utc),
                updated_at=job.next_run_time or datetime.now(timezone.utc),
            )
        )

    return static_tasks


def _parse_trigger(trigger) -> tuple[str, dict]:
    """從 APScheduler trigger 解析類型和設定"""
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
