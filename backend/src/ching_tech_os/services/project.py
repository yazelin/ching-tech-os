"""專案模組服務

asyncpg raw SQL，資料表見 migration 028。
進度與逾期數都在 SQL 裡用 aggregate 算完，Python 不跑迴圈統計。
"""

import logging
from datetime import date
from typing import Any
from uuid import UUID

from ..database import get_connection

logger = logging.getLogger(__name__)


# ============================================================
# 純函式（可獨立測試）
# ============================================================


def calc_progress(done_count: int | None, task_count: int | None) -> int:
    """進度百分比 = done 任務數 ÷ 任務總數，四捨五入到整數；沒有任務時為 0"""
    total = task_count or 0
    if total <= 0:
        return 0
    return round((done_count or 0) * 100 / total)


def is_milestone_overdue(
    due_date: date | None,
    status: str | None,
    today: date | None = None,
) -> bool:
    """逾期 = due_date < 今天 且 status <> 'completed'"""
    if due_date is None:
        return False
    if status == "completed":
        return False
    return due_date < (today or date.today())


# ============================================================
# 專案清單
# ============================================================

# 清單與明細共用的統計欄位：一句 SQL 把任務數、完成數、成員數、逾期里程碑數算完
_PROJECT_STATS_SQL = """
    COALESCE((
        SELECT count(*) FROM tasks t WHERE t.project_id = p.id
    ), 0)::int AS task_count,
    COALESCE((
        SELECT count(*) FILTER (WHERE t.status = 'done')
        FROM tasks t WHERE t.project_id = p.id
    ), 0)::int AS done_count,
    COALESCE((
        SELECT count(*) FROM project_members pm WHERE pm.project_id = p.id
    ), 0)::int AS member_count,
    COALESCE((
        SELECT count(*) FROM milestones m
        WHERE m.project_id = p.id
          AND m.due_date < CURRENT_DATE
          AND m.status <> 'completed'
    ), 0)::int AS overdue_milestones
"""


