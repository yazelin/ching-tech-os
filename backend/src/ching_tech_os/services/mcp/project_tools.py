"""專案模組 MCP 工具

寫法照 `services/mcp/erp_tools.py`：`_guard`（連線＋工具權限）、`_fail`（例外翻成
回傳值）、`_validated_fields`（欄位先過 Update 模型），解析不唯一時回
`{"need_confirmation": true, "candidates": [...]}` 讓 agent 回去問人。

SQL 全部留在 `services/project.py`，這裡只做三件事：

1. **輸入容忍自然語言**：專案吃名稱或 UUID、任務吃標題、里程碑吃名稱、
   負責人吃 username 或顯示名稱（使用者清單來源與 `/api/user/list` 同一張表）。
2. **權限**：讀取只看工具權限（`project-management`）；寫入另外過
   `api/project.py` 的 `require_project_editor` 等價檢查——admin 一律過，
   否則必須是該專案成員。
3. **建立專案不開放給 bot**：那是管理員在網頁做的事，所以這裡沒有
   `create_project`／`delete_project`。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from .server import check_mcp_tool_permission, ensure_db_connection, logger, mcp
from ...models.project import (
    MilestoneCreate,
    MilestoneUpdate,
    TaskCreate,
    TaskUpdate,
)
from ...services import project as project_service
from ...services.permissions import is_project_member
from ...services.user import get_all_users, get_user_role_and_permissions

# 回給 agent 的候選上限（與 erp_tools 一致：三個，多的讓他再問）
CANDIDATE_LIMIT = 3

# 名稱解析時一次撈幾筆專案（超過上限只是用來判斷「有更多」）
_PROJECT_SEARCH_SIZE = 20

# 狀態枚舉（REST 端由 models/project.py 的 Literal 鎖住，MCP 這邊手動比對）
_PROJECT_STATUSES = {"planning", "active", "on_hold", "completed", "cancelled"}
_TASK_STATUSES = {"todo", "doing", "done"}

_NOT_MEMBER = "只有專案成員能編輯"


# ============================================================
# 例外
# ============================================================


class ProjectToolError(Exception):
    """專案工具層的基底例外（service 的例外另外在 `_fail` 處理）"""


class NotFoundError(ProjectToolError):
    """解析不到任何候選"""

    def __init__(self, entity: str, query: str) -> None:
        self.entity = entity
        self.query = query
        super().__init__(f"找不到{entity}：{query}")


class AmbiguousError(ProjectToolError):
    """解析到多個候選，要人或 agent 挑一個"""

    def __init__(self, entity: str, query: str, candidates: list[dict[str, Any]]) -> None:
        self.entity = entity
        self.query = query
        self.candidates = candidates
        super().__init__(f"{entity}「{query}」有 {len(candidates)} 個候選，請確認")


class InvalidFieldError(ProjectToolError):
    """欄位沒通過 Update 模型驗證"""


# ============================================================
# 共用輔助
# ============================================================


def _clean(value: Any) -> Any:
    """UUID／date／datetime 轉成可序列化的字串（MCP 回傳要能 JSON 化）"""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _error(message: str) -> dict:
    return {"ok": False, "error": message}


def _fail(exc: Exception) -> dict:
    """把例外翻成工具回傳，不往外丟（agent 拿到的是資料不是 traceback）"""
    if isinstance(exc, AmbiguousError):
        return {
            "ok": False,
            "need_confirmation": True,
            "entity": exc.entity,
            "query": exc.query,
            "candidates": _clean(exc.candidates),
            "message": str(exc),
        }
    if isinstance(exc, NotFoundError):
        return {"ok": False, "not_found": True, "error": str(exc)}
    if isinstance(exc, project_service.UserNotFoundError):
        return {"ok": False, "not_found": True, "error": f"使用者不存在：{exc}"}
    if isinstance(exc, project_service.MilestoneNotInProjectError):
        return _error("里程碑不屬於此專案")
    if isinstance(exc, ProjectToolError):
        return _error(str(exc))
    logger.error("專案工具執行失敗: %s", exc)
    return _error(f"執行失敗：{exc}")


async def _guard(tool_name: str, ctos_user_id: int | None) -> dict | None:
    """連線 ＋ 工具權限；有問題回錯誤 dict，沒問題回 None"""
    await ensure_db_connection()
    allowed, message = await check_mcp_tool_permission(tool_name, ctos_user_id)
    if not allowed:
        return _error(message)
    return None


async def _require_editor(project_id: UUID, ctos_user_id: int | None) -> dict | None:
    """`api/project.py` 的 `require_project_editor` 等價檢查

    admin 一律過，否則必須是該專案成員；沒綁 CTOS 帳號（`ctos_user_id` 是 None）
    一律擋下來。專案存不存在由前面的解析負責。
    """
    if ctos_user_id is not None:
        info = await get_user_role_and_permissions(ctos_user_id)
        if (info or {}).get("role") == "admin":
            return None
        if await is_project_member(ctos_user_id, str(project_id)):
            return None
    return _error(_NOT_MEMBER)


def _validated_fields(model, fields: dict) -> dict:
    """把 agent 給的 fields 過一次模型

    狀態值不在 Literal 裡、NOT NULL 欄位送 null、日期格式不對，都在這裡就被擋下來，
    不會變成資料庫例外（回給 agent 的是「哪個欄位不行」）。

    Raises:
        InvalidFieldError: 驗證失敗（呼叫端會翻成 {"ok": false, "error": ...}）
    """
    try:
        body = model.model_validate(fields)
    except ValidationError as e:
        problems = "；".join(
            f"{'.'.join(str(x) for x in err['loc']) or '欄位'}：{err['msg']}"
            for err in e.errors()
        )
        raise InvalidFieldError(f"欄位不合法（{problems}）") from e
    return body.model_dump(exclude_unset=True)


# ============================================================
# 解析（輸入容忍自然語言）
# ============================================================


def _unique(entity: str, query: str, matches: list[dict], key: str) -> Any:
    """唯一命中才回，多個候選拋 Ambiguous，零命中拋 NotFound"""
    if not matches:
        raise NotFoundError(entity, query)
    if len(matches) > 1:
        raise AmbiguousError(entity, query, matches[:CANDIDATE_LIMIT])
    return matches[0][key]


async def _resolve_project(project: str | None) -> UUID:
    """專案吃 UUID 或名稱／客戶（名稱走 `list_projects` 的 q，不另外寫 SQL）"""
    if not project:
        raise NotFoundError("專案", "")
    try:
        project_id = UUID(project)
    except ValueError:
        pass
    else:
        if await project_service.project_exists(project_id):
            return project_id
        raise NotFoundError("專案", project)

    result = await project_service.list_projects(
        q=project, page_size=_PROJECT_SEARCH_SIZE
    )
    items = result.get("items") or []
    exact = [item for item in items if item.get("name") == project]
    candidates = exact or items
    return _unique(
        "專案",
        project,
        [
            {
                "id": item["id"],
                "name": item.get("name"),
                "customer": item.get("customer"),
                "status": item.get("status"),
            }
            for item in candidates
        ],
        "id",
    )


async def _project_detail(project_id: UUID) -> dict:
    detail = await project_service.get_project_detail(project_id)
    if detail is None:
        raise NotFoundError("專案", str(project_id))
    return detail


def _match_by_text(rows: list[dict], query: str, field: str) -> list[dict]:
    """先比完全相同，沒有才比子字串（大小寫不敏感）"""
    exact = [row for row in rows if (row.get(field) or "") == query]
    if exact:
        return exact
    lowered = query.casefold()
    return [row for row in rows if lowered in (row.get(field) or "").casefold()]


async def _resolve_task(project_id: UUID, task: str | None, detail: dict | None = None) -> UUID:
    """任務吃 UUID 或標題（在專案明細裡找，不另外查 SQL）"""
    if not task:
        raise NotFoundError("任務", "")
    rows = (detail or await _project_detail(project_id)).get("tasks") or []
    try:
        task_id = UUID(task)
    except ValueError:
        pass
    else:
        if any(row["id"] == task_id for row in rows):
            return task_id
        raise NotFoundError("任務", task)
    matches = [
        {"id": row["id"], "title": row.get("title"), "status": row.get("status")}
        for row in _match_by_text(rows, task, "title")
    ]
    return _unique("任務", task, matches, "id")


async def _resolve_milestone(
    project_id: UUID, milestone: str | None, detail: dict | None = None
) -> UUID:
    """里程碑吃 UUID 或名稱"""
    if not milestone:
        raise NotFoundError("里程碑", "")
    rows = (detail or await _project_detail(project_id)).get("milestones") or []
    try:
        milestone_id = UUID(milestone)
    except ValueError:
        pass
    else:
        if any(row["id"] == milestone_id for row in rows):
            return milestone_id
        raise NotFoundError("里程碑", milestone)
    matches = [
        {
            "id": row["id"],
            "name": row.get("name"),
            "due_date": row.get("due_date"),
            "status": row.get("status"),
        }
        for row in _match_by_text(rows, milestone, "name")
    ]
    return _unique("里程碑", milestone, matches, "id")


async def _resolve_user(user: str | None) -> int:
    """使用者吃 username 或顯示名稱（來源與 /api/user/list 同一張表）"""
    if not user:
        raise NotFoundError("使用者", "")
    rows = await get_all_users()
    lowered = user.casefold()
    exact = [
        row
        for row in rows
        if (row.get("username") or "").casefold() == lowered
        or (row.get("display_name") or "").casefold() == lowered
    ]
    partial = [
        row
        for row in rows
        if lowered in (row.get("username") or "").casefold()
        or lowered in (row.get("display_name") or "").casefold()
    ]
    matches = [
        {
            "user_id": row["id"],
            "username": row.get("username"),
            "display_name": row.get("display_name"),
        }
        for row in (exact or partial)
    ]
    return _unique("使用者", user, matches, "user_id")


# ============================================================
# 讀取
# ============================================================


@mcp.tool()
async def find_project(
    query: str,
    status: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """模糊搜尋專案（名稱或客戶）

    Args:
        query: 專案名稱或客戶名稱的一部分
        status: planning／active／on_hold／completed／cancelled，不給就全部
        ctos_user_id: CTOS 用戶 ID（伺服器會自動帶）
    """
    guard = await _guard("find_project", ctos_user_id)
    if guard:
        return guard
    if status is not None and status not in _PROJECT_STATUSES:
        return _error(
            f"status 不合法：{status}"
            "（只能是 planning／active／on_hold／completed／cancelled）"
        )
    try:
        result = await project_service.list_projects(
            status=status, q=query, page_size=_PROJECT_SEARCH_SIZE
        )
    except Exception as e:
        return _fail(e)
    items = result.get("items") or []
    return {
        "ok": True,
        "count": len(items),
        "total": result.get("total", len(items)),
        "candidates": _clean(items),
    }


@mcp.tool()
async def get_project(
    project_id: str | None = None,
    name: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """專案明細（成員、里程碑含逾期、任務、綁定群組、進度）

    Args:
        project_id: 專案 UUID（有就優先用）
        name: 專案名稱或客戶，會做模糊解析
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("get_project", ctos_user_id)
    if guard:
        return guard
    try:
        pid = await _resolve_project(project_id or name)
        detail = await project_service.get_project_detail(pid)
    except Exception as e:
        return _fail(e)
    if detail is None:
        return {"ok": False, "not_found": True, "error": "找不到專案"}
    return {"ok": True, "project": _clean(detail)}


