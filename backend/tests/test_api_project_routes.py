"""專案模組 API 路由測試。

httpx AsyncClient + ASGI transport，service 層全部 mock。
重點在權限矩陣與路由順序。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from ching_tech_os.api import project as project_api
from ching_tech_os.models.auth import SessionData

PROJECT_ID = uuid4()


# ── 共用 fixtures ─────────────────────────────────────────────


def _session(role: str = "user", user_id: int = 2) -> SessionData:
    now = datetime.now(timezone.utc)
    return SessionData(
        username="admin" if role == "admin" else "user",
        password="xxx",
        nas_host="localhost",
        user_id=user_id,
        created_at=now,
        expires_at=now,
        role=role,
    )


def _detail(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    base = {
        "id": PROJECT_ID,
        "name": "A 案",
        "customer": "甲客戶",
        "status": "active",
        "owner_id": 1,
        "owner_name": "小明",
        "start_date": None,
        "end_date": None,
        "description": None,
        "created_by": 1,
        "created_at": now,
        "updated_at": now,
        "progress": 50,
        "members": [],
        "milestones": [],
        "tasks": [],
        "bot_groups": [],
        "knowledge_count": 0,
    }
    base.update(overrides)
    return base


def _make_app(role: str = "user", *, app_permission: bool = True) -> FastAPI:
    """建立測試 app；只覆寫 app 權限與 admin 兩個依賴，編輯權限走真的邏輯"""
    app = FastAPI()
    app.include_router(project_api.router)

    from ching_tech_os.api.auth import require_admin

    if app_permission:
        app.dependency_overrides[project_api.require_project_access] = lambda: _session(role)
    else:
        async def _no_app_permission():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="無「專案管理」功能權限"
            )

        app.dependency_overrides[project_api.require_project_access] = _no_app_permission

    if role == "admin":
        app.dependency_overrides[require_admin] = lambda: _session("admin", user_id=1)
    else:
        async def _deny_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="需要管理員權限"
            )

        app.dependency_overrides[require_admin] = _deny_admin
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def project_exists(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        project_api.project_service, "project_exists", AsyncMock(return_value=True)
    )


def _set_member(monkeypatch: pytest.MonkeyPatch, is_member: bool) -> None:
    monkeypatch.setattr(
        project_api, "is_project_member", AsyncMock(return_value=is_member)
    )


# ============================================================
# 權限矩陣
# ============================================================


@pytest.mark.asyncio
async def test_put_project_rejected_for_non_member(
    monkeypatch: pytest.MonkeyPatch, project_exists
) -> None:
    """非 admin 非成員：編輯 403「只有專案成員能編輯」"""
    _set_member(monkeypatch, False)

    async with _client(_make_app("user")) as client:
        resp = await client.put(f"/api/projects/{PROJECT_ID}", json={"name": "改名"})

    assert resp.status_code == 403
    assert resp.json()["detail"] == "只有專案成員能編輯"


@pytest.mark.asyncio
async def test_put_project_allowed_for_member(
    monkeypatch: pytest.MonkeyPatch, project_exists
) -> None:
    """專案成員：編輯放行"""
    _set_member(monkeypatch, True)
    monkeypatch.setattr(
        project_api.project_service,
        "update_project",
        AsyncMock(return_value={"id": PROJECT_ID}),
    )
    monkeypatch.setattr(
        project_api.project_service,
        "get_project_detail",
        AsyncMock(return_value=_detail(name="改名")),
    )

    async with _client(_make_app("user")) as client:
        resp = await client.put(f"/api/projects/{PROJECT_ID}", json={"name": "改名"})

    assert resp.status_code == 200
    assert resp.json()["name"] == "改名"


@pytest.mark.asyncio
async def test_put_project_allowed_for_admin_without_membership(
    monkeypatch: pytest.MonkeyPatch, project_exists
) -> None:
    """admin 不必是成員也能編輯"""
    member_check = AsyncMock(return_value=False)
    monkeypatch.setattr(project_api, "is_project_member", member_check)
    monkeypatch.setattr(
        project_api.project_service,
        "update_project",
        AsyncMock(return_value={"id": PROJECT_ID}),
    )
    monkeypatch.setattr(
        project_api.project_service,
        "get_project_detail",
        AsyncMock(return_value=_detail()),
    )

    async with _client(_make_app("admin")) as client:
        resp = await client.put(f"/api/projects/{PROJECT_ID}", json={"name": "改名"})

    assert resp.status_code == 200
    member_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_editor_dependency_404_when_project_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """專案不存在：編輯類端點 404，不是 403"""
    monkeypatch.setattr(
        project_api.project_service, "project_exists", AsyncMock(return_value=False)
    )
    _set_member(monkeypatch, True)

    async with _client(_make_app("user")) as client:
        resp = await client.put(f"/api/projects/{PROJECT_ID}", json={"name": "x"})

    assert resp.status_code == 404
    assert resp.json()["detail"] == "專案不存在"


@pytest.mark.asyncio
async def test_no_app_permission_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """沒有 project-management app 權限：讀寫都 403"""
    app = _make_app("admin", app_permission=False)

    async with _client(app) as client:
        assert (await client.get("/api/projects")).status_code == 403
        assert (await client.get("/api/projects/summary")).status_code == 403
        assert (await client.get(f"/api/projects/{PROJECT_ID}")).status_code == 403
        resp = await client.put(f"/api/projects/{PROJECT_ID}", json={"name": "x"})
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_and_delete_require_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    """建立與刪除限管理員"""
    async with _client(_make_app("user")) as client:
        create = await client.post("/api/projects", json={"name": "新案"})
        delete = await client.delete(f"/api/projects/{PROJECT_ID}")

    assert create.status_code == 403
    assert create.json()["detail"] == "需要管理員權限"
    assert delete.status_code == 403


@pytest.mark.asyncio
async def test_create_project_as_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    create = AsyncMock(return_value={"id": PROJECT_ID})
    monkeypatch.setattr(project_api.project_service, "create_project", create)
    monkeypatch.setattr(
        project_api.project_service,
        "get_project_detail",
        AsyncMock(return_value=_detail(name="新案")),
    )

    async with _client(_make_app("admin")) as client:
        resp = await client.post(
            "/api/projects", json={"name": "新案", "owner_id": 4, "status": "planning"}
        )

    assert resp.status_code == 201
    assert resp.json()["name"] == "新案"
    # created_by 帶 session 的 user_id
    assert create.await_args.kwargs["created_by"] == 1
    assert create.await_args.args[0]["owner_id"] == 4


@pytest.mark.asyncio
async def test_delete_project_as_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        project_api.project_service, "delete_project", AsyncMock(return_value=True)
    )

    async with _client(_make_app("admin")) as client:
        resp = await client.delete(f"/api/projects/{PROJECT_ID}")

    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_project_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        project_api.project_service, "delete_project", AsyncMock(return_value=False)
    )

    async with _client(_make_app("admin")) as client:
        resp = await client.delete(f"/api/projects/{PROJECT_ID}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_status_rejected() -> None:
    """狀態用 Literal 鎖住，沒定義的值 422"""
    async with _client(_make_app("admin")) as client:
        resp = await client.post("/api/projects", json={"name": "x", "status": "ongoing"})

    assert resp.status_code == 422


# ============================================================
# 讀取
# ============================================================


@pytest.mark.asyncio
async def test_list_projects(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    listing = AsyncMock(
        return_value={
            "items": [
                {
                    "id": PROJECT_ID,
                    "name": "A 案",
                    "customer": "甲客戶",
                    "status": "active",
                    "owner_id": 1,
                    "owner_name": "小明",
                    "start_date": None,
                    "end_date": None,
                    "created_at": now,
                    "updated_at": now,
                    "progress": 25,
                    "member_count": 2,
                    "overdue_milestones": 1,
                }
            ],
            "total": 1,
        }
    )
    monkeypatch.setattr(project_api.project_service, "list_projects", listing)

    async with _client(_make_app("user")) as client:
        resp = await client.get("/api/projects?status=active&q=甲&page=2&page_size=50")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["progress"] == 25
    assert listing.await_args.kwargs == {
        "status": "active",
        "q": "甲",
        "page": 2,
        "page_size": 50,
    }


@pytest.mark.asyncio
async def test_list_projects_page_size_cap() -> None:
    """page_size 上限 100"""
    async with _client(_make_app("user")) as client:
        resp = await client.get("/api/projects?page_size=101")

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_summary_route_not_swallowed_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """/summary 必須先比對，不能被 /{project_id} 吃掉"""
    summary = AsyncMock(
        return_value={
            "active_count": 2,
            "overdue_milestones": [
                {
                    "project_id": PROJECT_ID,
                    "project_name": "A 案",
                    "milestone_id": uuid4(),
                    "name": "交機",
                    "due_date": date(2026, 9, 1),
                    "days_overdue": 10,
                }
            ],
        }
    )
    detail = AsyncMock(return_value=_detail())
    monkeypatch.setattr(project_api.project_service, "get_summary", summary)
    monkeypatch.setattr(project_api.project_service, "get_project_detail", detail)

    async with _client(_make_app("user")) as client:
        resp = await client.get("/api/projects/summary")

    assert resp.status_code == 200
    assert resp.json()["active_count"] == 2
    summary.assert_awaited_once()
    # 沒有落到 /{project_id}（否則 summary 會被當成 UUID 解析失敗 422）
    detail.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_project_detail_and_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        project_api.project_service,
        "get_project_detail",
        AsyncMock(return_value=_detail(knowledge_count=3)),
    )

    async with _client(_make_app("user")) as client:
        resp = await client.get(f"/api/projects/{PROJECT_ID}")
    assert resp.status_code == 200
    assert resp.json()["knowledge_count"] == 3

    monkeypatch.setattr(
        project_api.project_service,
        "get_project_detail",
        AsyncMock(return_value=None),
    )
    async with _client(_make_app("user")) as client:
        resp = await client.get(f"/api/projects/{PROJECT_ID}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_project_not_found(
    monkeypatch: pytest.MonkeyPatch, project_exists
) -> None:
    _set_member(monkeypatch, True)
    monkeypatch.setattr(
        project_api.project_service, "update_project", AsyncMock(return_value=None)
    )

    async with _client(_make_app("user")) as client:
        resp = await client.put(f"/api/projects/{PROJECT_ID}", json={"name": "x"})

    assert resp.status_code == 404


# ============================================================
# 成員
# ============================================================


@pytest.mark.asyncio
async def test_add_member(monkeypatch: pytest.MonkeyPatch, project_exists) -> None:
    _set_member(monkeypatch, True)
    monkeypatch.setattr(
        project_api.project_service,
        "add_member",
        AsyncMock(
            return_value={
                "user_id": 7,
                "username": "abc",
                "display_name": "阿貓",
                "role": "member",
            }
        ),
    )

    async with _client(_make_app("user")) as client:
        resp = await client.post(f"/api/projects/{PROJECT_ID}/members", json={"user_id": 7})

    assert resp.status_code == 201
    assert resp.json()["display_name"] == "阿貓"


@pytest.mark.asyncio
async def test_add_member_unknown_user(
    monkeypatch: pytest.MonkeyPatch, project_exists
) -> None:
    _set_member(monkeypatch, True)
    monkeypatch.setattr(
        project_api.project_service, "add_member", AsyncMock(return_value=None)
    )

    async with _client(_make_app("user")) as client:
        resp = await client.post(f"/api/projects/{PROJECT_ID}/members", json={"user_id": 7})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remove_owner_is_400(monkeypatch: pytest.MonkeyPatch, project_exists) -> None:
    """負責人不能移除"""
    _set_member(monkeypatch, True)
    monkeypatch.setattr(
        project_api.project_service, "remove_member", AsyncMock(return_value="owner")
    )

    async with _client(_make_app("user")) as client:
        resp = await client.delete(f"/api/projects/{PROJECT_ID}/members/1")

    assert resp.status_code == 400
    assert resp.json()["detail"] == "負責人不能移除"


@pytest.mark.asyncio
async def test_remove_member_ok_and_missing(
    monkeypatch: pytest.MonkeyPatch, project_exists
) -> None:
    _set_member(monkeypatch, True)
    monkeypatch.setattr(
        project_api.project_service, "remove_member", AsyncMock(return_value="removed")
    )

    async with _client(_make_app("user")) as client:
        resp = await client.delete(f"/api/projects/{PROJECT_ID}/members/2")
    assert resp.status_code == 200

    monkeypatch.setattr(
        project_api.project_service, "remove_member", AsyncMock(return_value="not_found")
    )
    async with _client(_make_app("user")) as client:
        resp = await client.delete(f"/api/projects/{PROJECT_ID}/members/2")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_member_endpoints_reject_non_member(
    monkeypatch: pytest.MonkeyPatch, project_exists
) -> None:
    _set_member(monkeypatch, False)

    async with _client(_make_app("user")) as client:
        add = await client.post(f"/api/projects/{PROJECT_ID}/members", json={"user_id": 7})
        remove = await client.delete(f"/api/projects/{PROJECT_ID}/members/7")

    assert add.status_code == 403
    assert remove.status_code == 403


# ============================================================
# 里程碑與任務
# ============================================================


def _milestone_payload() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": uuid4(),
        "project_id": PROJECT_ID,
        "name": "交機",
        "due_date": date(2026, 9, 1),
        "completed_at": None,
        "status": "pending",
        "sort_order": 0,
        "created_at": now,
        "updated_at": now,
        "is_overdue": True,
    }


def _task_payload(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    base = {
        "id": uuid4(),
        "project_id": PROJECT_ID,
        "milestone_id": None,
        "title": "拉線",
        "description": None,
        "assignee_id": None,
        "assignee_name": None,
        "status": "todo",
        "due_date": None,
        "sort_order": 0,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_milestone_crud(monkeypatch: pytest.MonkeyPatch, project_exists) -> None:
    _set_member(monkeypatch, True)
    mid = uuid4()
    monkeypatch.setattr(
        project_api.project_service,
        "create_milestone",
        AsyncMock(return_value=_milestone_payload()),
    )
    monkeypatch.setattr(
        project_api.project_service,
        "update_milestone",
        AsyncMock(return_value=_milestone_payload()),
    )
    monkeypatch.setattr(
        project_api.project_service, "delete_milestone", AsyncMock(return_value=True)
    )

    async with _client(_make_app("user")) as client:
        created = await client.post(
            f"/api/projects/{PROJECT_ID}/milestones",
            json={"name": "交機", "due_date": "2026-09-01"},
        )
        updated = await client.put(
            f"/api/projects/{PROJECT_ID}/milestones/{mid}", json={"status": "completed"}
        )
        deleted = await client.delete(f"/api/projects/{PROJECT_ID}/milestones/{mid}")

    assert created.status_code == 201
    assert created.json()["is_overdue"] is True
    assert updated.status_code == 200
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_milestone_not_found(monkeypatch: pytest.MonkeyPatch, project_exists) -> None:
    _set_member(monkeypatch, True)
    mid = uuid4()
    monkeypatch.setattr(
        project_api.project_service, "update_milestone", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        project_api.project_service, "delete_milestone", AsyncMock(return_value=False)
    )

    async with _client(_make_app("user")) as client:
        updated = await client.put(
            f"/api/projects/{PROJECT_ID}/milestones/{mid}", json={"status": "completed"}
        )
        deleted = await client.delete(f"/api/projects/{PROJECT_ID}/milestones/{mid}")

    assert updated.status_code == 404
    assert deleted.status_code == 404


@pytest.mark.asyncio
async def test_task_crud(monkeypatch: pytest.MonkeyPatch, project_exists) -> None:
    _set_member(monkeypatch, True)
    tid = uuid4()
    monkeypatch.setattr(
        project_api.project_service, "create_task", AsyncMock(return_value=_task_payload())
    )
    monkeypatch.setattr(
        project_api.project_service,
        "update_task",
        AsyncMock(return_value=_task_payload(status="done")),
    )
    monkeypatch.setattr(
        project_api.project_service, "delete_task", AsyncMock(return_value=True)
    )

    async with _client(_make_app("user")) as client:
        created = await client.post(
            f"/api/projects/{PROJECT_ID}/tasks", json={"title": "拉線"}
        )
        updated = await client.put(
            f"/api/projects/{PROJECT_ID}/tasks/{tid}", json={"status": "done"}
        )
        deleted = await client.delete(f"/api/projects/{PROJECT_ID}/tasks/{tid}")

    assert created.status_code == 201
    assert updated.json()["status"] == "done"
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_task_not_found(monkeypatch: pytest.MonkeyPatch, project_exists) -> None:
    _set_member(monkeypatch, True)
    tid = uuid4()
    monkeypatch.setattr(
        project_api.project_service, "update_task", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        project_api.project_service, "delete_task", AsyncMock(return_value=False)
    )

    async with _client(_make_app("user")) as client:
        updated = await client.put(
            f"/api/projects/{PROJECT_ID}/tasks/{tid}", json={"status": "done"}
        )
        deleted = await client.delete(f"/api/projects/{PROJECT_ID}/tasks/{tid}")

    assert updated.status_code == 404
    assert deleted.status_code == 404


@pytest.mark.asyncio
async def test_milestone_and_task_endpoints_reject_non_member(
    monkeypatch: pytest.MonkeyPatch, project_exists
) -> None:
    _set_member(monkeypatch, False)
    mid = uuid4()

    async with _client(_make_app("user")) as client:
        ms = await client.post(
            f"/api/projects/{PROJECT_ID}/milestones",
            json={"name": "交機", "due_date": "2026-09-01"},
        )
        task = await client.post(f"/api/projects/{PROJECT_ID}/tasks", json={"title": "拉線"})
        ms_del = await client.delete(f"/api/projects/{PROJECT_ID}/milestones/{mid}")

    assert ms.status_code == 403
    assert task.status_code == 403
    assert ms_del.status_code == 403