async def list_projects(
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """專案清單（含進度、成員數、逾期里程碑數）"""
    offset = (max(page, 1) - 1) * page_size
    where = """
        WHERE ($1::text IS NULL OR p.status = $1)
          AND (
            $2::text IS NULL
            OR p.name ILIKE '%' || $2 || '%'
            OR COALESCE(p.customer, '') ILIKE '%' || $2 || '%'
          )
    """
    async with get_connection() as conn:
        total = await conn.fetchval(
            f"SELECT count(*) FROM projects p {where}", status, q
        )
        rows = await conn.fetch(
            f"""
            SELECT
                p.id, p.name, p.customer, p.status, p.owner_id,
                COALESCE(u.display_name, u.username) AS owner_name,
                p.start_date, p.end_date, p.created_at, p.updated_at,
                {_PROJECT_STATS_SQL}
            FROM projects p
            LEFT JOIN users u ON u.id = p.owner_id
            {where}
            ORDER BY p.updated_at DESC
            LIMIT $3 OFFSET $4
            """,
            status,
            q,
            page_size,
            offset,
        )

    items = []
    for row in rows:
        item = dict(row)
        item["progress"] = calc_progress(item.pop("done_count"), item.pop("task_count"))
        items.append(item)
    return {"items": items, "total": int(total or 0)}


# ============================================================
# 專案明細
# ============================================================


async def project_exists(project_id: UUID) -> bool:
    """專案是否存在（權限依賴用）"""
    async with get_connection() as conn:
        found = await conn.fetchval(
            "SELECT 1 FROM projects WHERE id = $1", project_id
        )
    return found is not None


async def get_project_detail(project_id: UUID) -> dict[str, Any] | None:
    """專案明細：主檔＋進度＋成員＋里程碑＋任務＋綁定群組＋知識條目數"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT
                p.id, p.name, p.customer, p.status, p.owner_id,
                COALESCE(u.display_name, u.username) AS owner_name,
                p.start_date, p.end_date, p.description, p.created_by,
                p.created_at, p.updated_at,
                {_PROJECT_STATS_SQL}
            FROM projects p
            LEFT JOIN users u ON u.id = p.owner_id
            WHERE p.id = $1
            """,
            project_id,
        )
        if row is None:
            return None

        member_rows = await conn.fetch(
            """
            SELECT pm.user_id, u.username, u.display_name, pm.role
            FROM project_members pm
            LEFT JOIN users u ON u.id = pm.user_id
            WHERE pm.project_id = $1
            ORDER BY (pm.role = 'owner') DESC, pm.created_at
            """,
            project_id,
        )
        milestone_rows = await conn.fetch(
            """
            SELECT id, project_id, name, due_date, completed_at, status,
                   sort_order, created_at, updated_at
            FROM milestones
            WHERE project_id = $1
            ORDER BY sort_order, due_date
            """,
            project_id,
        )
        task_rows = await conn.fetch(
            """
            SELECT t.id, t.project_id, t.milestone_id, t.title, t.description,
                   t.assignee_id, COALESCE(u.display_name, u.username) AS assignee_name,
                   t.status, t.due_date, t.sort_order, t.created_at, t.updated_at
            FROM tasks t
            LEFT JOIN users u ON u.id = t.assignee_id
            WHERE t.project_id = $1
            ORDER BY t.sort_order, t.created_at
            """,
            project_id,
        )
        group_rows = await conn.fetch(
            """
            SELECT id, platform_type, name AS group_name
            FROM bot_groups
            WHERE project_id = $1
            ORDER BY name
            """,
            project_id,
        )

    detail = dict(row)
    detail["progress"] = calc_progress(
        detail.pop("done_count"), detail.pop("task_count")
    )
    detail.pop("member_count", None)
    detail.pop("overdue_milestones", None)
    detail["members"] = [dict(r) for r in member_rows]
    detail["milestones"] = [
        {**dict(r), "is_overdue": is_milestone_overdue(r["due_date"], r["status"])}
        for r in milestone_rows
    ]
    detail["tasks"] = [dict(r) for r in task_rows]
    detail["bot_groups"] = [dict(r) for r in group_rows]
    detail["knowledge_count"] = count_project_knowledge(str(project_id))
    return detail


def count_project_knowledge(project_id: str) -> int:
    """專案關聯的知識條目數（知識庫是檔案索引，不另開 index）"""
    try:
        from .knowledge import search_knowledge

        return search_knowledge(scope="project", project_id=project_id).total
    except Exception as e:  # pragma: no cover - 知識庫不可用時不擋專案明細
        logger.warning("計算專案知識條目數失敗: %s", e)
        return 0


# ============================================================
# 專案 CRUD
# ============================================================


async def _sync_owner_member(conn, project_id: UUID, owner_id: int | None) -> None:
    """負責人必為成員：原 owner 降成 member，新 owner upsert 成 role='owner'"""
    await conn.execute(
        """
        UPDATE project_members
        SET role = 'member'
        WHERE project_id = $1 AND role = 'owner' AND user_id IS DISTINCT FROM $2
        """,
        project_id,
        owner_id,
    )
    if owner_id is None:
        return
    await conn.execute(
        """
        INSERT INTO project_members (project_id, user_id, role)
        VALUES ($1, $2, 'owner')
        ON CONFLICT (project_id, user_id) DO UPDATE SET role = 'owner'
        """,
        project_id,
        owner_id,
    )