@mcp.tool()
async def list_overdue_milestones(ctos_user_id: int | None = None) -> dict:
    """逾期里程碑清單（依到期日升冪，最多 20 筆）＋進行中專案數

    逾期＝到期日已過、里程碑未完成，且所屬專案還在進行中。

    Args:
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("list_overdue_milestones", ctos_user_id)
    if guard:
        return guard
    try:
        summary = await project_service.get_summary()
    except Exception as e:
        return _fail(e)
    rows = summary.get("overdue_milestones") or []
    return {
        "ok": True,
        "active_count": summary.get("active_count", 0),
        "count": len(rows),
        "overdue_milestones": _clean(rows),
    }


@mcp.tool()
async def list_tasks(
    project: str,
    status: str | None = None,
    assignee: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """專案任務清單

    Args:
        project: 專案名稱或 UUID
        status: todo／doing／done，不給就全部
        assignee: 負責人 username 或顯示名稱，不給就全部
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("list_tasks", ctos_user_id)
    if guard:
        return guard
    if status is not None and status not in _TASK_STATUSES:
        return _error(f"status 不合法：{status}（只能是 todo／doing／done）")
    try:
        pid = await _resolve_project(project)
        assignee_id = await _resolve_user(assignee) if assignee else None
        detail = await _project_detail(pid)
    except Exception as e:
        return _fail(e)
    rows = [
        row
        for row in (detail.get("tasks") or [])
        if (status is None or row.get("status") == status)
        and (assignee_id is None or row.get("assignee_id") == assignee_id)
    ]
    return {
        "ok": True,
        "project_id": str(pid),
        "project_name": detail.get("name"),
        "count": len(rows),
        "tasks": _clean(rows),
    }


