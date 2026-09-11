"""專案模組 MCP 工具測試（PR 7b）

重點與 `test_mcp_erp_tools.py` 同一套：
- 權限被拒時回錯誤 dict，不進 service
- 解析不到唯一目標時回 `{"need_confirmation": true, "candidates": [...]}`，不丟例外
- 寫入類工具要過專案成員檢查（admin 或成員，否則「只有專案成員能編輯」）
- 建立專案不開放給 bot（模組沒有這支工具）
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.services import project as project_service
from ching_tech_os.services.mcp import project_tools

NOW = datetime.now(timezone.utc)
PROJECT_ID = uuid4()
OTHER_PROJECT_ID = uuid4()
MILESTONE_ID = uuid4()
TASK_ID = uuid4()

USERS = [
    {"id": 7, "username": "yaze", "display_name": "亞澤"},
    {"id": 8, "username": "amin", "display_name": "阿明"},
    {"id": 9, "username": "aming", "display_name": "阿明華"},
]

DETAIL = {
    "id": PROJECT_ID,
    "name": "亦達自動化",
    "customer": "亦達",
    "status": "active",
    "progress": 50,
    "member_count": 2,
    "overdue_milestones": 1,
    "created_at": NOW,
    "members": [
        {"user_id": 7, "username": "yaze", "display_name": "亞澤", "role": "owner"}
    ],
    "milestones": [
        {
            "id": MILESTONE_ID,
            "project_id": PROJECT_ID,
            "name": "出機",
            "due_date": date(2026, 9, 1),
            "status": "pending",
            "is_overdue": True,
        }
    ],
    "tasks": [
        {
            "id": TASK_ID,
            "project_id": PROJECT_ID,
            "milestone_id": MILESTONE_ID,
            "title": "配電盤配線",
            "status": "todo",
            "assignee_id": 7,
            "assignee_name": "亞澤",
            "due_date": None,
        },
        {
            "id": uuid4(),
            "project_id": PROJECT_ID,
            "milestone_id": None,
            "title": "現場試車",
            "status": "done",
            "assignee_id": 8,
            "assignee_name": "阿明",
            "due_date": None,
        },
    ],
    "bot_groups": [],
    "knowledge_count": 3,
}


@pytest.fixture(autouse=True)
def _allow(monkeypatch: pytest.MonkeyPatch):
    """預設放行工具權限、當成 admin，並跳過真的連線"""
    monkeypatch.setattr(project_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        project_tools,
        "check_mcp_tool_permission",
        AsyncMock(return_value=(True, "")),
    )
    monkeypatch.setattr(
        project_tools,
        "get_user_role_and_permissions",
        AsyncMock(return_value={"role": "admin", "permissions": None}),
    )
    monkeypatch.setattr(project_tools, "is_project_member", AsyncMock(return_value=False))
    monkeypatch.setattr(project_service, "project_exists", AsyncMock(return_value=True))
    monkeypatch.setattr(project_tools, "get_all_users", AsyncMock(return_value=USERS))


def _deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        project_tools,
        "check_mcp_tool_permission",
        AsyncMock(return_value=(False, "您沒有「專案管理」功能權限，無法使用此工具")),
    )


def _as_member(monkeypatch: pytest.MonkeyPatch, member: bool) -> None:
    """非管理員；member 決定是不是該專案成員"""
    monkeypatch.setattr(
        project_tools,
        "get_user_role_and_permissions",
        AsyncMock(return_value={"role": "user", "permissions": None}),
    )
    monkeypatch.setattr(
        project_tools, "is_project_member", AsyncMock(return_value=member)
    )


def _detail(monkeypatch: pytest.MonkeyPatch, detail=DETAIL) -> AsyncMock:
    mock = AsyncMock(return_value=detail)
    monkeypatch.setattr(project_service, "get_project_detail", mock)
    return mock


# ============================================================
# 共用輔助
# ============================================================


def test_clean_serializes_uuid_and_dates() -> None:
    value = project_tools._clean(
        {"id": PROJECT_ID, "due": date(2026, 9, 1), "at": NOW, "rows": [{"x": TASK_ID}]}
    )
    assert value["id"] == str(PROJECT_ID)
    assert value["due"] == "2026-09-01"
    assert value["at"] == NOW.isoformat()
    assert value["rows"][0]["x"] == str(TASK_ID)


def test_fail_maps_ambiguous_to_need_confirmation() -> None:
    err = project_tools.AmbiguousError(
        "專案", "亦達", [{"id": PROJECT_ID, "name": "亦達自動化"}]
    )
    result = project_tools._fail(err)
    assert result["ok"] is False
    assert result["need_confirmation"] is True
    assert result["entity"] == "專案"
    assert result["query"] == "亦達"
    assert result["candidates"][0]["id"] == str(PROJECT_ID)


def test_fail_maps_not_found_and_service_errors() -> None:
    assert project_tools._fail(project_tools.NotFoundError("專案", "x"))["not_found"] is True
    user_err = project_tools._fail(project_service.UserNotFoundError("99"))
    assert user_err["not_found"] is True and "使用者" in user_err["error"]
    milestone_err = project_tools._fail(
        project_service.MilestoneNotInProjectError(str(MILESTONE_ID))
    )
    assert milestone_err["error"] == "里程碑不屬於此專案"
    assert "執行失敗" in project_tools._fail(RuntimeError("boom"))["error"]


def test_validated_fields_rejects_bad_status() -> None:
    from ching_tech_os.models.project import TaskUpdate

    with pytest.raises(project_tools.InvalidFieldError) as exc:
        project_tools._validated_fields(TaskUpdate, {"status": "finished"})
    assert "欄位不合法" in str(exc.value)


def test_validated_fields_rejects_null_on_not_null_column() -> None:
    from ching_tech_os.models.project import TaskUpdate

    with pytest.raises(project_tools.InvalidFieldError):
        project_tools._validated_fields(TaskUpdate, {"title": None})


def test_validated_fields_keeps_only_given_fields() -> None:
    from ching_tech_os.models.project import TaskUpdate

    payload = project_tools._validated_fields(TaskUpdate, {"due_date": "2026-10-01"})
    assert payload == {"due_date": date(2026, 10, 1)}


# ============================================================
# 解析
# ============================================================


@pytest.mark.asyncio
async def test_resolve_project_accepts_uuid(monkeypatch) -> None:
    assert await project_tools._resolve_project(str(PROJECT_ID)) == PROJECT_ID


@pytest.mark.asyncio
async def test_resolve_project_uuid_not_in_db_is_not_found(monkeypatch) -> None:
    monkeypatch.setattr(project_service, "project_exists", AsyncMock(return_value=False))
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._resolve_project(str(PROJECT_ID))


@pytest.mark.asyncio
async def test_resolve_project_by_name_uses_list_projects(monkeypatch) -> None:
    listed = AsyncMock(
        return_value={"items": [{"id": PROJECT_ID, "name": "亦達自動化"}], "total": 1}
    )
    monkeypatch.setattr(project_service, "list_projects", listed)
    assert await project_tools._resolve_project("亦達") == PROJECT_ID
    assert listed.await_args.kwargs["q"] == "亦達"


@pytest.mark.asyncio
async def test_resolve_project_prefers_exact_name(monkeypatch) -> None:
    monkeypatch.setattr(
        project_service,
        "list_projects",
        AsyncMock(
            return_value={
                "items": [
                    {"id": OTHER_PROJECT_ID, "name": "亦達自動化二期"},
                    {"id": PROJECT_ID, "name": "亦達自動化"},
                ],
                "total": 2,
            }
        ),
    )
    assert await project_tools._resolve_project("亦達自動化") == PROJECT_ID


@pytest.mark.asyncio
async def test_resolve_project_ambiguous(monkeypatch) -> None:
    monkeypatch.setattr(
        project_service,
        "list_projects",
        AsyncMock(
            return_value={
                "items": [
                    {"id": PROJECT_ID, "name": "亦達自動化", "status": "active"},
                    {"id": OTHER_PROJECT_ID, "name": "亦達二期", "status": "active"},
                ],
                "total": 2,
            }
        ),
    )
    with pytest.raises(project_tools.AmbiguousError) as exc:
        await project_tools._resolve_project("亦達")
    assert len(exc.value.candidates) == 2


@pytest.mark.asyncio
async def test_resolve_project_requires_input() -> None:
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._resolve_project("")


@pytest.mark.asyncio
async def test_resolve_user_matches_username_and_display_name() -> None:
    assert await project_tools._resolve_user("yaze") == 7
    assert await project_tools._resolve_user("亞澤") == 7


@pytest.mark.asyncio
async def test_resolve_user_ambiguous_substring() -> None:
    with pytest.raises(project_tools.AmbiguousError) as exc:
        await project_tools._resolve_user("阿")
    assert {c["user_id"] for c in exc.value.candidates} == {8, 9}


@pytest.mark.asyncio
async def test_resolve_user_exact_name_beats_substring() -> None:
    """「阿明」完全同名的那個贏，不因為「阿明華」也含這兩個字就變成候選"""
    assert await project_tools._resolve_user("阿明") == 8


@pytest.mark.asyncio
async def test_resolve_user_not_found() -> None:
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._resolve_user("查無此人")


@pytest.mark.asyncio
async def test_resolve_task_and_milestone(monkeypatch) -> None:
    _detail(monkeypatch)
    assert await project_tools._resolve_task(PROJECT_ID, "配線") == TASK_ID
    assert await project_tools._resolve_task(PROJECT_ID, str(TASK_ID)) == TASK_ID
    assert await project_tools._resolve_milestone(PROJECT_ID, "出機") == MILESTONE_ID
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._resolve_task(PROJECT_ID, "不存在的任務")


@pytest.mark.asyncio
async def test_resolve_task_ambiguous(monkeypatch) -> None:
    detail = dict(DETAIL)
    detail["tasks"] = [
        {"id": TASK_ID, "title": "配線 A", "status": "todo"},
        {"id": uuid4(), "title": "配線 B", "status": "todo"},
    ]
    _detail(monkeypatch, detail)
    with pytest.raises(project_tools.AmbiguousError):
        await project_tools._resolve_task(PROJECT_ID, "配線")


# ============================================================
# 讀取工具
# ============================================================


@pytest.mark.asyncio
async def test_find_project_returns_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        project_service,
        "list_projects",
        AsyncMock(
            return_value={
                "items": [{"id": PROJECT_ID, "name": "亦達自動化", "status": "active"}],
                "total": 1,
            }
        ),
    )
    result = await project_tools.find_project("亦達", ctos_user_id=7)
    assert result["ok"] is True
    assert result["count"] == 1
    assert result["candidates"][0]["id"] == str(PROJECT_ID)


@pytest.mark.asyncio
async def test_find_project_rejects_bad_status(monkeypatch) -> None:
    listed = AsyncMock()
    monkeypatch.setattr(project_service, "list_projects", listed)
    result = await project_tools.find_project("亦達", status="ongoing", ctos_user_id=7)
    assert result["ok"] is False
    assert "status" in result["error"]
    listed.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_project_by_id(monkeypatch) -> None:
    _detail(monkeypatch)
    result = await project_tools.get_project(project_id=str(PROJECT_ID), ctos_user_id=7)
    assert result["ok"] is True
    assert result["project"]["id"] == str(PROJECT_ID)
    assert result["project"]["milestones"][0]["is_overdue"] is True
    assert result["project"]["progress"] == 50


@pytest.mark.asyncio
async def test_get_project_by_name_ambiguous(monkeypatch) -> None:
    monkeypatch.setattr(
        project_service,
        "list_projects",
        AsyncMock(
            return_value={
                "items": [
                    {"id": PROJECT_ID, "name": "亦達自動化"},
                    {"id": OTHER_PROJECT_ID, "name": "亦達二期"},
                ],
                "total": 2,
            }
        ),
    )
    result = await project_tools.get_project(name="亦達", ctos_user_id=7)
    assert result["need_confirmation"] is True
    assert len(result["candidates"]) == 2


@pytest.mark.asyncio
async def test_get_project_requires_id_or_name() -> None:
    result = await project_tools.get_project(ctos_user_id=7)
    assert result["ok"] is False
    assert result["not_found"] is True


@pytest.mark.asyncio
async def test_get_project_detail_missing(monkeypatch) -> None:
    _detail(monkeypatch, None)
    result = await project_tools.get_project(project_id=str(PROJECT_ID), ctos_user_id=7)
    assert result == {"ok": False, "not_found": True, "error": "找不到專案"}


@pytest.mark.asyncio
async def test_list_overdue_milestones(monkeypatch) -> None:
    monkeypatch.setattr(
        project_service,
        "get_summary",
        AsyncMock(
            return_value={
                "active_count": 4,
                "overdue_milestones": [
                    {
                        "project_id": PROJECT_ID,
                        "project_name": "亦達自動化",
                        "milestone_id": MILESTONE_ID,
                        "name": "出機",
                        "due_date": date(2026, 9, 1),
                        "days_overdue": 11,
                    }
                ],
            }
        ),
    )
    result = await project_tools.list_overdue_milestones(ctos_user_id=7)
    assert result["ok"] is True
    assert result["active_count"] == 4
    assert result["count"] == 1
    assert result["overdue_milestones"][0]["due_date"] == "2026-09-01"


@pytest.mark.asyncio
async def test_list_tasks_filters_by_status_and_assignee(monkeypatch) -> None:
    _detail(monkeypatch)
    result = await project_tools.list_tasks(str(PROJECT_ID), status="done", ctos_user_id=7)
    assert [t["title"] for t in result["tasks"]] == ["現場試車"]

    by_user = await project_tools.list_tasks(
        str(PROJECT_ID), assignee="yaze", ctos_user_id=7
    )
    assert [t["title"] for t in by_user["tasks"]] == ["配電盤配線"]
    assert by_user["count"] == 1


@pytest.mark.asyncio
async def test_list_tasks_rejects_bad_status(monkeypatch) -> None:
    detail = _detail(monkeypatch)
    result = await project_tools.list_tasks(str(PROJECT_ID), status="pending", ctos_user_id=7)
    assert result["ok"] is False
    detail.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_tools_do_not_need_membership(monkeypatch) -> None:
    """讀取只看 app 權限，不是成員也能查（跟 REST 一致）"""
    _as_member(monkeypatch, False)
    _detail(monkeypatch)
    result = await project_tools.get_project(project_id=str(PROJECT_ID), ctos_user_id=7)
    assert result["ok"] is True


# ============================================================
# 寫入工具
# ============================================================


@pytest.mark.asyncio
async def test_create_task_resolves_assignee_and_milestone(monkeypatch) -> None:
    _detail(monkeypatch)
    created = AsyncMock(
        return_value={
            "id": TASK_ID,
            "project_id": PROJECT_ID,
            "title": "配電盤配線",
            "status": "todo",
            "assignee_id": 7,
            "due_date": date(2026, 10, 1),
        }
    )
    monkeypatch.setattr(project_service, "create_task", created)

    result = await project_tools.create_task(
        str(PROJECT_ID),
        "配電盤配線",
        assignee="亞澤",
        milestone="出機",
        due_date="2026-10-01",
        ctos_user_id=7,
    )

    assert result["ok"] is True
    assert result["task_id"] == str(TASK_ID)
    payload = created.await_args[0][1]
    assert payload["assignee_id"] == 7
    assert payload["milestone_id"] == MILESTONE_ID
    assert payload["due_date"] == date(2026, 10, 1)


@pytest.mark.asyncio
async def test_create_task_rejects_bad_due_date(monkeypatch) -> None:
    created = AsyncMock()
    monkeypatch.setattr(project_service, "create_task", created)
    result = await project_tools.create_task(
        str(PROJECT_ID), "x", due_date="十月一日", ctos_user_id=7
    )
    assert result["ok"] is False
    assert "欄位不合法" in result["error"]
    created.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_task_requires_title(monkeypatch) -> None:
    created = AsyncMock()
    monkeypatch.setattr(project_service, "create_task", created)
    result = await project_tools.create_task(str(PROJECT_ID), "", ctos_user_id=7)
    assert result["ok"] is False
    created.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_task_denied_for_non_member(monkeypatch) -> None:
    _as_member(monkeypatch, False)
    created = AsyncMock()
    monkeypatch.setattr(project_service, "create_task", created)

    result = await project_tools.create_task(str(PROJECT_ID), "配線", ctos_user_id=7)

    assert result == {"ok": False, "error": "只有專案成員能編輯"}
    created.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_task_allowed_for_member(monkeypatch) -> None:
    _as_member(monkeypatch, True)
    monkeypatch.setattr(
        project_service,
        "create_task",
        AsyncMock(return_value={"id": TASK_ID, "project_id": PROJECT_ID, "title": "配線", "status": "todo"}),
    )
    result = await project_tools.create_task(str(PROJECT_ID), "配線", ctos_user_id=7)
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_write_denied_when_user_unknown(monkeypatch) -> None:
    """沒綁 CTOS 帳號的 bot 使用者不能寫"""
    monkeypatch.setattr(
        project_tools,
        "get_user_role_and_permissions",
        AsyncMock(side_effect=AssertionError("不該查角色")),
    )
    created = AsyncMock()
    monkeypatch.setattr(project_service, "create_task", created)
    result = await project_tools.create_task(str(PROJECT_ID), "配線", ctos_user_id=None)
    assert result == {"ok": False, "error": "只有專案成員能編輯"}
    created.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_validates_fields(monkeypatch) -> None:
    _detail(monkeypatch)
    updated = AsyncMock()
    monkeypatch.setattr(project_service, "update_task", updated)
    result = await project_tools.update_task(
        str(PROJECT_ID), str(TASK_ID), {"status": "finished"}, ctos_user_id=7
    )
    assert result["ok"] is False
    assert "欄位不合法" in result["error"]
    updated.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_resolves_assignee_name(monkeypatch) -> None:
    _detail(monkeypatch)
    updated = AsyncMock(
        return_value={
            "id": TASK_ID,
            "project_id": PROJECT_ID,
            "title": "配電盤配線",
            "status": "doing",
            "assignee_id": 8,
        }
    )
    monkeypatch.setattr(project_service, "update_task", updated)

    result = await project_tools.update_task(
        str(PROJECT_ID),
        "配線",
        {"status": "doing", "assignee": "阿明華", "due_date": "2026-10-05"},
        ctos_user_id=7,
    )

    assert result["ok"] is True
    payload = updated.await_args[0][2]
    assert payload["assignee_id"] == 9
    assert payload["status"] == "doing"
    assert payload["due_date"] == date(2026, 10, 5)


@pytest.mark.asyncio
async def test_update_task_requires_fields(monkeypatch) -> None:
    updated = AsyncMock()
    monkeypatch.setattr(project_service, "update_task", updated)
    result = await project_tools.update_task(str(PROJECT_ID), str(TASK_ID), {}, ctos_user_id=7)
    assert result["ok"] is False
    updated.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_not_found(monkeypatch) -> None:
    _detail(monkeypatch)
    monkeypatch.setattr(project_service, "update_task", AsyncMock(return_value=None))
    result = await project_tools.update_task(
        str(PROJECT_ID), str(TASK_ID), {"status": "done"}, ctos_user_id=7
    )
    assert result["not_found"] is True


@pytest.mark.asyncio
async def test_update_task_maps_milestone_not_in_project(monkeypatch) -> None:
    _detail(monkeypatch)
    monkeypatch.setattr(
        project_service,
        "update_task",
        AsyncMock(side_effect=project_service.MilestoneNotInProjectError("x")),
    )
    result = await project_tools.update_task(
        str(PROJECT_ID), str(TASK_ID), {"status": "done"}, ctos_user_id=7
    )
    assert result["error"] == "里程碑不屬於此專案"


@pytest.mark.asyncio
async def test_create_milestone(monkeypatch) -> None:
    created = AsyncMock(
        return_value={
            "id": MILESTONE_ID,
            "project_id": PROJECT_ID,
            "name": "出機",
            "due_date": date(2026, 11, 1),
            "status": "pending",
            "is_overdue": False,
        }
    )
    monkeypatch.setattr(project_service, "create_milestone", created)
    result = await project_tools.create_milestone(
        str(PROJECT_ID), "出機", "2026-11-01", ctos_user_id=7
    )
    assert result["ok"] is True
    assert result["milestone_id"] == str(MILESTONE_ID)
    assert result["due_date"] == "2026-11-01"
    assert created.await_args[0][1]["due_date"] == date(2026, 11, 1)


@pytest.mark.asyncio
async def test_create_milestone_rejects_bad_date(monkeypatch) -> None:
    created = AsyncMock()
    monkeypatch.setattr(project_service, "create_milestone", created)
    result = await project_tools.create_milestone(
        str(PROJECT_ID), "出機", "十一月", ctos_user_id=7
    )
    assert result["ok"] is False
    created.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_milestone_sets_status_and_date(monkeypatch) -> None:
    _detail(monkeypatch)
    updated = AsyncMock(
        return_value={
            "id": MILESTONE_ID,
            "project_id": PROJECT_ID,
            "name": "出機",
            "due_date": date(2026, 9, 1),
            "status": "completed",
            "completed_at": date.today(),
            "is_overdue": False,
        }
    )
    monkeypatch.setattr(project_service, "update_milestone", updated)

    result = await project_tools.complete_milestone(str(PROJECT_ID), "出機", ctos_user_id=7)

    assert result["ok"] is True
    assert result["status"] == "completed"
    payload = updated.await_args[0][2]
    assert payload["status"] == "completed"
    assert payload["completed_at"] == date.today()


@pytest.mark.asyncio
async def test_complete_milestone_not_found(monkeypatch) -> None:
    _detail(monkeypatch)
    monkeypatch.setattr(project_service, "update_milestone", AsyncMock(return_value=None))
    result = await project_tools.complete_milestone(
        str(PROJECT_ID), str(MILESTONE_ID), ctos_user_id=7
    )
    assert result["not_found"] is True


@pytest.mark.asyncio
async def test_add_project_member_resolves_user(monkeypatch) -> None:
    added = AsyncMock(
        return_value={
            "user_id": 8,
            "username": "amin",
            "display_name": "阿明",
            "role": "member",
        }
    )
    monkeypatch.setattr(project_service, "add_member", added)
    result = await project_tools.add_project_member(str(PROJECT_ID), "amin", ctos_user_id=7)
    assert result["ok"] is True
    assert result["user_id"] == 8
    assert result["role"] == "member"
    assert added.await_args[0][1] == 8


@pytest.mark.asyncio
async def test_add_project_member_ambiguous_user(monkeypatch) -> None:
    added = AsyncMock()
    monkeypatch.setattr(project_service, "add_member", added)
    result = await project_tools.add_project_member(str(PROJECT_ID), "阿", ctos_user_id=7)
    assert result["need_confirmation"] is True
    assert result["entity"] == "使用者"
    added.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_project_member_user_gone(monkeypatch) -> None:
    monkeypatch.setattr(project_service, "add_member", AsyncMock(return_value=None))
    result = await project_tools.add_project_member(str(PROJECT_ID), "amin", ctos_user_id=7)
    assert result["not_found"] is True


@pytest.mark.asyncio
async def test_add_project_member_denied_for_non_member(monkeypatch) -> None:
    _as_member(monkeypatch, False)
    added = AsyncMock()
    monkeypatch.setattr(project_service, "add_member", added)
    result = await project_tools.add_project_member(str(PROJECT_ID), "amin", ctos_user_id=7)
    assert result == {"ok": False, "error": "只有專案成員能編輯"}
    added.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_project_is_not_a_tool() -> None:
    """建立專案不開放給 bot（admin 在網頁做）"""
    assert not hasattr(project_tools, "create_project")
    assert not hasattr(project_tools, "delete_project")


# ============================================================
# 工具與權限對照表
# ============================================================


PROJECT_TOOLS = [
    "find_project",
    "get_project",
    "list_overdue_milestones",
    "list_tasks",
    "create_task",
    "update_task",
    "create_milestone",
    "complete_milestone",
    "add_project_member",
]


def test_every_project_tool_is_in_tool_app_mapping() -> None:
    from ching_tech_os.services.permissions import TOOL_APP_MAPPING

    assert len(PROJECT_TOOLS) == 9
    for name in PROJECT_TOOLS:
        assert TOOL_APP_MAPPING[name] == "project-management", name
        assert callable(getattr(project_tools, name)), name


def test_module_registry_loads_project_tools() -> None:
    from ching_tech_os.modules import BUILTIN_MODULES

    assert (
        BUILTIN_MODULES["project-management"]["mcp_module"]
        == ".services.mcp.project_tools"
    )


_MINIMAL_CALLS: list[tuple[str, tuple, dict]] = [
    ("find_project", ("亦達",), {}),
    ("get_project", (), {"project_id": str(PROJECT_ID)}),
    ("list_overdue_milestones", (), {}),
    ("list_tasks", (str(PROJECT_ID),), {}),
    ("create_task", (str(PROJECT_ID), "配線"), {}),
    ("update_task", (str(PROJECT_ID), str(TASK_ID), {"status": "done"}), {}),
    ("create_milestone", (str(PROJECT_ID), "出機", "2026-11-01"), {}),
    ("complete_milestone", (str(PROJECT_ID), str(MILESTONE_ID)), {}),
    ("add_project_member", (str(PROJECT_ID), "amin"), {}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name, args, kwargs", _MINIMAL_CALLS)
async def test_all_tools_check_permission(
    monkeypatch: pytest.MonkeyPatch, tool_name, args, kwargs
) -> None:
    """每一支都要先過 check_mcp_tool_permission，被拒就不進 service"""
    checker = AsyncMock(return_value=(False, "無權限"))
    monkeypatch.setattr(project_tools, "check_mcp_tool_permission", checker)
    for attr in dir(project_service):
        value = getattr(project_service, attr)
        if attr.startswith("_") or not callable(value):
            continue
        if getattr(value, "__module__", "") == project_service.__name__:
            monkeypatch.setattr(
                project_service, attr, AsyncMock(side_effect=AssertionError(attr))
            )

    result = await getattr(project_tools, tool_name)(*args, **kwargs)

    assert result == {"ok": False, "error": "無權限"}
    assert checker.await_args[0][0] == tool_name


def test_minimal_calls_cover_every_tool() -> None:
    assert [name for name, _a, _k in _MINIMAL_CALLS] == PROJECT_TOOLS


# ============================================================
# 例外路徑補洞
# ============================================================


@pytest.mark.asyncio
async def test_resolve_requires_task_and_milestone_input(monkeypatch) -> None:
    _detail(monkeypatch)
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._resolve_task(PROJECT_ID, "")
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._resolve_milestone(PROJECT_ID, "")
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._resolve_user("")


@pytest.mark.asyncio
async def test_resolve_task_and_milestone_uuid_must_belong_to_project(monkeypatch) -> None:
    _detail(monkeypatch)
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._resolve_task(PROJECT_ID, str(uuid4()))
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._resolve_milestone(PROJECT_ID, str(uuid4()))


@pytest.mark.asyncio
async def test_resolve_milestone_by_name_not_found(monkeypatch) -> None:
    _detail(monkeypatch)
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._resolve_milestone(PROJECT_ID, "不存在的里程碑")


@pytest.mark.asyncio
async def test_project_detail_missing_is_not_found(monkeypatch) -> None:
    _detail(monkeypatch, None)
    with pytest.raises(project_tools.NotFoundError):
        await project_tools._project_detail(PROJECT_ID)


@pytest.mark.asyncio
async def test_service_errors_become_return_values(monkeypatch) -> None:
    """service 炸掉不往外丟，回 {"ok": false, ...}"""
    monkeypatch.setattr(
        project_service, "list_projects", AsyncMock(side_effect=RuntimeError("boom"))
    )
    monkeypatch.setattr(
        project_service, "get_summary", AsyncMock(side_effect=RuntimeError("boom"))
    )
    assert (await project_tools.find_project("亦達", ctos_user_id=7))["ok"] is False
    assert (await project_tools.list_overdue_milestones(ctos_user_id=7))["ok"] is False
    assert (await project_tools.list_tasks("亦達", ctos_user_id=7))["ok"] is False


@pytest.mark.asyncio
async def test_create_milestone_requires_name(monkeypatch) -> None:
    created = AsyncMock()
    monkeypatch.setattr(project_service, "create_milestone", created)
    result = await project_tools.create_milestone(str(PROJECT_ID), "", "2026-11-01", ctos_user_id=7)
    assert result["ok"] is False
    created.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_resolves_milestone_alias(monkeypatch) -> None:
    _detail(monkeypatch)
    updated = AsyncMock(
        return_value={
            "id": TASK_ID,
            "project_id": PROJECT_ID,
            "title": "配電盤配線",
            "status": "todo",
        }
    )
    monkeypatch.setattr(project_service, "update_task", updated)
    result = await project_tools.update_task(
        str(PROJECT_ID), str(TASK_ID), {"milestone": "出機"}, ctos_user_id=7
    )
    assert result["ok"] is True
    assert updated.await_args[0][2]["milestone_id"] == MILESTONE_ID


@pytest.mark.asyncio
async def test_list_tasks_filters_by_display_name(monkeypatch) -> None:
    _detail(monkeypatch)
    result = await project_tools.list_tasks(str(PROJECT_ID), assignee="阿明", ctos_user_id=7)
    assert [t["title"] for t in result["tasks"]] == ["現場試車"]
    assert result["project_name"] == "亦達自動化"