async def create_project(data: dict, created_by: int | None = None) -> dict[str, Any]:
    """建立專案；有指定負責人時自動加成員"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO projects
                (name, customer, status, owner_id, start_date, end_date,
                 description, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            data["name"],
            data.get("customer"),
            data.get("status") or "active",
            data.get("owner_id"),
            data.get("start_date"),
            data.get("end_date"),
            data.get("description"),
            created_by,
        )
        await _sync_owner_member(conn, row["id"], row["owner_id"])
    return dict(row)


# 允許更新的主檔欄位
_PROJECT_UPDATE_FIELDS = (
    "name",
    "customer",
    "status",
    "owner_id",
    "start_date",
    "end_date",
    "description",
)


async def update_project(project_id: UUID, data: dict) -> dict[str, Any] | None:
    """更新主檔（只更新有給的欄位）；改 owner_id 時同步成員"""
    fields = {k: v for k, v in data.items() if k in _PROJECT_UPDATE_FIELDS}
    async with get_connection() as conn:
        if fields:
            names = list(fields.keys())
            assignments = ", ".join(
                f"{name} = ${i + 2}" for i, name in enumerate(names)
            )
            row = await conn.fetchrow(
                f"""
                UPDATE projects
                SET {assignments}, updated_at = NOW()
                WHERE id = $1
                RETURNING *
                """,
                project_id,
                *[fields[name] for name in names],
            )
        else:
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE id = $1", project_id
            )
        if row is None:
            return None
        if "owner_id" in fields:
            await _sync_owner_member(conn, project_id, row["owner_id"])
    return dict(row)


async def delete_project(project_id: UUID) -> bool:
    """刪除專案；先把綁定的 bot_groups.project_id 設回 NULL"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE bot_groups SET project_id = NULL WHERE project_id = $1",
            project_id,
        )
        result = await conn.execute("DELETE FROM projects WHERE id = $1", project_id)
    return result == "DELETE 1"


# ============================================================
# 成員
# ============================================================


async def add_member(project_id: UUID, user_id: int) -> dict[str, Any] | None:
    """加入成員（已存在則沿用原本的 role）"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO project_members (project_id, user_id, role)
            VALUES ($1, $2, 'member')
            ON CONFLICT (project_id, user_id) DO NOTHING
            """,
            project_id,
            user_id,
        )
        row = await conn.fetchrow(
            """
            SELECT pm.user_id, u.username, u.display_name, pm.role
            FROM project_members pm
            LEFT JOIN users u ON u.id = pm.user_id
            WHERE pm.project_id = $1 AND pm.user_id = $2
            """,
            project_id,
            user_id,
        )
    return dict(row) if row else None


async def remove_member(project_id: UUID, user_id: int) -> str:
    """移除成員

    Returns:
        'removed'、'owner'（負責人不能移除）或 'not_found'
    """
    async with get_connection() as conn:
        role = await conn.fetchval(
            "SELECT role FROM project_members WHERE project_id = $1 AND user_id = $2",
            project_id,
            user_id,
        )
        if role is None:
            return "not_found"
        if role == "owner":
            return "owner"
        await conn.execute(
            "DELETE FROM project_members WHERE project_id = $1 AND user_id = $2",
            project_id,
            user_id,
        )
    return "removed"


# ============================================================
# 里程碑
# ============================================================

_MILESTONE_UPDATE_FIELDS = ("name", "due_date", "completed_at", "status", "sort_order")


def _with_overdue(row) -> dict[str, Any]:
    """補上 is_overdue"""
    data = dict(row)
    data["is_overdue"] = is_milestone_overdue(data["due_date"], data["status"])
    return data