# ============================================================
# 任務
# ============================================================


@mcp.tool()
async def create_task(
    project: str,
    title: str,
    assignee: str | None = None,
    milestone: str | None = None,
    due_date: str | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """建立任務（要是專案成員或管理員）

    Args:
        project: 專案名稱或 UUID
        title: 任務標題（必填）
        assignee: 負責人 username 或顯示名稱
        milestone: 里程碑名稱或 UUID（要屬於同一個專案）
        due_date: 到期日 YYYY-MM-DD
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("create_task", ctos_user_id)
    if guard:
        return guard
    if not title:
        return _error("任務標題必填")
    try:
        pid = await _resolve_project(project)
        denied = await _require_editor(pid, ctos_user_id)
        if denied:
            return denied
        payload = _validated_fields(
            TaskCreate,
            {
                "title": title,
                "assignee_id": await _resolve_user(assignee) if assignee else None,
                "milestone_id": (
                    str(await _resolve_milestone(pid, milestone)) if milestone else None
                ),
                "due_date": due_date,
            },
        )
        row = await project_service.create_task(pid, payload)
    except Exception as e:
        return _fail(e)
    return {
        "ok": True,
        "project_id": str(pid),
        "task_id": str(row["id"]),
        "title": row["title"],
        "status": row["status"],
    }


# fields 裡吃名稱的鍵 → 轉成資料表欄位
_TASK_FIELD_ALIASES = {"assignee": "assignee_id", "milestone": "milestone_id"}


@mcp.tool()
async def update_task(
    project: str,
    task: str,
    fields: dict | None = None,
    ctos_user_id: int | None = None,
) -> dict:
    """更新任務（狀態、負責人、到期日等；要是專案成員或管理員）

    Args:
        project: 專案名稱或 UUID
        task: 任務標題或 UUID
        fields: 要改的欄位，例如 `{"status": "done"}`、`{"assignee": "亞澤"}`、
            `{"due_date": "2026-10-01"}`；`assignee`／`milestone` 吃名稱，
            也可以直接給 `assignee_id`／`milestone_id`
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("update_task", ctos_user_id)
    if guard:
        return guard
    if not fields:
        return _error("沒有要更新的欄位")
    try:
        pid = await _resolve_project(project)
        denied = await _require_editor(pid, ctos_user_id)
        if denied:
            return denied
        detail = await _project_detail(pid)
        task_id = await _resolve_task(pid, task, detail)
        payload = dict(fields)
        if payload.get("assignee") is not None:
            payload["assignee_id"] = await _resolve_user(payload["assignee"])
        if payload.get("milestone") is not None:
            payload["milestone_id"] = str(
                await _resolve_milestone(pid, payload["milestone"], detail)
            )
        for alias in _TASK_FIELD_ALIASES:
            payload.pop(alias, None)
        row = await project_service.update_task(
            pid, task_id, _validated_fields(TaskUpdate, payload)
        )
    except Exception as e:
        return _fail(e)
    if row is None:
        return {"ok": False, "not_found": True, "error": "找不到任務"}
    return {
        "ok": True,
        "project_id": str(pid),
        "task_id": str(row["id"]),
        "title": row["title"],
        "status": row["status"],
    }


# ============================================================
# 里程碑
# ============================================================


@mcp.tool()
async def create_milestone(
    project: str,
    name: str,
    due_date: str,
    ctos_user_id: int | None = None,
) -> dict:
    """建立里程碑（要是專案成員或管理員）

    Args:
        project: 專案名稱或 UUID
        name: 里程碑名稱
        due_date: 到期日 YYYY-MM-DD（必填）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("create_milestone", ctos_user_id)
    if guard:
        return guard
    if not name:
        return _error("里程碑名稱必填")
    try:
        pid = await _resolve_project(project)
        denied = await _require_editor(pid, ctos_user_id)
        if denied:
            return denied
        payload = _validated_fields(
            MilestoneCreate, {"name": name, "due_date": due_date}
        )
        row = await project_service.create_milestone(pid, payload)
    except Exception as e:
        return _fail(e)
    return {
        "ok": True,
        "project_id": str(pid),
        "milestone_id": str(row["id"]),
        "name": row["name"],
        "due_date": _clean(row["due_date"]),
        "status": row["status"],
    }


@mcp.tool()
async def complete_milestone(
    project: str,
    milestone: str,
    ctos_user_id: int | None = None,
) -> dict:
    """把里程碑標記為完成（完成日期填今天；要是專案成員或管理員）

    Args:
        project: 專案名稱或 UUID
        milestone: 里程碑名稱或 UUID
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("complete_milestone", ctos_user_id)
    if guard:
        return guard
    try:
        pid = await _resolve_project(project)
        denied = await _require_editor(pid, ctos_user_id)
        if denied:
            return denied
        milestone_id = await _resolve_milestone(pid, milestone)
        payload = _validated_fields(
            MilestoneUpdate, {"status": "completed", "completed_at": date.today()}
        )
        row = await project_service.update_milestone(pid, milestone_id, payload)
    except Exception as e:
        return _fail(e)
    if row is None:
        return {"ok": False, "not_found": True, "error": "找不到里程碑"}
    return {
        "ok": True,
        "project_id": str(pid),
        "milestone_id": str(row["id"]),
        "name": row["name"],
        "status": row["status"],
        "completed_at": _clean(row.get("completed_at")),
    }


# ============================================================
# 成員
# ============================================================


@mcp.tool()
async def add_project_member(
    project: str,
    user: str,
    ctos_user_id: int | None = None,
) -> dict:
    """把人加進專案成員（要是專案成員或管理員）

    Args:
        project: 專案名稱或 UUID
        user: username 或顯示名稱（解析不唯一時回候選，不會自己挑）
        ctos_user_id: CTOS 用戶 ID
    """
    guard = await _guard("add_project_member", ctos_user_id)
    if guard:
        return guard
    try:
        pid = await _resolve_project(project)
        denied = await _require_editor(pid, ctos_user_id)
        if denied:
            return denied
        user_id = await _resolve_user(user)
        row = await project_service.add_member(pid, user_id)
    except Exception as e:
        return _fail(e)
    if row is None:
        return {"ok": False, "not_found": True, "error": "使用者不存在"}
    return {
        "ok": True,
        "project_id": str(pid),
        "user_id": row["user_id"],
        "username": row.get("username"),
        "display_name": row.get("display_name"),
        "role": row.get("role"),
    }
