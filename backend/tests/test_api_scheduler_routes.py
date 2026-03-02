"""排程管理 API 路由測試。

使用 httpx AsyncClient + ASGI transport 測試所有 API 端點。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ching_tech_os.api import scheduler as scheduler_api
from ching_tech_os.models.scheduled_task import ScheduledTaskResponse


# ── 共用 fixtures ─────────────────────────────────────────────

TASK_ID = uuid4()


def _make_task(name: str = "test-task", **overrides) -> dict:
    now = datetime.now(timezone.utc)
    base = {
        "id": TASK_ID,
        "name": name,
        "description": "desc",
        "trigger_type": "cron",
        "trigger_config": {"hour": "8", "minute": "0"},
        "executor_type": "agent",
        "executor_config": {"agent_name": "bot", "prompt": "hello"},
        "is_enabled": True,
        "created_by": 1,
        "last_run_at": None,
        "next_run_at": None,
        "last_run_success": None,
        "last_run_error": None,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return base


def _mock_admin_session():
    """回傳 mock 管理員 session"""
    from ching_tech_os.models.auth import SessionData

    return SessionData(
        username="admin",
        password="xxx",
        nas_host="localhost",
        user_id=1,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
        role="admin",
    )


def _mock_user_session():
    """回傳 mock 一般使用者 session"""
    from ching_tech_os.models.auth import SessionData

    return SessionData(
        username="user",
        password="xxx",
        nas_host="localhost",
        user_id=2,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
        role="user",
    )


@pytest.fixture
def app_admin():
    """建立使用管理員 session 的測試 app"""
    app = FastAPI()
    app.include_router(scheduler_api.router)

    # 覆寫 auth dependency
    from ching_tech_os.api.auth import require_admin
    app.dependency_overrides[require_admin] = lambda: _mock_admin_session()
    return app


@pytest.fixture
def app_user():
    """建立使用一般使用者 session 的測試 app（會被 403）"""
    app = FastAPI()
    app.include_router(scheduler_api.router)

    from ching_tech_os.api.auth import require_admin
    from fastapi import HTTPException, status

    async def _deny():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理員權限")

    app.dependency_overrides[require_admin] = _deny
    return app


# ============================================================
# GET /api/scheduler/tasks
# ============================================================


@pytest.mark.asyncio
async def test_list_tasks(app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """測試列出排程"""
    task = _make_task()
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.list_scheduled_tasks",
        AsyncMock(return_value=[task]),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.get_dynamic_job_next_run",
        MagicMock(return_value=None),
    )
    # Mock 靜態排程收集
    monkeypatch.setattr(scheduler_api, "_collect_static_schedules", lambda: [])

    async with AsyncClient(transport=ASGITransport(app=app_admin), base_url="http://test") as client:
        resp = await client.get("/api/scheduler/tasks")

    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["source"] == "dynamic"


# ============================================================
# POST /api/scheduler/tasks
# ============================================================


@pytest.mark.asyncio
async def test_create_task(app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """測試建立排程"""
    task = _make_task("new-task")
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.list_scheduled_tasks",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.create_scheduled_task",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.register_dynamic_job",
        MagicMock(),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.get_dynamic_job_next_run",
        MagicMock(return_value=None),
    )

    body = {
        "name": "new-task",
        "trigger_type": "cron",
        "trigger_config": {"hour": "8"},
        "executor_type": "agent",
        "executor_config": {"agent_name": "bot", "prompt": "hi"},
    }

    async with AsyncClient(transport=ASGITransport(app=app_admin), base_url="http://test") as client:
        resp = await client.post("/api/scheduler/tasks", json=body)

    assert resp.status_code == 201
    assert resp.json()["name"] == "new-task"


@pytest.mark.asyncio
async def test_create_task_duplicate_name(app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """測試建立排程 — 名稱重複"""
    existing = _make_task("dup-task")
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.list_scheduled_tasks",
        AsyncMock(return_value=[existing]),
    )

    body = {
        "name": "dup-task",
        "trigger_type": "cron",
        "trigger_config": {"hour": "8"},
        "executor_type": "agent",
        "executor_config": {"agent_name": "bot", "prompt": "hi"},
    }

    async with AsyncClient(transport=ASGITransport(app=app_admin), base_url="http://test") as client:
        resp = await client.post("/api/scheduler/tasks", json=body)

    assert resp.status_code == 409


# ============================================================
# GET /api/scheduler/tasks/{task_id}
# ============================================================


@pytest.mark.asyncio
async def test_get_task(app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """測試取得單一排程"""
    task = _make_task()
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.get_scheduled_task",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.get_dynamic_job_next_run",
        MagicMock(return_value=None),
    )

    async with AsyncClient(transport=ASGITransport(app=app_admin), base_url="http://test") as client:
        resp = await client.get(f"/api/scheduler/tasks/{TASK_ID}")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_task_not_found(app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """測試取得不存在的排程"""
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.get_scheduled_task",
        AsyncMock(return_value=None),
    )

    async with AsyncClient(transport=ASGITransport(app=app_admin), base_url="http://test") as client:
        resp = await client.get(f"/api/scheduler/tasks/{uuid4()}")

    assert resp.status_code == 404


# ============================================================
# DELETE /api/scheduler/tasks/{task_id}
# ============================================================


@pytest.mark.asyncio
async def test_delete_task(app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """測試刪除排程"""
    task = _make_task()
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.get_scheduled_task",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.unregister_dynamic_job",
        MagicMock(),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.delete_scheduled_task",
        AsyncMock(return_value=True),
    )

    async with AsyncClient(transport=ASGITransport(app=app_admin), base_url="http://test") as client:
        resp = await client.delete(f"/api/scheduler/tasks/{TASK_ID}")

    assert resp.status_code == 204


# ============================================================
# PATCH /api/scheduler/tasks/{task_id}/toggle
# ============================================================


@pytest.mark.asyncio
async def test_toggle_task(app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """測試切換啟停用"""
    task = _make_task(is_enabled=False)
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.get_scheduled_task",
        AsyncMock(return_value=task),
    )
    updated_task = {**task, "is_enabled": True}
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.toggle_scheduled_task",
        AsyncMock(return_value=updated_task),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.register_dynamic_job",
        MagicMock(),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.get_dynamic_job_next_run",
        MagicMock(return_value=None),
    )

    async with AsyncClient(transport=ASGITransport(app=app_admin), base_url="http://test") as client:
        resp = await client.patch(
            f"/api/scheduler/tasks/{TASK_ID}/toggle",
            json={"is_enabled": True},
        )

    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is True


# ============================================================
# POST /api/scheduler/tasks/{task_id}/run
# ============================================================


@pytest.mark.asyncio
async def test_run_task(app_admin: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """測試手動觸發"""
    task = _make_task()
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.get_scheduled_task",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.task_scheduler.execute_dynamic_task",
        AsyncMock(),
    )

    async with AsyncClient(transport=ASGITransport(app=app_admin), base_url="http://test") as client:
        resp = await client.post(f"/api/scheduler/tasks/{TASK_ID}/run")

    assert resp.status_code == 202


# ============================================================
# 權限檢查
# ============================================================


@pytest.mark.asyncio
async def test_non_admin_gets_403(app_user: FastAPI) -> None:
    """非管理員應回傳 403"""
    async with AsyncClient(transport=ASGITransport(app=app_user), base_url="http://test") as client:
        resp = await client.get("/api/scheduler/tasks")

    assert resp.status_code == 403


# ============================================================
# Pydantic 模型驗證
# ============================================================


def test_model_validation_missing_fields() -> None:
    """缺少必填欄位應觸發 ValidationError"""
    from pydantic import ValidationError
    from ching_tech_os.models.scheduled_task import ScheduledTaskCreate

    with pytest.raises(ValidationError):
        ScheduledTaskCreate(name="")  # 缺少 trigger_type 等


def test_model_validation_invalid_trigger_type() -> None:
    """不合法的 trigger_type 應觸發 ValidationError"""
    from pydantic import ValidationError
    from ching_tech_os.models.scheduled_task import ScheduledTaskCreate

    with pytest.raises(ValidationError):
        ScheduledTaskCreate(
            name="test",
            trigger_type="invalid",
            trigger_config={},
            executor_type="agent",
            executor_config={},
        )


def test_model_validation_invalid_executor_type() -> None:
    """不合法的 executor_type 應觸發 ValidationError"""
    from pydantic import ValidationError
    from ching_tech_os.models.scheduled_task import ScheduledTaskCreate

    with pytest.raises(ValidationError):
        ScheduledTaskCreate(
            name="test",
            trigger_type="cron",
            trigger_config={},
            executor_type="invalid",
            executor_config={},
        )


def test_model_valid_cron_create() -> None:
    """合法的 cron 排程建立"""
    from ching_tech_os.models.scheduled_task import ScheduledTaskCreate

    task = ScheduledTaskCreate(
        name="daily-report",
        trigger_type="cron",
        trigger_config={"hour": "8", "minute": "0"},
        executor_type="agent",
        executor_config={"agent_name": "bot", "prompt": "報告"},
    )
    assert task.name == "daily-report"
    assert task.trigger_type == "cron"


def test_model_valid_interval_create() -> None:
    """合法的 interval 排程建立"""
    from ching_tech_os.models.scheduled_task import ScheduledTaskCreate

    task = ScheduledTaskCreate(
        name="health-check",
        trigger_type="interval",
        trigger_config={"hours": 1},
        executor_type="skill_script",
        executor_config={"skill": "debug", "script": "check.py"},
    )
    assert task.executor_type == "skill_script"