async def create_milestone(project_id: UUID, data: dict) -> dict[str, Any]:
    """建立里程碑"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO milestones
                (project_id, name, due_date, completed_at, status, sort_order)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            project_id,
            data["name"],
            data["due_date"],
            data.get("completed_at"),
            data.get("status") or "pending",
            data.get("sort_order") or 0,
        )
    return _with_overdue(row)


async def update_milestone(
    project_id: UUID, milestone_id: UUID, data: dict
) -> dict[str, Any] | None:
    """更新里程碑"""
    fields = {k: v for k, v in data.items() if k in _MILESTONE_UPDATE_FIELDS}
    async with get_connection() as conn:
        if not fields:
            row = await conn.fetchrow(
                "SELECT * FROM milestones WHERE id = $1 AND project_id = $2",
                milestone_id,
                project_id,
            )
        else:
            names = list(fields.keys())
            assignments = ", ".join(
                f"{name} = ${i + 3}" for i, name in enumerate(names)
            )
            row = await conn.fetchrow(
                f"""
                UPDATE milestones
                SET {assignments}, updated_at = NOW()
                WHERE id = $1 AND project_id = $2
                RETURNING *
                """,
                milestone_id,
                project_id,
                *[fields[name] for name in names],
            )
    return _with_overdue(row) if row else None


async def delete_milestone(project_id: UUID, milestone_id: UUID) -> bool:
    """刪除里程碑（底下任務的 milestone_id 由 FK 設為 NULL）"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM milestones WHERE id = $1 AND project_id = $2",
            milestone_id,
            project_id,
        )
    return result == "DELETE 1"


# ============================================================
# 任務
# ============================================================

_TASK_UPDATE_FIELDS = (
    "title",
    "description",
    "milestone_id",
    "assignee_id",
    "status",
    "due_date",
    "sort_order",
)


async def create_task(project_id: UUID, data: dict) -> dict[str, Any]:
    """建立任務"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO tasks
                (project_id, milestone_id, title, description, assignee_id,
                 status, due_date, sort_order)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            project_id,
            data.get("milestone_id"),
            data["title"],
            data.get("description"),
            data.get("assignee_id"),
            data.get("status") or "todo",
            data.get("due_date"),
            data.get("sort_order") or 0,
        )
    return dict(row)


async def update_task(
    project_id: UUID, task_id: UUID, data: dict
) -> dict[str, Any] | None:
    """更新任務"""
    fields = {k: v for k, v in data.items() if k in _TASK_UPDATE_FIELDS}
    async with get_connection() as conn:
        if not fields:
            row = await conn.fetchrow(
                "SELECT * FROM tasks WHERE id = $1 AND project_id = $2",
                task_id,
                project_id,
            )
        else:
            names = list(fields.keys())
            assignments = ", ".join(
                f"{name} = ${i + 3}" for i, name in enumerate(names)
            )
            row = await conn.fetchrow(
                f"""
                UPDATE tasks
                SET {assignments}, updated_at = NOW()
                WHERE id = $1 AND project_id = $2
                RETURNING *
                """,
                task_id,
                project_id,
                *[fields[name] for name in names],
            )
    return dict(row) if row else None


async def delete_task(project_id: UUID, task_id: UUID) -> bool:
    """刪除任務"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM tasks WHERE id = $1 AND project_id = $2",
            task_id,
            project_id,
        )
    return result == "DELETE 1"


# ============================================================
# Dashboard 摘要
# ============================================================

# 逾期清單依到期日升冪，最多 20 筆
SUMMARY_OVERDUE_LIMIT = 20


async def get_summary() -> dict[str, Any]:
    """dashboard 摘要：進行中專案數與逾期里程碑清單"""
    async with get_connection() as conn:
        active_count = await conn.fetchval(
            "SELECT count(*) FROM projects WHERE status = 'active'"
        )
        rows = await conn.fetch(
            """
            SELECT
                m.project_id,
                p.name AS project_name,
                m.id AS milestone_id,
                m.name,
                m.due_date,
                (CURRENT_DATE - m.due_date)::int AS days_overdue
            FROM milestones m
            JOIN projects p ON p.id = m.project_id
            WHERE m.due_date < CURRENT_DATE
              AND m.status <> 'completed'
              AND p.status = 'active'
            ORDER BY m.due_date ASC
            LIMIT $1
            """,
            SUMMARY_OVERDUE_LIMIT,
        )
    return {
        "active_count": int(active_count or 0),
        "overdue_milestones": [dict(r) for r in rows],
    }
