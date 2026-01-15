"""Line Bot MCP Server

使用 FastMCP 定義工具，支援：
- Claude Code CLI（stdio 模式）
- Line Bot AI（直接呼叫）
- 其他 MCP 客戶端

工具只定義一次，Schema 自動從 type hints 和 docstring 生成。
"""

import asyncio
import logging
import uuid as uuid_module
from datetime import datetime, timedelta, timezone
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from ..database import get_connection, init_db_pool

logger = logging.getLogger("mcp_server")

# 台北時區 (UTC+8)
TAIPEI_TZ = timezone(timedelta(hours=8))


def to_taipei_time(dt: datetime) -> datetime:
    """將 datetime 轉換為台北時區"""
    if dt is None:
        return None
    # 如果是 naive datetime，假設為 UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TAIPEI_TZ)

# 建立 FastMCP Server 實例
mcp = FastMCP(
    "ching-tech-os",
    instructions="擎添工業 OS 的 AI 工具，可查詢專案、會議、成員等資訊。",
)


# ============================================================
# 資料庫連線輔助函數
# ============================================================


async def ensure_db_connection():
    """確保資料庫連線池已初始化（懶初始化）"""
    from ..database import _pool
    if _pool is None:
        logger.info("初始化資料庫連線池...")
        await init_db_pool()


# ============================================================
# 權限檢查輔助函數
# ============================================================


async def check_project_member_permission(project_id: str, user_id: int) -> bool:
    """
    檢查用戶是否為專案成員

    Args:
        project_id: 專案 UUID 字串
        user_id: CTOS 用戶 ID

    Returns:
        True 表示用戶是專案成員，可以操作
    """
    from uuid import UUID as UUID_type
    await ensure_db_connection()
    async with get_connection() as conn:
        exists = await conn.fetchval(
            """
            SELECT 1 FROM project_members
            WHERE project_id = $1 AND user_id = $2
            """,
            UUID_type(project_id),
            user_id,
        )
        return exists is not None


# ============================================================
# MCP 工具定義
# ============================================================


@mcp.tool()
async def query_project(project_id: str | None = None, keyword: str | None = None) -> str:
    """
    查詢專案資訊

    Args:
        project_id: 專案 UUID，查詢特定專案
        keyword: 搜尋關鍵字，搜尋專案名稱和描述
    """
    await ensure_db_connection()
    async with get_connection() as conn:
        if project_id:
            # 查詢特定專案
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE id = $1",
                UUID(project_id),
            )
            if not row:
                return f"找不到專案 ID: {project_id}"

            # 取得里程碑統計
            milestone_stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress
                FROM project_milestones
                WHERE project_id = $1
                """,
                UUID(project_id),
            )

            # 取得成員數
            member_count = await conn.fetchval(
                "SELECT COUNT(*) FROM project_members WHERE project_id = $1",
                UUID(project_id),
            )

            created_at_taipei = to_taipei_time(row['created_at'])
            return f"""專案：{row['name']}
狀態：{row['status']}
描述：{row['description'] or '無描述'}
成員數：{member_count}
里程碑：共 {milestone_stats['total']} 個，完成 {milestone_stats['completed']}，進行中 {milestone_stats['in_progress']}
建立時間：{created_at_taipei.strftime('%Y-%m-%d')}"""

        elif keyword:
            # 搜尋專案
            rows = await conn.fetch(
                """
                SELECT id, name, status, description
                FROM projects
                WHERE name ILIKE $1 OR description ILIKE $1
                ORDER BY updated_at DESC
                LIMIT 5
                """,
                f"%{keyword}%",
            )
            if not rows:
                return f"找不到包含「{keyword}」的專案"

            results = ["搜尋結果："]
            for row in rows:
                results.append(f"- {row['name']} ({row['status']}) [ID: {row['id']}]")
            return "\n".join(results)

        else:
            # 列出最近專案
            rows = await conn.fetch(
                """
                SELECT id, name, status
                FROM projects
                ORDER BY updated_at DESC
                LIMIT 5
                """
            )
            if not rows:
                return "目前沒有任何專案"

            results = ["最近的專案："]
            for row in rows:
                results.append(f"- {row['name']} ({row['status']}) [ID: {row['id']}]")
            return "\n".join(results)


@mcp.tool()
async def create_project(
    name: str,
    description: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """
    建立新專案

    Args:
        name: 專案名稱（必填）
        description: 專案描述
        start_date: 開始日期（格式：YYYY-MM-DD）
        end_date: 結束日期（格式：YYYY-MM-DD）
    """
    from datetime import date as date_type
    from ..models.project import ProjectCreate
    from .project import create_project as svc_create_project

    await ensure_db_connection()

    try:
        # 解析日期
        parsed_start = None
        parsed_end = None
        if start_date:
            parsed_start = date_type.fromisoformat(start_date)
        if end_date:
            parsed_end = date_type.fromisoformat(end_date)

        # 建立專案
        data = ProjectCreate(
            name=name,
            description=description,
            start_date=parsed_start,
            end_date=parsed_end,
        )
        result = await svc_create_project(data, created_by="linebot")

        return f"✅ 已建立專案「{result.name}」\n專案 ID：{result.id}"

    except Exception as e:
        logger.error(f"建立專案失敗: {e}")
        return f"建立專案失敗：{str(e)}"


@mcp.tool()
async def add_project_member(
    project_id: str,
    name: str,
    role: str | None = None,
    company: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    notes: str | None = None,
    is_internal: bool = True,
    ctos_user_id: int | None = None,
) -> str:
    """
    新增專案成員

    Args:
        project_id: 專案 UUID
        name: 成員姓名（必填）
        role: 角色/職稱
        company: 公司名稱（外部聯絡人適用）
        email: 電子郵件
        phone: 電話
        notes: 備註
        is_internal: 是否為內部人員，預設 True（外部聯絡人如客戶、廠商設為 False）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，內部人員自動綁定帳號）
    """
    from uuid import UUID as UUID_type
    from ..models.project import ProjectMemberCreate
    from .project import create_member as svc_create_member, ProjectNotFoundError

    await ensure_db_connection()

    try:
        # 準備 user_id：內部人員且有 ctos_user_id 時自動綁定
        user_id = ctos_user_id if is_internal and ctos_user_id else None

        # 檢查是否已有同名成員（避免重複新增）
        async with get_connection() as conn:
            existing = await conn.fetchrow(
                """
                SELECT id, user_id FROM project_members
                WHERE project_id = $1 AND name = $2
                """,
                UUID_type(project_id),
                name,
            )

        if existing:
            # 已有同名成員
            if existing["user_id"]:
                # 已經綁定，不需要重複新增
                return f"ℹ️ 專案中已有成員「{name}」（已綁定帳號）"
            elif user_id:
                # 未綁定但有 ctos_user_id，更新綁定
                async with get_connection() as conn:
                    await conn.execute(
                        "UPDATE project_members SET user_id = $1 WHERE id = $2",
                        user_id,
                        existing["id"],
                    )
                return f"✅ 已將「{name}」綁定到您的帳號"
            else:
                return f"ℹ️ 專案中已有成員「{name}」（尚未綁定帳號）"

        # 新增成員
        data = ProjectMemberCreate(
            name=name,
            role=role,
            company=company,
            email=email,
            phone=phone,
            notes=notes,
            is_internal=is_internal,
            user_id=user_id,
        )
        result = await svc_create_member(UUID_type(project_id), data)

        member_type = "內部人員" if result.is_internal else "外部聯絡人"
        role_str = f"（{result.role}）" if result.role else ""
        bound_str = "（已綁定帳號）" if user_id else ""
        return f"✅ 已新增{member_type}：{result.name}{role_str}{bound_str}"

    except ProjectNotFoundError:
        return f"找不到專案 ID: {project_id}"
    except Exception as e:
        logger.error(f"新增專案成員失敗: {e}")
        return f"新增專案成員失敗：{str(e)}"


@mcp.tool()
async def add_project_milestone(
    project_id: str,
    name: str,
    milestone_type: str = "custom",
    planned_date: str | None = None,
    actual_date: str | None = None,
    status: str = "pending",
    notes: str | None = None,
) -> str:
    """
    新增專案里程碑

    Args:
        project_id: 專案 UUID
        name: 里程碑名稱（必填）
        milestone_type: 類型，可選：design（設計）、manufacture（製造）、delivery（交貨）、field_test（現場測試）、acceptance（驗收）、custom（自訂），預設 custom
        planned_date: 預計日期（格式：YYYY-MM-DD）
        actual_date: 實際日期（格式：YYYY-MM-DD）
        status: 狀態，可選：pending（待處理）、in_progress（進行中）、completed（已完成）、delayed（延遲），預設 pending
        notes: 備註
    """
    from datetime import date as date_type
    from uuid import UUID as UUID_type
    from ..models.project import ProjectMilestoneCreate
    from .project import create_milestone as svc_create_milestone, ProjectNotFoundError

    await ensure_db_connection()

    try:
        # 解析日期
        parsed_planned = None
        parsed_actual = None
        if planned_date:
            parsed_planned = date_type.fromisoformat(planned_date)
        if actual_date:
            parsed_actual = date_type.fromisoformat(actual_date)

        data = ProjectMilestoneCreate(
            name=name,
            milestone_type=milestone_type,
            planned_date=parsed_planned,
            actual_date=parsed_actual,
            status=status,
            notes=notes,
        )
        result = await svc_create_milestone(UUID_type(project_id), data)

        status_emoji = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "delayed": "⚠️",
        }.get(result.status, "❓")

        date_str = f"，預計 {result.planned_date}" if result.planned_date else ""
        return f"✅ 已新增里程碑：{status_emoji} {result.name}{date_str}"

    except ProjectNotFoundError:
        return f"找不到專案 ID: {project_id}"
    except ValueError as e:
        return f"日期格式錯誤，請使用 YYYY-MM-DD 格式：{str(e)}"
    except Exception as e:
        logger.error(f"新增專案里程碑失敗: {e}")
        return f"新增專案里程碑失敗：{str(e)}"


@mcp.tool()
async def update_project(
    project_id: str,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    更新專案資訊

    Args:
        project_id: 專案 UUID
        name: 專案名稱
        description: 專案描述
        status: 專案狀態，可選：active（進行中）、completed（已完成）、on_hold（暫停）、cancelled（已取消）
        start_date: 開始日期（格式：YYYY-MM-DD）
        end_date: 結束日期（格式：YYYY-MM-DD）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    from datetime import date as date_type
    from uuid import UUID as UUID_type
    from ..models.project import ProjectUpdate
    from .project import update_project as svc_update_project, ProjectNotFoundError

    await ensure_db_connection()

    # 權限檢查：需要是專案成員才能更新
    if ctos_user_id is None:
        return "❌ 您的 Line 帳號尚未關聯 CTOS 用戶，無法進行專案更新操作。請聯繫管理員進行帳號關聯。"
    if not await check_project_member_permission(project_id, ctos_user_id):
        return "❌ 您不是此專案的成員，無法進行此操作。"

    try:
        # 解析日期
        parsed_start = date_type.fromisoformat(start_date) if start_date else None
        parsed_end = date_type.fromisoformat(end_date) if end_date else None

        data = ProjectUpdate(
            name=name,
            description=description,
            status=status,
            start_date=parsed_start,
            end_date=parsed_end,
        )
        result = await svc_update_project(UUID_type(project_id), data)

        updates = []
        if name:
            updates.append(f"名稱: {result.name}")
        if status:
            updates.append(f"狀態: {result.status}")
        if start_date:
            updates.append(f"開始日期: {result.start_date}")
        if end_date:
            updates.append(f"結束日期: {result.end_date}")

        update_str = "、".join(updates) if updates else "無變更"
        return f"✅ 已更新專案「{result.name}」：{update_str}"

    except ProjectNotFoundError:
        return f"找不到專案 ID: {project_id}"
    except ValueError as e:
        return f"日期格式錯誤，請使用 YYYY-MM-DD 格式：{str(e)}"
    except Exception as e:
        logger.error(f"更新專案失敗: {e}")
        return f"更新專案失敗：{str(e)}"


@mcp.tool()
async def update_milestone(
    milestone_id: str,
    project_id: str | None = None,
    name: str | None = None,
    milestone_type: str | None = None,
    planned_date: str | None = None,
    actual_date: str | None = None,
    status: str | None = None,
    notes: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    更新專案里程碑

    Args:
        milestone_id: 里程碑 UUID
        project_id: 專案 UUID（可選，如有提供會驗證里程碑是否屬於該專案）
        name: 里程碑名稱
        milestone_type: 類型，可選：design（設計）、manufacture（製造）、delivery（交貨）、field_test（現場測試）、acceptance（驗收）、custom（自訂）
        planned_date: 預計日期（格式：YYYY-MM-DD）
        actual_date: 實際日期（格式：YYYY-MM-DD）
        status: 狀態，可選：pending（待處理）、in_progress（進行中）、completed（已完成）、delayed（延遲）
        notes: 備註
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    from datetime import date as date_type
    from uuid import UUID as UUID_type
    from ..models.project import ProjectMilestoneUpdate
    from .project import update_milestone as svc_update_milestone, ProjectNotFoundError

    await ensure_db_connection()

    # 權限檢查前置：需要有 CTOS 用戶 ID
    if ctos_user_id is None:
        return "❌ 您的 Line 帳號尚未關聯 CTOS 用戶，無法進行專案更新操作。請聯繫管理員進行帳號關聯。"

    try:
        # 取得里程碑所屬專案
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT project_id FROM project_milestones WHERE id = $1",
                UUID_type(milestone_id),
            )
            if not row:
                return f"找不到里程碑 ID: {milestone_id}"
            actual_project_id = row["project_id"]

        # 權限檢查：需要是專案成員才能更新
        if not await check_project_member_permission(str(actual_project_id), ctos_user_id):
            return "❌ 您不是此專案的成員，無法進行此操作。"

        # 如果有提供 project_id，驗證是否匹配
        if project_id and UUID_type(project_id) != actual_project_id:
            return f"里程碑不屬於專案 {project_id}"

        # 解析日期
        parsed_planned = date_type.fromisoformat(planned_date) if planned_date else None
        parsed_actual = date_type.fromisoformat(actual_date) if actual_date else None

        data = ProjectMilestoneUpdate(
            name=name,
            milestone_type=milestone_type,
            planned_date=parsed_planned,
            actual_date=parsed_actual,
            status=status,
            notes=notes,
        )
        result = await svc_update_milestone(actual_project_id, UUID_type(milestone_id), data)

        status_emoji = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "delayed": "⚠️",
        }.get(result.status, "❓")

        return f"✅ 已更新里程碑：{status_emoji} {result.name}"

    except ProjectNotFoundError:
        return f"找不到里程碑 ID: {milestone_id}"
    except ValueError as e:
        return f"日期格式錯誤，請使用 YYYY-MM-DD 格式：{str(e)}"
    except Exception as e:
        logger.error(f"更新里程碑失敗: {e}")
        return f"更新里程碑失敗：{str(e)}"


@mcp.tool()
async def update_project_member(
    member_id: str,
    project_id: str | None = None,
    name: str | None = None,
    role: str | None = None,
    company: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    notes: str | None = None,
    is_internal: bool | None = None,
    ctos_user_id: int | None = None,
    bind_to_caller: bool = False,
) -> str:
    """
    更新專案成員資訊

    Args:
        member_id: 成員 UUID
        project_id: 專案 UUID（可選，如有提供會驗證成員是否屬於該專案）
        name: 成員姓名
        role: 角色/職稱
        company: 公司名稱
        email: 電子郵件
        phone: 電話
        notes: 備註
        is_internal: 是否為內部人員
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查和綁定）
        bind_to_caller: 是否將此成員綁定到呼叫者的 CTOS 帳號（設為 True 以綁定）
    """
    from uuid import UUID as UUID_type
    from ..models.project import ProjectMemberUpdate
    from .project import update_member as svc_update_member, ProjectNotFoundError

    await ensure_db_connection()

    # 權限檢查前置：需要有 CTOS 用戶 ID
    if ctos_user_id is None:
        return "❌ 您的 Line 帳號尚未關聯 CTOS 用戶，無法進行專案更新操作。請聯繫管理員進行帳號關聯。"

    try:
        # 取得成員所屬專案
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT project_id FROM project_members WHERE id = $1",
                UUID_type(member_id),
            )
            if not row:
                return f"找不到成員 ID: {member_id}"
            actual_project_id = row["project_id"]

        # 權限檢查：需要是專案成員才能更新
        if not await check_project_member_permission(str(actual_project_id), ctos_user_id):
            return "❌ 您不是此專案的成員，無法進行此操作。"

        # 如果有提供 project_id，驗證是否匹配
        if project_id and UUID_type(project_id) != actual_project_id:
            return f"成員不屬於專案 {project_id}"

        # 準備 user_id：若 bind_to_caller=True 則綁定到呼叫者
        user_id_to_set = ctos_user_id if bind_to_caller else None

        data = ProjectMemberUpdate(
            name=name,
            role=role,
            company=company,
            email=email,
            phone=phone,
            notes=notes,
            is_internal=is_internal,
            user_id=user_id_to_set,
        )
        result = await svc_update_member(actual_project_id, UUID_type(member_id), data)

        member_type = "內部人員" if result.is_internal else "外部聯絡人"
        bound_str = "（已綁定帳號）" if bind_to_caller else ""
        return f"✅ 已更新{member_type}：{result.name}{bound_str}"

    except ProjectNotFoundError:
        return f"找不到成員 ID: {member_id}"
    except Exception as e:
        logger.error(f"更新成員失敗: {e}")
        return f"更新成員失敗：{str(e)}"


@mcp.tool()
async def add_project_meeting(
    project_id: str,
    title: str,
    meeting_date: str | None = None,
    location: str | None = None,
    attendees: str | None = None,
    content: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    新增專案會議記錄

    Args:
        project_id: 專案 UUID
        title: 會議標題（必填）
        meeting_date: 會議日期時間（格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM），不填則使用當前時間
        location: 地點
        attendees: 參與者（逗號分隔）
        content: 會議內容（Markdown 格式）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    from uuid import UUID as UUID_type
    from ..models.project import ProjectMeetingCreate
    from .project import create_meeting as svc_create_meeting, ProjectNotFoundError

    await ensure_db_connection()

    # 權限檢查：需要是專案成員才能新增會議
    if ctos_user_id is None:
        return "❌ 您的 Line 帳號尚未關聯 CTOS 用戶，無法進行專案更新操作。請聯繫管理員進行帳號關聯。"
    if not await check_project_member_permission(project_id, ctos_user_id):
        return "❌ 您不是此專案的成員，無法進行此操作。"

    try:
        # 解析日期時間
        if meeting_date:
            # 支援兩種格式
            if " " in meeting_date or "T" in meeting_date:
                parsed_date = datetime.fromisoformat(meeting_date.replace(" ", "T"))
            else:
                parsed_date = datetime.fromisoformat(f"{meeting_date}T00:00:00")
        else:
            parsed_date = datetime.now()

        # 解析參與者
        attendees_list = [a.strip() for a in attendees.split(",")] if attendees else []

        data = ProjectMeetingCreate(
            title=title,
            meeting_date=parsed_date,
            location=location,
            attendees=attendees_list,
            content=content,
        )
        result = await svc_create_meeting(UUID_type(project_id), data)

        meeting_date_taipei = to_taipei_time(result.meeting_date)
        date_str = meeting_date_taipei.strftime("%Y-%m-%d %H:%M")
        return f"✅ 已新增會議：{result.title}（{date_str}）"

    except ProjectNotFoundError:
        return f"找不到專案 ID: {project_id}"
    except ValueError as e:
        return f"日期格式錯誤，請使用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM 格式：{str(e)}"
    except Exception as e:
        logger.error(f"新增會議失敗: {e}")
        return f"新增會議失敗：{str(e)}"


@mcp.tool()
async def update_project_meeting(
    meeting_id: str,
    project_id: str | None = None,
    title: str | None = None,
    meeting_date: str | None = None,
    location: str | None = None,
    attendees: str | None = None,
    content: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    更新專案會議記錄

    Args:
        meeting_id: 會議 UUID
        project_id: 專案 UUID（可選，如有提供會驗證會議是否屬於該專案）
        title: 會議標題
        meeting_date: 會議日期時間（格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM）
        location: 地點
        attendees: 參與者（逗號分隔）
        content: 會議內容（Markdown 格式）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    from uuid import UUID as UUID_type
    from ..models.project import ProjectMeetingUpdate
    from .project import update_meeting as svc_update_meeting, ProjectNotFoundError

    await ensure_db_connection()

    # 權限檢查前置：需要有 CTOS 用戶 ID
    if ctos_user_id is None:
        return "❌ 您的 Line 帳號尚未關聯 CTOS 用戶，無法進行專案更新操作。請聯繫管理員進行帳號關聯。"

    try:
        # 取得會議所屬專案
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT project_id FROM project_meetings WHERE id = $1",
                UUID_type(meeting_id),
            )
            if not row:
                return f"找不到會議 ID: {meeting_id}"
            actual_project_id = row["project_id"]

        # 權限檢查：需要是專案成員才能更新
        if not await check_project_member_permission(str(actual_project_id), ctos_user_id):
            return "❌ 您不是此專案的成員，無法進行此操作。"

        # 如果有提供 project_id，驗證是否匹配
        if project_id and UUID_type(project_id) != actual_project_id:
            return f"會議不屬於專案 {project_id}"

        # 解析日期時間
        parsed_date = None
        if meeting_date:
            if " " in meeting_date or "T" in meeting_date:
                parsed_date = datetime.fromisoformat(meeting_date.replace(" ", "T"))
            else:
                parsed_date = datetime.fromisoformat(f"{meeting_date}T00:00:00")

        # 解析參與者
        attendees_list = None
        if attendees is not None:
            attendees_list = [a.strip() for a in attendees.split(",")] if attendees else []

        data = ProjectMeetingUpdate(
            title=title,
            meeting_date=parsed_date,
            location=location,
            attendees=attendees_list,
            content=content,
        )
        result = await svc_update_meeting(actual_project_id, UUID_type(meeting_id), data)

        return f"✅ 已更新會議：{result.title}"

    except ProjectNotFoundError:
        return f"找不到會議 ID: {meeting_id}"
    except ValueError as e:
        return f"日期格式錯誤，請使用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM 格式：{str(e)}"
    except Exception as e:
        logger.error(f"更新會議失敗: {e}")
        return f"更新會議失敗：{str(e)}"


@mcp.tool()
async def get_project_milestones(
    project_id: str,
    status: str | None = None,
    limit: int = 10,
) -> str:
    """
    取得專案里程碑列表

    Args:
        project_id: 專案 UUID
        status: 狀態過濾，可選值：pending, in_progress, completed, delayed
        limit: 最大數量，預設 10
    """
    await ensure_db_connection()
    async with get_connection() as conn:
        query = """
            SELECT id, name, milestone_type, planned_date, actual_date, status, notes
            FROM project_milestones
            WHERE project_id = $1
        """
        params: list = [UUID(project_id)]

        if status:
            query += " AND status = $2"
            params.append(status)

        query += " ORDER BY sort_order, planned_date LIMIT $" + str(len(params) + 1)
        params.append(limit)

        rows = await conn.fetch(query, *params)

        if not rows:
            return "此專案目前沒有里程碑"

        # 取得專案名稱
        project = await conn.fetchrow(
            "SELECT name FROM projects WHERE id = $1",
            UUID(project_id),
        )
        project_name = project["name"] if project else "未知專案"

        # 格式化里程碑
        milestones = [f"【{project_name}】里程碑：\n"]
        for row in rows:
            status_emoji = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "delayed": "⚠️",
            }.get(row["status"], "❓")
            planned = row["planned_date"].strftime("%m/%d") if row["planned_date"] else "未排程"
            milestone_id = str(row["id"])
            milestones.append(f"{status_emoji} {row['name']} | 預計 {planned} | ID: {milestone_id}")

        return "\n".join(milestones)


@mcp.tool()
async def get_project_meetings(
    project_id: str,
    limit: int = 5,
) -> str:
    """
    取得專案會議記錄

    Args:
        project_id: 專案 UUID
        limit: 最大數量，預設 5
    """
    await ensure_db_connection()
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, meeting_date, location, attendees, content
            FROM project_meetings
            WHERE project_id = $1
            ORDER BY meeting_date DESC
            LIMIT $2
            """,
            UUID(project_id),
            limit,
        )

        if not rows:
            return "此專案目前沒有會議記錄"

        # 取得專案名稱
        project = await conn.fetchrow(
            "SELECT name FROM projects WHERE id = $1",
            UUID(project_id),
        )
        project_name = project["name"] if project else "未知專案"

        # 格式化會議記錄
        meetings = [f"【{project_name}】最近會議：\n"]
        for row in rows:
            meeting_date_taipei = to_taipei_time(row["meeting_date"])
            date_str = meeting_date_taipei.strftime("%Y-%m-%d %H:%M")
            attendees = ", ".join(row["attendees"]) if row["attendees"] else "無記錄"
            content_snippet = (row["content"] or "")[:100]
            if len(row["content"] or "") > 100:
                content_snippet += "..."
            meeting_id = str(row["id"])

            meetings.append(f"📅 {date_str} - {row['title']}")
            meetings.append(f"   地點：{row['location'] or '未指定'}")
            meetings.append(f"   參與者：{attendees}")
            if content_snippet:
                meetings.append(f"   內容：{content_snippet}")
            meetings.append(f"   ID: {meeting_id}")
            meetings.append("")

        return "\n".join(meetings)


@mcp.tool()
async def get_project_members(
    project_id: str,
    is_internal: bool | None = None,
) -> str:
    """
    取得專案成員與聯絡人

    Args:
        project_id: 專案 UUID
        is_internal: 篩選內部或外部人員，不指定則顯示全部
    """
    await ensure_db_connection()
    async with get_connection() as conn:
        query = """
            SELECT id, name, role, company, email, phone, is_internal
            FROM project_members
            WHERE project_id = $1
        """
        params: list = [UUID(project_id)]

        if is_internal is not None:
            query += " AND is_internal = $2"
            params.append(is_internal)

        query += " ORDER BY is_internal DESC, name"

        rows = await conn.fetch(query, *params)

        if not rows:
            return "此專案目前沒有成員"

        # 取得專案名稱
        project = await conn.fetchrow(
            "SELECT name FROM projects WHERE id = $1",
            UUID(project_id),
        )
        project_name = project["name"] if project else "未知專案"

        # 格式化成員
        members = [f"【{project_name}】成員/聯絡人：\n"]

        internal = [r for r in rows if r["is_internal"]]
        external = [r for r in rows if not r["is_internal"]]

        if internal:
            members.append("內部人員：")
            for row in internal:
                member_id = str(row["id"])
                members.append(f"  👤 {row['name']} - {row['role'] or '未指定角色'} | ID: {member_id}")

        if external:
            members.append("\n外部聯絡人：")
            for row in external:
                member_id = str(row["id"])
                info = f"  👤 {row['name']}"
                if row["company"]:
                    info += f" ({row['company']})"
                if row["role"]:
                    info += f" - {row['role']}"
                info += f" | ID: {member_id}"
                members.append(info)

        return "\n".join(members)


@mcp.tool()
async def search_knowledge(
    query: str,
    project: str | None = None,
    category: str | None = None,
    limit: int = 5,
) -> str:
    """
    搜尋知識庫

    Args:
        query: 搜尋關鍵字
        project: 專案過濾（如：專案 ID 或名稱）
        category: 分類過濾（如：technical, process, tool）
        limit: 最大結果數量，預設 5
    """
    from . import knowledge as kb_service

    try:
        result = kb_service.search_knowledge(
            query=query,
            project=project,
            category=category,
        )

        if not result.items:
            return f"找不到包含「{query}」的知識"

        # 格式化結果
        items = result.items[:limit]
        output = [f"搜尋「{query}」找到 {len(result.items)} 筆結果：\n"]

        for item in items:
            tags_str = ", ".join(item.tags.topics) if item.tags.topics else "無標籤"
            output.append(f"📄 [{item.id}] {item.title}")
            output.append(f"   分類：{item.category} | 標籤：{tags_str}")
            if item.snippet:
                # 截取片段
                snippet = item.snippet[:100] + "..." if len(item.snippet) > 100 else item.snippet
                output.append(f"   摘要：{snippet}")
            output.append("")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"搜尋知識庫失敗: {e}")
        return f"搜尋失敗：{str(e)}"


@mcp.tool()
async def get_knowledge_item(kb_id: str) -> str:
    """
    取得知識庫文件的完整內容

    Args:
        kb_id: 知識 ID（如 kb-001、kb-002）
    """
    from . import knowledge as kb_service
    from pathlib import Path

    try:
        item = kb_service.get_knowledge(kb_id)

        # 格式化輸出
        tags_str = ", ".join(item.tags.topics) if item.tags.topics else "無標籤"
        output = [
            f"📄 **[{item.id}] {item.title}**",
            f"分類：{item.category} | 標籤：{tags_str}",
            "",
            "---",
            "",
            item.content or "（無內容）",
        ]

        # 加入附件資訊
        if item.attachments:
            output.append("")
            output.append("---")
            output.append("")
            output.append(f"📎 **附件** ({len(item.attachments)} 個)")
            for idx, att in enumerate(item.attachments):
                filename = Path(att.path).name
                desc = f" - {att.description}" if att.description else ""
                output.append(f"  [{idx}] {att.type}: {filename}{desc}")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"取得知識失敗: {e}")
        return f"找不到知識 {kb_id}：{str(e)}"


@mcp.tool()
async def update_knowledge_item(
    kb_id: str,
    title: str | None = None,
    content: str | None = None,
    category: str | None = None,
    topics: list[str] | None = None,
    projects: list[str] | None = None,
    roles: list[str] | None = None,
    level: str | None = None,
    type: str | None = None,
) -> str:
    """
    更新知識庫文件

    Args:
        kb_id: 知識 ID（如 kb-001）
        title: 新標題（不填則不更新）
        content: 新內容（不填則不更新）
        category: 新分類（不填則不更新）
        topics: 主題標籤列表（不填則不更新）
        projects: 關聯專案列表（不填則不更新）
        roles: 適用角色列表（不填則不更新）
        level: 難度層級，如 beginner、intermediate、advanced（不填則不更新）
        type: 知識類型，如 note、spec、guide（不填則不更新）
    """
    from ..models.knowledge import KnowledgeUpdate, KnowledgeTags
    from . import knowledge as kb_service

    try:
        # 建立標籤更新資料（任一標籤欄位有值就建立 KnowledgeTags）
        tags = None
        if any([topics, projects, roles, level]):
            tags = KnowledgeTags(
                topics=topics or [],
                projects=projects or [],
                roles=roles or [],
                level=level,
            )

        # 建立更新資料
        update_data = KnowledgeUpdate(
            title=title,
            content=content,
            category=category,
            type=type,
            tags=tags,
        )

        item = kb_service.update_knowledge(kb_id, update_data)

        return f"✅ 已更新 [{item.id}] {item.title}"

    except Exception as e:
        logger.error(f"更新知識失敗: {e}")
        return f"更新失敗：{str(e)}"


@mcp.tool()
async def add_attachments_to_knowledge(
    kb_id: str,
    attachments: list[str],
    descriptions: list[str] | None = None,
) -> str:
    """
    為現有知識庫新增附件

    Args:
        kb_id: 知識 ID（如 kb-001）
        attachments: 附件的 NAS 路徑列表（從 get_message_attachments 取得）
        descriptions: 附件描述列表（與 attachments 一一對應，如「圖1 水切爐」）
    """
    from . import knowledge as kb_service

    # 限制附件數量
    if len(attachments) > 10:
        return "附件數量不能超過 10 個"

    # 確認知識存在
    try:
        knowledge = kb_service.get_knowledge(kb_id)
    except Exception:
        return f"找不到知識 {kb_id}"

    # 取得目前附件數量（用來計算新附件的 index）
    current_attachment_count = len(knowledge.attachments)

    # 處理附件
    success_count = 0
    failed_attachments = []
    added_descriptions = []

    for i, nas_path in enumerate(attachments):
        try:
            kb_service.copy_linebot_attachment_to_knowledge(kb_id, nas_path)
            success_count += 1

            # 如果有對應的描述，更新附件描述
            if descriptions and i < len(descriptions) and descriptions[i]:
                try:
                    new_index = current_attachment_count + success_count - 1
                    kb_service.update_attachment_description(kb_id, new_index, descriptions[i])
                    added_descriptions.append(descriptions[i])
                except Exception as e:
                    logger.warning(f"設定描述失敗 {descriptions[i]}: {e}")
        except Exception as e:
            logger.warning(f"附件複製失敗 {nas_path}: {e}")
            failed_attachments.append(nas_path)

    # 回傳結果
    if success_count == 0 and failed_attachments:
        return f"所有附件都無法加入：{', '.join(failed_attachments)}"

    output = [f"✅ 已為 {kb_id} 新增 {success_count} 個附件"]

    if added_descriptions:
        output.append(f"📝 已設定描述：{', '.join(added_descriptions)}")

    if failed_attachments:
        output.append(f"⚠️ 以下附件無法加入：")
        for path in failed_attachments:
            output.append(f"  - {path}")

    return "\n".join(output)


@mcp.tool()
async def delete_knowledge_item(kb_id: str) -> str:
    """
    刪除知識庫文件

    Args:
        kb_id: 知識 ID（如 kb-001）
    """
    from . import knowledge as kb_service

    try:
        kb_service.delete_knowledge(kb_id)
        return f"✅ 已刪除知識 {kb_id}"

    except Exception as e:
        logger.error(f"刪除知識失敗: {e}")
        return f"刪除失敗：{str(e)}"


@mcp.tool()
async def get_knowledge_attachments(kb_id: str) -> str:
    """
    取得知識庫的附件列表

    Args:
        kb_id: 知識 ID（如 kb-001、kb-002）
    """
    from . import knowledge as kb_service
    from pathlib import Path

    try:
        item = kb_service.get_knowledge(kb_id)

        if not item.attachments:
            return f"知識 {kb_id} 沒有附件"

        output = [f"📎 **{kb_id} 附件列表** ({len(item.attachments)} 個)\n"]

        for idx, att in enumerate(item.attachments):
            filename = Path(att.path).name
            output.append(f"[{idx}] {att.type}")
            output.append(f"    檔名：{filename}")
            if att.size:
                output.append(f"    大小：{att.size}")
            if att.description:
                output.append(f"    說明：{att.description}")
            else:
                output.append("    說明：（無）")
            output.append("")

        output.append("提示：使用 update_knowledge_attachment 更新附件說明")
        return "\n".join(output)

    except Exception as e:
        logger.error(f"取得附件列表失敗: {e}")
        return f"找不到知識 {kb_id}：{str(e)}"


@mcp.tool()
async def update_knowledge_attachment(
    kb_id: str,
    attachment_index: int,
    description: str | None = None,
) -> str:
    """
    更新知識庫附件的說明

    Args:
        kb_id: 知識 ID（如 kb-001）
        attachment_index: 附件索引（從 0 開始，可用 get_knowledge_attachments 查詢）
        description: 附件說明（如「圖1 水切爐畫面」）
    """
    from . import knowledge as kb_service
    from pathlib import Path

    try:
        attachment = kb_service.update_attachment(
            kb_id=kb_id,
            attachment_idx=attachment_index,
            description=description,
        )

        filename = Path(attachment.path).name
        desc = attachment.description or "（無）"
        return f"✅ 已更新 {kb_id} 附件 [{attachment_index}]\n檔名：{filename}\n說明：{desc}"

    except Exception as e:
        logger.error(f"更新附件失敗: {e}")
        return f"更新失敗：{str(e)}"


async def _determine_knowledge_scope(
    line_group_id: str | None,
    line_user_id: str | None,
    ctos_user_id: int | None,
) -> tuple[str, str | None, str | None]:
    """判斷知識庫的 scope 和相關屬性

    Args:
        line_group_id: Line 群組的內部 UUID
        line_user_id: Line 用戶 ID
        ctos_user_id: CTOS 用戶 ID

    Returns:
        tuple[scope, owner_username, project_id]
        - scope: "global", "personal", 或 "project"
        - owner_username: 擁有者帳號（scope=personal 時使用）
        - project_id: 專案 UUID（scope=project 時使用）
    """
    from uuid import UUID as UUID_type

    scope = "global"
    owner_username: str | None = None
    project_id: str | None = None

    # 1. 取得 CTOS 使用者名稱（如果有綁定）
    if ctos_user_id:
        async with get_connection() as conn:
            user_row = await conn.fetchrow(
                "SELECT username FROM users WHERE id = $1",
                ctos_user_id,
            )
            if user_row:
                owner_username = user_row["username"]

    # 2. 判斷對話來源並設定 scope
    if line_group_id:
        # 群組聊天：檢查群組是否綁定專案
        async with get_connection() as conn:
            group_row = await conn.fetchrow(
                "SELECT project_id FROM line_groups WHERE id = $1",
                UUID_type(line_group_id),
            )
            if group_row and group_row["project_id"]:
                # 群組已綁定專案 → scope=project
                scope = "project"
                project_id = str(group_row["project_id"])
            else:
                # 群組未綁定專案 → scope=global
                scope = "global"
    elif line_user_id and owner_username:
        # 個人聊天且已綁定帳號 → scope=personal
        scope = "personal"
    # 其他情況（未綁定帳號）→ scope=global（預設值）

    return scope, owner_username, project_id


@mcp.tool()
async def add_note(
    title: str,
    content: str,
    category: str = "note",
    topics: list[str] | None = None,
    project: str | None = None,
    line_group_id: str | None = None,
    line_user_id: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    新增筆記到知識庫

    Args:
        title: 筆記標題
        content: 筆記內容（Markdown 格式）
        category: 分類，預設 note（可選：technical, process, tool, note）
        topics: 主題標籤列表
        project: 關聯的專案名稱
        line_group_id: Line 群組的內部 UUID（從對話識別取得，群組對話時使用）
        line_user_id: Line 用戶 ID（從對話識別取得，個人對話時使用）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於判斷帳號綁定）
    """
    from ..models.knowledge import KnowledgeCreate, KnowledgeTags, KnowledgeSource
    from . import knowledge as kb_service

    try:
        await ensure_db_connection()

        # 自動判斷 scope 和相關屬性
        scope, owner_username, project_id = await _determine_knowledge_scope(
            line_group_id, line_user_id, ctos_user_id
        )

        # 建立標籤
        tags = KnowledgeTags(
            projects=[project] if project else [],
            roles=[],
            topics=topics or [],
            level=None,
        )

        # 建立來源（標記來自 Line Bot）
        source = KnowledgeSource(
            project=None,
            path="linebot",
            commit=None,
        )

        # 建立知識
        data = KnowledgeCreate(
            title=title,
            content=content,
            type="note",
            category=category,
            scope=scope,
            project_id=project_id,
            tags=tags,
            source=source,
            related=[],
            author=owner_username or "linebot",
        )

        result = kb_service.create_knowledge(data, owner=owner_username, project_id=project_id)

        # 組裝回應訊息
        scope_text = {"global": "全域", "personal": "個人", "project": "專案"}.get(scope, scope)
        return f"✅ 筆記已新增！\nID：{result.id}\n標題：{result.title}\n範圍：{scope_text}知識"

    except Exception as e:
        logger.error(f"新增筆記失敗: {e}")
        return f"新增筆記失敗：{str(e)}"


@mcp.tool()
async def add_note_with_attachments(
    title: str,
    content: str,
    attachments: list[str],
    category: str = "note",
    topics: list[str] | None = None,
    project: str | None = None,
    line_group_id: str | None = None,
    line_user_id: str | None = None,
    ctos_user_id: int | None = None,
) -> str:
    """
    新增筆記到知識庫並加入附件

    Args:
        title: 筆記標題
        content: 筆記內容（Markdown 格式）
        attachments: 附件的 NAS 路徑列表（從 get_message_attachments 取得）
        category: 分類，預設 note（可選：technical, process, tool, note）
        topics: 主題標籤列表
        project: 關聯的專案名稱
        line_group_id: Line 群組的內部 UUID（從對話識別取得，群組對話時使用）
        line_user_id: Line 用戶 ID（從對話識別取得，個人對話時使用）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於判斷帳號綁定）
    """
    from ..models.knowledge import KnowledgeCreate, KnowledgeTags, KnowledgeSource
    from . import knowledge as kb_service

    # 限制附件數量
    if len(attachments) > 10:
        return "附件數量不能超過 10 個"

    try:
        await ensure_db_connection()

        # 自動判斷 scope 和相關屬性
        scope, owner_username, knowledge_project_id = await _determine_knowledge_scope(
            line_group_id, line_user_id, ctos_user_id
        )

        # 建立知識庫筆記
        tags = KnowledgeTags(
            projects=[project] if project else [],
            roles=[],
            topics=topics or [],
            level=None,
        )

        source = KnowledgeSource(
            project=None,
            path="linebot",
            commit=None,
        )

        data = KnowledgeCreate(
            title=title,
            content=content,
            type="note",
            category=category,
            scope=scope,
            project_id=knowledge_project_id,
            tags=tags,
            source=source,
            related=[],
            author=owner_username or "linebot",
        )

        result = kb_service.create_knowledge(data, owner=owner_username, project_id=knowledge_project_id)
        kb_id = result.id

        # 2. 處理附件
        success_count = 0
        failed_attachments = []

        for nas_path in attachments:
            try:
                kb_service.copy_linebot_attachment_to_knowledge(kb_id, nas_path)
                success_count += 1
            except Exception as e:
                logger.warning(f"附件複製失敗 {nas_path}: {e}")
                failed_attachments.append(nas_path)

        # 3. 回傳結果
        scope_text = {"global": "全域", "personal": "個人", "project": "專案"}.get(scope, scope)
        output = [f"✅ 筆記已新增！", f"ID：{kb_id}", f"標題：{title}", f"範圍：{scope_text}知識"]

        if success_count > 0:
            output.append(f"附件：已加入 {success_count} 個")

        if failed_attachments:
            output.append(f"⚠️ 以下附件無法加入：")
            for path in failed_attachments:
                output.append(f"  - {path}")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"新增筆記失敗: {e}")
        return f"新增筆記失敗：{str(e)}"


@mcp.tool()
async def summarize_chat(
    line_group_id: str,
    hours: int = 24,
    max_messages: int = 50,
) -> str:
    """
    取得 Line 群組聊天記錄，供 AI 摘要使用

    Args:
        line_group_id: Line 群組的內部 UUID
        hours: 取得最近幾小時的訊息，預設 24
        max_messages: 最大訊息數量，預設 50
    """
    await ensure_db_connection()
    async with get_connection() as conn:
        # 計算時間範圍
        since = datetime.now() - timedelta(hours=hours)

        # 取得訊息
        rows = await conn.fetch(
            """
            SELECT m.content, m.created_at, m.message_type,
                   u.display_name as user_name
            FROM line_messages m
            LEFT JOIN line_users u ON m.line_user_id = u.id
            WHERE m.line_group_id = $1
              AND m.created_at >= $2
              AND m.message_type = 'text'
              AND m.content IS NOT NULL
            ORDER BY m.created_at ASC
            LIMIT $3
            """,
            UUID(line_group_id),
            since,
            max_messages,
        )

        if not rows:
            return f"過去 {hours} 小時內沒有文字訊息"

        # 取得群組名稱
        group = await conn.fetchrow(
            "SELECT name FROM line_groups WHERE id = $1",
            UUID(line_group_id),
        )
        group_name = group["name"] if group else "未知群組"

        # 格式化訊息
        messages = [f"【{group_name}】過去 {hours} 小時的聊天記錄（共 {len(rows)} 則）：\n"]
        for row in rows:
            created_at_taipei = to_taipei_time(row["created_at"])
            time_str = created_at_taipei.strftime("%H:%M")
            user = row["user_name"] or "未知用戶"
            messages.append(f"[{time_str}] {user}: {row['content']}")

        return "\n".join(messages)


@mcp.tool()
async def get_message_attachments(
    line_user_id: str | None = None,
    line_group_id: str | None = None,
    days: int = 7,
    file_type: str | None = None,
    limit: int = 20,
) -> str:
    """
    查詢對話中的附件（圖片、檔案等），用於將附件加入知識庫

    Args:
        line_user_id: Line 用戶 ID（個人聊天時使用）
        line_group_id: Line 群組的內部 UUID
        days: 查詢最近幾天的附件，預設 7 天，可根據用戶描述調整
        file_type: 檔案類型過濾（image, file, video, audio），不填則查詢全部
        limit: 最大回傳數量，預設 20
    """
    await ensure_db_connection()

    if not line_user_id and not line_group_id:
        return "請提供 line_user_id 或 line_group_id"

    async with get_connection() as conn:
        # 計算時間範圍
        since = datetime.now() - timedelta(days=days)

        # 建立查詢條件
        conditions = ["m.created_at >= $1"]
        params: list = [since]
        param_idx = 2

        if line_group_id:
            conditions.append(f"m.line_group_id = ${param_idx}")
            params.append(UUID(line_group_id))
            param_idx += 1
        elif line_user_id:
            # 個人聊天：查詢該用戶的訊息且不在群組中
            conditions.append(f"u.line_user_id = ${param_idx}")
            params.append(line_user_id)
            param_idx += 1
            conditions.append("m.line_group_id IS NULL")

        if file_type:
            conditions.append(f"f.file_type = ${param_idx}")
            params.append(file_type)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # 查詢附件
        rows = await conn.fetch(
            f"""
            SELECT f.id, f.file_type, f.file_name, f.file_size, f.nas_path,
                   f.created_at, u.display_name as user_name
            FROM line_files f
            JOIN line_messages m ON f.message_id = m.id
            LEFT JOIN line_users u ON m.line_user_id = u.id
            WHERE {where_clause}
              AND f.nas_path IS NOT NULL
            ORDER BY f.created_at DESC
            LIMIT {limit}
            """,
            *params,
        )

        if not rows:
            type_hint = f"（類型：{file_type}）" if file_type else ""
            return f"最近 {days} 天內沒有找到附件{type_hint}"

        # 格式化結果
        type_names = {
            "image": "圖片",
            "file": "檔案",
            "video": "影片",
            "audio": "音訊",
        }

        output = [f"找到 {len(rows)} 個附件（最近 {days} 天）：\n"]
        for i, row in enumerate(rows, 1):
            type_name = type_names.get(row["file_type"], row["file_type"])
            created_at_taipei = to_taipei_time(row["created_at"])
            time_str = created_at_taipei.strftime("%Y-%m-%d %H:%M")
            user = row["user_name"] or "未知用戶"

            output.append(f"{i}. [{type_name}] {time_str} - {user}")
            output.append(f"   NAS 路徑：{row['nas_path']}")

            if row["file_name"]:
                output.append(f"   檔名：{row['file_name']}")
            if row["file_size"]:
                size_kb = row["file_size"] / 1024
                if size_kb >= 1024:
                    output.append(f"   大小：{size_kb / 1024:.1f} MB")
                else:
                    output.append(f"   大小：{size_kb:.1f} KB")
            output.append("")

        output.append("提示：使用 NAS 路徑作為 add_note_with_attachments 的 attachments 參數")

        return "\n".join(output)


@mcp.tool()
async def search_nas_files(
    keywords: str,
    file_types: str | None = None,
    limit: int = 100,
) -> str:
    """
    搜尋 NAS 共享檔案

    Args:
        keywords: 搜尋關鍵字，多個關鍵字用逗號分隔（AND 匹配，大小寫不敏感）
        file_types: 檔案類型過濾，多個類型用逗號分隔（如：pdf,xlsx,dwg）
        limit: 最大回傳數量，預設 100
    """
    from pathlib import Path
    from ..config import settings

    # 取得專案掛載點路徑
    projects_path = Path(settings.projects_mount_path)

    if not projects_path.exists():
        return f"錯誤：掛載點 {settings.projects_mount_path} 不存在或未掛載"

    # 解析關鍵字（大小寫不敏感）
    keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    if not keyword_list:
        return "錯誤：請提供至少一個關鍵字"

    # 解析檔案類型
    type_list = []
    if file_types:
        type_list = [t.strip().lower().lstrip(".") for t in file_types.split(",") if t.strip()]

    # 搜尋檔案
    matched_files = []
    try:
        for file_path in projects_path.rglob("*"):
            if not file_path.is_file():
                continue

            # 取得相對路徑（用於匹配和顯示）
            rel_path = file_path.relative_to(projects_path)
            rel_path_str = str(rel_path)
            rel_path_lower = rel_path_str.lower()

            # 關鍵字匹配（所有關鍵字都要匹配路徑）
            if not all(kw in rel_path_lower for kw in keyword_list):
                continue

            # 檔案類型匹配
            if type_list:
                suffix = file_path.suffix.lower().lstrip(".")
                if suffix not in type_list:
                    continue

            # 取得檔案資訊
            try:
                stat = file_path.stat()
                size = stat.st_size
                modified = datetime.fromtimestamp(stat.st_mtime)
            except OSError:
                size = 0
                modified = None

            matched_files.append({
                "path": f"/{rel_path_str}",
                "name": file_path.name,
                "size": size,
                "modified": modified,
            })

            if len(matched_files) >= limit:
                break

    except PermissionError:
        return "錯誤：沒有權限存取檔案系統"
    except Exception as e:
        return f"搜尋時發生錯誤：{str(e)}"

    if not matched_files:
        type_hint = f"（類型：{file_types}）" if file_types else ""
        return f"找不到符合「{keywords}」的檔案{type_hint}"

    # 格式化輸出
    output = [f"找到 {len(matched_files)} 個檔案：\n"]
    for f in matched_files:
        size_str = ""
        if f["size"]:
            if f["size"] >= 1024 * 1024:
                size_str = f" ({f['size'] / 1024 / 1024:.1f} MB)"
            elif f["size"] >= 1024:
                size_str = f" ({f['size'] / 1024:.1f} KB)"

        output.append(f"📄 {f['path']}{size_str}")

    if len(matched_files) >= limit:
        output.append(f"\n（已達上限 {limit} 筆，可能還有更多結果）")

    output.append("\n提示：使用 get_nas_file_info 取得詳細資訊，或 create_share_link 產生下載連結")
    return "\n".join(output)


@mcp.tool()
async def get_nas_file_info(file_path: str) -> str:
    """
    取得 NAS 檔案詳細資訊

    Args:
        file_path: 檔案路徑（相對於 /mnt/nas/projects 或完整路徑）
    """
    from pathlib import Path
    from ..config import settings

    projects_path = Path(settings.projects_mount_path)

    # 正規化路徑
    if file_path.startswith(settings.projects_mount_path):
        # 完整路徑
        full_path = Path(file_path)
    else:
        # 相對路徑（移除開頭的 /）
        rel_path = file_path.lstrip("/")
        full_path = projects_path / rel_path

    # 安全檢查：確保路徑在允許範圍內
    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(projects_path.resolve())):
            return "錯誤：不允許存取此路徑"
    except Exception:
        return "錯誤：無效的路徑"

    if not full_path.exists():
        return f"錯誤：檔案不存在 - {file_path}"

    if not full_path.is_file():
        return f"錯誤：路徑不是檔案 - {file_path}"

    # 取得檔案資訊
    try:
        stat = full_path.stat()
        size = stat.st_size
        modified = datetime.fromtimestamp(stat.st_mtime)
        rel_path = full_path.relative_to(projects_path)
    except OSError as e:
        return f"錯誤：無法讀取檔案資訊 - {e}"

    # 格式化大小
    if size >= 1024 * 1024:
        size_str = f"{size / 1024 / 1024:.2f} MB"
    elif size >= 1024:
        size_str = f"{size / 1024:.2f} KB"
    else:
        size_str = f"{size} bytes"

    # 判斷檔案類型
    suffix = full_path.suffix.lower()
    type_map = {
        ".pdf": "PDF 文件",
        ".doc": "Word 文件",
        ".docx": "Word 文件",
        ".xls": "Excel 試算表",
        ".xlsx": "Excel 試算表",
        ".ppt": "PowerPoint 簡報",
        ".pptx": "PowerPoint 簡報",
        ".png": "PNG 圖片",
        ".jpg": "JPEG 圖片",
        ".jpeg": "JPEG 圖片",
        ".gif": "GIF 圖片",
        ".dwg": "AutoCAD 圖檔",
        ".dxf": "AutoCAD 交換檔",
        ".zip": "ZIP 壓縮檔",
        ".rar": "RAR 壓縮檔",
        ".txt": "文字檔",
        ".csv": "CSV 檔案",
    }
    file_type = type_map.get(suffix, f"{suffix} 檔案")

    return f"""📄 **{full_path.name}**

類型：{file_type}
大小：{size_str}
修改時間：{modified.strftime('%Y-%m-%d %H:%M:%S')}
完整路徑：{str(full_path)}

可用操作：
- create_share_link(resource_type="nas_file", resource_id="{str(full_path)}") 產生下載連結
- read_document(file_path="{str(full_path)}") 讀取文件內容（Word/Excel/PowerPoint/PDF）"""


@mcp.tool()
async def read_document(
    file_path: str,
    max_chars: int = 50000,
) -> str:
    """
    讀取文件內容（支援 Word、Excel、PowerPoint、PDF）

    將文件轉換為純文字，讓 AI 可以分析、總結或查詢內容。

    Args:
        file_path: NAS 檔案路徑（nas:// 格式、相對路徑或完整路徑）
        max_chars: 最大字元數限制，預設 50000
    """
    from pathlib import Path
    from ..config import settings
    from . import document_reader

    projects_path = Path(settings.projects_mount_path)
    ctos_path = Path(settings.ctos_mount_path)
    nas_path = Path(settings.nas_mount_path)

    # 正規化路徑
    if file_path.startswith("nas://"):
        # nas://linebot/files/... -> /mnt/nas/ctos/linebot/files/...
        # nas://projects/attachments/... -> /mnt/nas/ctos/projects/attachments/...
        nas_relative = file_path[6:]  # 移除 "nas://"
        full_path = ctos_path / nas_relative
    elif file_path.startswith(settings.ctos_mount_path):
        # ctos 完整路徑
        full_path = Path(file_path)
    elif file_path.startswith(settings.projects_mount_path):
        # projects 完整路徑
        full_path = Path(file_path)
    else:
        # 相對路徑（移除開頭的 /）- 預設在 projects 目錄下
        rel_path = file_path.lstrip("/")
        full_path = projects_path / rel_path

    # 安全檢查：確保路徑在允許範圍內（/mnt/nas/ 下）
    try:
        full_path = full_path.resolve()
        resolved_nas = str(nas_path.resolve())
        if not str(full_path).startswith(resolved_nas):
            return "錯誤：不允許存取此路徑"
    except Exception:
        return "錯誤：無效的路徑"

    if not full_path.exists():
        return f"錯誤：檔案不存在 - {file_path}"

    if not full_path.is_file():
        return f"錯誤：路徑不是檔案 - {file_path}"

    # 檢查是否為支援的文件格式
    suffix = full_path.suffix.lower()
    if suffix not in document_reader.SUPPORTED_EXTENSIONS:
        if suffix in document_reader.LEGACY_EXTENSIONS:
            return f"錯誤：不支援舊版格式 {suffix}，請轉存為新版格式（.docx/.xlsx/.pptx）"
        return f"錯誤：不支援的檔案格式 {suffix}。支援的格式：{', '.join(document_reader.SUPPORTED_EXTENSIONS)}"

    # 解析文件
    try:
        result = document_reader.extract_text(str(full_path))

        # 截斷過長的內容
        text = result.text
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[內容已截斷，原文共 {len(text)} 字元]"

        # 建立回應
        response = f"📄 **{full_path.name}**\n"
        response += f"格式：{result.format.upper()}\n"
        if result.page_count:
            label = "工作表數" if result.format == "xlsx" else "頁數"
            response += f"{label}：{result.page_count}\n"
        if result.truncated:
            response += "⚠️ 內容已截斷\n"
        if result.error:
            response += f"⚠️ 注意：{result.error}\n"
        response += "\n---\n\n"
        response += text

        return response

    except document_reader.FileTooLargeError as e:
        return f"錯誤：{e}"
    except document_reader.PasswordProtectedError:
        return "錯誤：此文件有密碼保護，無法讀取"
    except document_reader.CorruptedFileError as e:
        return f"錯誤：文件損壞 - {e}"
    except document_reader.UnsupportedFormatError as e:
        return f"錯誤：{e}"
    except Exception as e:
        logger.error(f"read_document 錯誤: {e}")
        return f"錯誤：讀取文件失敗 - {e}"


@mcp.tool()
async def create_share_link(
    resource_type: str,
    resource_id: str,
    expires_in: str | None = "24h",
) -> str:
    """
    建立公開分享連結，讓沒有帳號的人也能查看知識庫、專案或下載檔案

    Args:
        resource_type: 資源類型，可選：
            - knowledge: 知識庫
            - project: 專案
            - nas_file: NAS 檔案（路徑）
            - project_attachment: 專案附件（附件 UUID）
        resource_id: 資源 ID（如 kb-001、專案 UUID、NAS 路徑或附件 UUID）
        expires_in: 有效期限，可選 1h、24h、7d、null（永久），預設 24h
    """
    await ensure_db_connection()

    from .share import (
        create_share_link as _create_share_link,
        ShareError,
        ResourceNotFoundError,
    )
    from ..models.share import ShareLinkCreate

    # 驗證資源類型
    valid_types = ("knowledge", "project", "nas_file", "project_attachment")
    if resource_type not in valid_types:
        return f"錯誤：資源類型必須是 {', '.join(valid_types)}，收到：{resource_type}"

    # 驗證有效期限
    valid_expires = {"1h", "24h", "7d", "null", None}
    if expires_in not in valid_expires:
        return f"錯誤：有效期限必須是 1h、24h、7d 或 null（永久），收到：{expires_in}"

    try:
        data = ShareLinkCreate(
            resource_type=resource_type,
            resource_id=resource_id,
            expires_in=expires_in,
        )
        # 使用 system 作為建立者（Line Bot 代理建立）
        result = await _create_share_link(data, "linebot")

        # 轉換為台北時區顯示
        if result.expires_at:
            expires_taipei = to_taipei_time(result.expires_at)
            expires_text = f"有效至 {expires_taipei.strftime('%Y-%m-%d %H:%M')}"
        else:
            expires_text = "永久有效"

        return f"""分享連結已建立！

📎 連結：{result.full_url}
📄 資源：{result.resource_title}
⏰ {expires_text}

可以直接把連結傳給需要查看的人。"""

    except ResourceNotFoundError as e:
        return f"錯誤：找不到資源 - {e}"
    except ShareError as e:
        return f"錯誤：{e}"
    except Exception as e:
        return f"建立分享連結時發生錯誤：{e}"


@mcp.tool()
async def send_nas_file(
    file_path: str,
    line_user_id: str | None = None,
    line_group_id: str | None = None,
) -> str:
    """
    直接發送 NAS 檔案給用戶。圖片會直接顯示在對話中，其他檔案會發送下載連結。

    Args:
        file_path: NAS 檔案的完整路徑（從 search_nas_files 取得）
        line_user_id: Line 用戶 ID（個人對話時使用，從【對話識別】取得）
        line_group_id: Line 群組的內部 UUID（群組對話時使用，從【對話識別】取得）

    注意：
    - 圖片（jpg/jpeg/png/gif/webp）< 10MB 會直接顯示
    - 其他檔案會發送下載連結
    - 必須提供 line_user_id 或 line_group_id 其中之一
    """
    await ensure_db_connection()

    from pathlib import Path
    from .share import (
        create_share_link as _create_share_link,
        validate_nas_file_path,
        ShareError,
        NasFileNotFoundError,
        NasFileAccessDenied,
    )
    from ..models.share import ShareLinkCreate
    from .linebot import push_image, push_text

    # 驗證必要參數
    if not line_user_id and not line_group_id:
        return "錯誤：請從【對話識別】區塊取得 line_user_id 或 line_group_id"

    # 驗證檔案路徑
    try:
        full_path = validate_nas_file_path(file_path)
    except NasFileNotFoundError as e:
        return f"錯誤：{e}"
    except NasFileAccessDenied as e:
        return f"錯誤：{e}"

    # 取得檔案資訊
    file_name = full_path.name
    file_size = full_path.stat().st_size
    file_ext = full_path.suffix.lower().lstrip(".")

    # 判斷是否為圖片
    image_extensions = {"jpg", "jpeg", "png", "gif", "webp"}
    is_image = file_ext in image_extensions

    # Line ImageMessage 限制 10MB
    max_image_size = 10 * 1024 * 1024

    # 產生分享連結
    try:
        data = ShareLinkCreate(
            resource_type="nas_file",
            resource_id=file_path,
            expires_in="24h",
        )
        result = await _create_share_link(data, "linebot")
    except Exception as e:
        return f"建立分享連結失敗：{e}"

    # 決定發送目標（優先使用群組 ID）
    # line_group_id 是內部 UUID，需要轉換為 Line group ID
    target_id = None
    if line_group_id:
        # 查詢 Line group ID
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT line_group_id FROM line_groups WHERE id = $1",
                UUID(line_group_id),
            )
            if row:
                target_id = row["line_group_id"]
            else:
                return f"錯誤：找不到群組 {line_group_id}"
    elif line_user_id:
        target_id = line_user_id

    if not target_id:
        return "錯誤：無法確定發送目標"

    # 發送訊息
    try:
        if is_image and file_size <= max_image_size:
            # 小圖片：直接發送 ImageMessage
            # 下載連結需要加上 /download
            download_url = result.full_url.replace("/s/", "/api/public/") + "/download"
            message_id, error = await push_image(target_id, download_url)
            if message_id:
                return f"已發送圖片：{file_name}"
            else:
                # 發送圖片失敗，fallback 到連結
                fallback_msg = f"📎 {file_name}\n{result.full_url}\n⏰ 連結 24 小時內有效"
                fallback_id, fallback_error = await push_text(target_id, fallback_msg)
                if fallback_id:
                    return f"圖片發送失敗（{error}），已改發連結：{file_name}"
                else:
                    # 連結也發不出去，回傳連結讓 AI 在回覆中告訴用戶
                    return f"無法直接發送（{fallback_error}），以下是下載連結：\n{result.full_url}\n（24 小時內有效）"
        else:
            # 其他檔案或大圖片：發送連結
            size_str = f"{file_size / 1024 / 1024:.1f}MB" if file_size >= 1024 * 1024 else f"{file_size / 1024:.1f}KB"
            message = f"📎 {file_name}（{size_str}）\n{result.full_url}\n⏰ 連結 24 小時內有效"
            message_id, error = await push_text(target_id, message)
            if message_id:
                return f"已發送檔案連結：{file_name}"
            else:
                # 發送失敗，回傳連結讓 AI 在回覆中告訴用戶
                return f"無法直接發送（{error}），以下是下載連結：\n{result.full_url}\n（24 小時內有效）"
    except Exception as e:
        return f"發送訊息失敗：{e}，連結：{result.full_url}"


@mcp.tool()
async def prepare_file_message(
    file_path: str,
) -> str:
    """
    準備檔案訊息供 Line Bot 回覆。圖片會直接顯示在回覆中，其他檔案會以連結形式呈現。

    Args:
        file_path: NAS 檔案的完整路徑（從 search_nas_files 取得）

    Returns:
        包含檔案訊息標記的字串，系統會自動處理並在回覆中顯示圖片或連結
    """
    await ensure_db_connection()

    import json
    from pathlib import Path
    from .share import (
        create_share_link as _create_share_link,
        validate_nas_file_path,
        ShareError,
        NasFileNotFoundError,
        NasFileAccessDenied,
    )
    from ..models.share import ShareLinkCreate

    # 驗證檔案路徑
    try:
        full_path = validate_nas_file_path(file_path)
    except NasFileNotFoundError as e:
        return f"錯誤：{e}"
    except NasFileAccessDenied as e:
        return f"錯誤：{e}"

    # 取得檔案資訊
    file_name = full_path.name
    file_size = full_path.stat().st_size
    file_ext = full_path.suffix.lower().lstrip(".")

    # 格式化檔案大小
    if file_size >= 1024 * 1024:
        size_str = f"{file_size / 1024 / 1024:.1f}MB"
    else:
        size_str = f"{file_size / 1024:.1f}KB"

    # 判斷是否為圖片（Line ImageMessage 支援的格式）
    image_extensions = {"jpg", "jpeg", "png", "gif", "webp"}
    is_image = file_ext in image_extensions

    # Line ImageMessage 限制 10MB
    max_image_size = 10 * 1024 * 1024

    # 產生分享連結
    try:
        data = ShareLinkCreate(
            resource_type="nas_file",
            resource_id=file_path,
            expires_in="24h",
        )
        result = await _create_share_link(data, "linebot")
    except Exception as e:
        return f"建立分享連結失敗：{e}"

    # 下載連結需要加上 /download
    download_url = result.full_url.replace("/s/", "/api/public/") + "/download"

    # 計算相對於 linebot_local_path 的路徑（用於存 line_files）
    # full_path: /mnt/nas/ctos/linebot/files/ai-images/xxx.jpg
    # linebot_local_path: /mnt/nas/ctos/linebot/files
    # relative_nas_path: ai-images/xxx.jpg
    from ..config import settings
    linebot_base = settings.linebot_local_path
    full_path_str = str(full_path)
    if full_path_str.startswith(linebot_base):
        relative_nas_path = full_path_str[len(linebot_base):].lstrip("/")
    else:
        relative_nas_path = full_path_str  # 其他路徑保持原樣

    # 組合檔案訊息標記
    if is_image and file_size <= max_image_size:
        # 小圖片：標記為 image 類型
        file_info = {
            "type": "image",
            "url": download_url,
            "name": file_name,
            "nas_path": relative_nas_path,  # 相對路徑，用於 line_files 存儲
        }
        hint = f"已準備好圖片 {file_name}，會顯示在回覆中"
    else:
        # 其他檔案或大圖片：標記為 file 類型
        file_info = {
            "type": "file",
            "url": result.full_url,
            "name": file_name,
            "size": size_str,
            "nas_path": relative_nas_path,  # 相對路徑，用於 line_files 存儲
        }
        hint = f"已準備好檔案 {file_name}（{size_str}），會以連結形式顯示"

    # 回傳標記（linebot_ai.py 會解析這個標記）
    marker = f"[FILE_MESSAGE:{json.dumps(file_info, ensure_ascii=False)}]"

    return f"{hint}\n{marker}"


# ============================================
# 專案發包/交貨期程管理
# ============================================


@mcp.tool()
async def add_delivery_schedule(
    project_id: str,
    vendor: str,
    item: str,
    quantity: str | None = None,
    order_date: str | None = None,
    expected_delivery_date: str | None = None,
    status: str = "pending",
    notes: str | None = None,
) -> str:
    """
    新增專案發包/交貨記錄

    Args:
        project_id: 專案 UUID
        vendor: 廠商名稱（必填）
        item: 料件名稱（必填）
        quantity: 數量（含單位，如「2 台」）
        order_date: 發包日期（格式:YYYY-MM-DD）
        expected_delivery_date: 預計交貨日期（格式:YYYY-MM-DD）
        status: 狀態，可選:pending(待發包)、ordered(已發包)、delivered(已到貨)、completed(已完成)，預設 pending
        notes: 備註
    """
    await ensure_db_connection()
    from datetime import date

    # 驗證專案存在
    async with get_connection() as conn:
        project = await conn.fetchrow(
            "SELECT id, name FROM projects WHERE id = $1",
            project_id,
        )
        if not project:
            return f"錯誤：找不到專案 {project_id}"

        # 解析日期
        parsed_order_date = None
        parsed_expected_date = None

        if order_date:
            try:
                parsed_order_date = date.fromisoformat(order_date)
            except ValueError:
                return f"錯誤：發包日期格式錯誤，請使用 YYYY-MM-DD 格式"

        if expected_delivery_date:
            try:
                parsed_expected_date = date.fromisoformat(expected_delivery_date)
            except ValueError:
                return f"錯誤：預計交貨日期格式錯誤，請使用 YYYY-MM-DD 格式"

        # 驗證狀態
        valid_statuses = ["pending", "ordered", "delivered", "completed"]
        if status not in valid_statuses:
            return f"錯誤：狀態必須是 {', '.join(valid_statuses)} 其中之一"

        # 新增記錄
        row = await conn.fetchrow(
            """
            INSERT INTO project_delivery_schedules
                (project_id, vendor, item, quantity, order_date, expected_delivery_date, status, notes, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'AI')
            RETURNING id, vendor, item
            """,
            project_id,
            vendor,
            item,
            quantity,
            parsed_order_date,
            parsed_expected_date,
            status,
            notes,
        )

        status_names = {
            "pending": "待發包",
            "ordered": "已發包",
            "delivered": "已到貨",
            "completed": "已完成",
        }
        status_display = status_names.get(status, status)

        result = f"✅ 已新增發包記錄\n"
        result += f"- 專案：{project['name']}\n"
        result += f"- 廠商：{vendor}\n"
        result += f"- 料件：{item}\n"
        if quantity:
            result += f"- 數量：{quantity}\n"
        if parsed_order_date:
            result += f"- 發包日：{parsed_order_date}\n"
        if parsed_expected_date:
            result += f"- 預計交貨：{parsed_expected_date}\n"
        result += f"- 狀態：{status_display}"

        return result


@mcp.tool()
async def update_delivery_schedule(
    project_id: str,
    delivery_id: str | None = None,
    vendor: str | None = None,
    item: str | None = None,
    new_vendor: str | None = None,
    new_item: str | None = None,
    new_quantity: str | None = None,
    new_status: str | None = None,
    order_date: str | None = None,
    actual_delivery_date: str | None = None,
    expected_delivery_date: str | None = None,
    new_notes: str | None = None,
) -> str:
    """
    更新專案發包/交貨記錄

    Args:
        project_id: 專案 UUID
        delivery_id: 發包記錄 UUID（直接指定）
        vendor: 廠商名稱（用於匹配記錄）
        item: 料件名稱（用於匹配記錄）
        new_vendor: 更新廠商名稱
        new_item: 更新料件名稱
        new_quantity: 更新數量（如「2 台」）
        new_status: 新狀態，可選:pending(待發包)、ordered(已發包)、delivered(已到貨)、completed(已完成)
        order_date: 更新發包日期（格式:YYYY-MM-DD）
        actual_delivery_date: 實際到貨日期（格式:YYYY-MM-DD）
        expected_delivery_date: 更新預計交貨日期（格式:YYYY-MM-DD）
        new_notes: 更新備註
    """
    await ensure_db_connection()
    from datetime import date

    async with get_connection() as conn:
        # 驗證專案存在
        project = await conn.fetchrow(
            "SELECT id, name FROM projects WHERE id = $1",
            project_id,
        )
        if not project:
            return f"錯誤：找不到專案 {project_id}"

        # 找到目標記錄
        if delivery_id:
            # 直接用 ID
            row = await conn.fetchrow(
                "SELECT * FROM project_delivery_schedules WHERE id = $1 AND project_id = $2",
                delivery_id, project_id,
            )
            if not row:
                return f"錯誤：找不到發包記錄 {delivery_id}"
            matches = [row]
        elif vendor and item:
            # 用廠商 + 料件匹配
            matches = await conn.fetch(
                """
                SELECT * FROM project_delivery_schedules
                WHERE project_id = $1 AND vendor ILIKE $2 AND item ILIKE $3
                """,
                project_id, f"%{vendor}%", f"%{item}%",
            )
            if not matches:
                return f"錯誤：找不到匹配的發包記錄（廠商：{vendor}，料件：{item}）"
            if len(matches) > 1:
                result = f"找到 {len(matches)} 筆匹配記錄，請更精確指定：\n"
                for m in matches:
                    result += f"- {m['vendor']} - {m['item']}（ID: {m['id']}）\n"
                return result
        elif vendor:
            # 只有廠商
            matches = await conn.fetch(
                "SELECT * FROM project_delivery_schedules WHERE project_id = $1 AND vendor ILIKE $2",
                project_id, f"%{vendor}%",
            )
            if not matches:
                return f"錯誤：找不到廠商「{vendor}」的發包記錄"
            if len(matches) > 1:
                result = f"找到 {len(matches)} 筆匹配記錄，請指定料件名稱：\n"
                for m in matches:
                    result += f"- {m['vendor']} - {m['item']}\n"
                return result
        else:
            return "錯誤：請提供 delivery_id，或同時提供 vendor 和 item 來匹配記錄"

        target = matches[0]

        # 建立更新
        updates = []
        params = []
        param_idx = 1

        if new_vendor:
            updates.append(f"vendor = ${param_idx}")
            params.append(new_vendor)
            param_idx += 1

        if new_item:
            updates.append(f"item = ${param_idx}")
            params.append(new_item)
            param_idx += 1

        if new_quantity:
            updates.append(f"quantity = ${param_idx}")
            params.append(new_quantity)
            param_idx += 1

        if order_date:
            try:
                parsed_date = date.fromisoformat(order_date)
                updates.append(f"order_date = ${param_idx}")
                params.append(parsed_date)
                param_idx += 1
            except ValueError:
                return "錯誤：發包日期格式錯誤，請使用 YYYY-MM-DD 格式"

        if new_status:
            valid_statuses = ["pending", "ordered", "delivered", "completed"]
            if new_status not in valid_statuses:
                return f"錯誤：狀態必須是 {', '.join(valid_statuses)} 其中之一"
            updates.append(f"status = ${param_idx}")
            params.append(new_status)
            param_idx += 1

        if actual_delivery_date:
            try:
                parsed_date = date.fromisoformat(actual_delivery_date)
                updates.append(f"actual_delivery_date = ${param_idx}")
                params.append(parsed_date)
                param_idx += 1
            except ValueError:
                return "錯誤：實際到貨日期格式錯誤，請使用 YYYY-MM-DD 格式"

        if expected_delivery_date:
            try:
                parsed_date = date.fromisoformat(expected_delivery_date)
                updates.append(f"expected_delivery_date = ${param_idx}")
                params.append(parsed_date)
                param_idx += 1
            except ValueError:
                return "錯誤：預計交貨日期格式錯誤，請使用 YYYY-MM-DD 格式"

        if new_notes:
            updates.append(f"notes = ${param_idx}")
            params.append(new_notes)
            param_idx += 1

        if not updates:
            return "錯誤：沒有要更新的欄位"

        updates.append("updated_at = NOW()")
        params.append(target["id"])

        sql = f"UPDATE project_delivery_schedules SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        updated = await conn.fetchrow(sql, *params)

        status_names = {
            "pending": "待發包",
            "ordered": "已發包",
            "delivered": "已到貨",
            "completed": "已完成",
        }

        result = f"✅ 已更新發包記錄\n"
        result += f"- 廠商：{updated['vendor']}\n"
        result += f"- 料件：{updated['item']}\n"
        if updated["quantity"]:
            result += f"- 數量：{updated['quantity']}\n"
        result += f"- 狀態：{status_names.get(updated['status'], updated['status'])}"
        if updated["order_date"]:
            result += f"\n- 發包日：{updated['order_date']}"
        if updated["expected_delivery_date"]:
            result += f"\n- 預計交貨：{updated['expected_delivery_date']}"
        if updated["actual_delivery_date"]:
            result += f"\n- 實際到貨：{updated['actual_delivery_date']}"

        return result


@mcp.tool()
async def get_delivery_schedules(
    project_id: str,
    status: str | None = None,
    vendor: str | None = None,
    limit: int = 20,
) -> str:
    """
    取得專案的發包/交貨記錄

    Args:
        project_id: 專案 UUID
        status: 狀態過濾，可選值:pending(待發包), ordered(已發包), delivered(已到貨), completed(已完成)
        vendor: 廠商過濾
        limit: 最大數量，預設 20
    """
    await ensure_db_connection()

    async with get_connection() as conn:
        # 驗證專案存在
        project = await conn.fetchrow(
            "SELECT id, name FROM projects WHERE id = $1",
            project_id,
        )
        if not project:
            return f"錯誤：找不到專案 {project_id}"

        # 建立查詢
        sql = "SELECT * FROM project_delivery_schedules WHERE project_id = $1"
        params = [project_id]
        param_idx = 2

        if status:
            sql += f" AND status = ${param_idx}"
            params.append(status)
            param_idx += 1

        if vendor:
            sql += f" AND vendor ILIKE ${param_idx}"
            params.append(f"%{vendor}%")
            param_idx += 1

        sql += f" ORDER BY COALESCE(expected_delivery_date, '9999-12-31'), created_at LIMIT ${param_idx}"
        params.append(limit)

        rows = await conn.fetch(sql, *params)

        if not rows:
            return f"專案「{project['name']}」目前沒有發包記錄"

        status_names = {
            "pending": "待發包",
            "ordered": "已發包",
            "delivered": "已到貨",
            "completed": "已完成",
        }

        result = f"📦 {project['name']} 的發包記錄（共 {len(rows)} 筆）：\n\n"

        for r in rows:
            status_display = status_names.get(r["status"], r["status"])
            result += f"【{r['vendor']}】{r['item']}\n"
            if r["quantity"]:
                result += f"  數量：{r['quantity']}\n"
            if r["order_date"]:
                result += f"  發包日：{r['order_date']}\n"
            if r["expected_delivery_date"]:
                result += f"  預計交貨：{r['expected_delivery_date']}\n"
            if r["actual_delivery_date"]:
                result += f"  實際到貨：{r['actual_delivery_date']}\n"
            result += f"  狀態：{status_display}\n"
            if r["notes"]:
                result += f"  備註：{r['notes']}\n"
            result += "\n"

        return result.strip()


# ============================================================
# 專案連結管理
# ============================================================


@mcp.tool()
async def add_project_link(
    project_id: str,
    title: str,
    url: str,
    description: str | None = None,
) -> str:
    """
    新增專案連結

    Args:
        project_id: 專案 UUID
        title: 連結標題（必填）
        url: URL（必填）
        description: 描述
    """
    await ensure_db_connection()

    async with get_connection() as conn:
        # 驗證專案存在
        project = await conn.fetchrow(
            "SELECT id, name FROM projects WHERE id = $1",
            project_id,
        )
        if not project:
            return f"錯誤：找不到專案 {project_id}"

        # 新增連結
        await conn.execute(
            """
            INSERT INTO project_links (project_id, title, url, description)
            VALUES ($1, $2, $3, $4)
            """,
            project_id,
            title,
            url,
            description,
        )

        return f"✅ 已為專案「{project['name']}」新增連結「{title}」"


@mcp.tool()
async def get_project_links(
    project_id: str,
    limit: int = 20,
) -> str:
    """
    查詢專案連結列表

    Args:
        project_id: 專案 UUID
        limit: 最大數量，預設 20
    """
    await ensure_db_connection()

    async with get_connection() as conn:
        # 驗證專案存在
        project = await conn.fetchrow(
            "SELECT id, name FROM projects WHERE id = $1",
            project_id,
        )
        if not project:
            return f"錯誤：找不到專案 {project_id}"

        # 查詢連結
        rows = await conn.fetch(
            """
            SELECT id, title, url, description, created_at
            FROM project_links
            WHERE project_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            project_id,
            limit,
        )

        if not rows:
            return f"專案「{project['name']}」目前沒有連結"

        result = f"🔗 {project['name']} 的連結（共 {len(rows)} 筆）：\n\n"

        for r in rows:
            result += f"【{r['title']}】\n"
            result += f"  URL：{r['url']}\n"
            if r["description"]:
                result += f"  說明：{r['description']}\n"
            result += f"  ID：{r['id']}\n\n"

        return result.strip()


@mcp.tool()
async def update_project_link(
    link_id: str,
    project_id: str | None = None,
    title: str | None = None,
    url: str | None = None,
    description: str | None = None,
) -> str:
    """
    更新專案連結

    Args:
        link_id: 連結 UUID
        project_id: 專案 UUID（可選，用於驗證）
        title: 新標題
        url: 新 URL
        description: 新描述
    """
    await ensure_db_connection()

    if not any([title, url, description is not None]):
        return "錯誤：請提供要更新的欄位（title、url 或 description）"

    async with get_connection() as conn:
        # 查詢連結
        sql = "SELECT * FROM project_links WHERE id = $1"
        params = [link_id]

        if project_id:
            sql += " AND project_id = $2"
            params.append(project_id)

        link = await conn.fetchrow(sql, *params)
        if not link:
            return f"錯誤：找不到連結 {link_id}"

        # 建立更新語句
        updates = []
        update_params = []
        param_idx = 1

        if title:
            updates.append(f"title = ${param_idx}")
            update_params.append(title)
            param_idx += 1

        if url:
            updates.append(f"url = ${param_idx}")
            update_params.append(url)
            param_idx += 1

        if description is not None:
            updates.append(f"description = ${param_idx}")
            update_params.append(description)
            param_idx += 1

        update_params.append(link_id)

        await conn.execute(
            f"UPDATE project_links SET {', '.join(updates)} WHERE id = ${param_idx}",
            *update_params,
        )

        return f"✅ 已更新連結「{title or link['title']}」"


@mcp.tool()
async def delete_project_link(
    link_id: str,
    project_id: str | None = None,
) -> str:
    """
    刪除專案連結

    Args:
        link_id: 連結 UUID
        project_id: 專案 UUID（可選，用於驗證）
    """
    await ensure_db_connection()

    async with get_connection() as conn:
        # 查詢連結
        sql = "SELECT * FROM project_links WHERE id = $1"
        params = [link_id]

        if project_id:
            sql += " AND project_id = $2"
            params.append(project_id)

        link = await conn.fetchrow(sql, *params)
        if not link:
            return f"錯誤：找不到連結 {link_id}"

        # 刪除連結
        await conn.execute("DELETE FROM project_links WHERE id = $1", link_id)

        return f"✅ 已刪除連結「{link['title']}」"


# ============================================================
# 專案附件管理
# ============================================================


@mcp.tool()
async def add_project_attachment(
    project_id: str,
    nas_path: str,
    description: str | None = None,
) -> str:
    """
    從 NAS 路徑添加附件到專案

    Args:
        project_id: 專案 UUID
        nas_path: NAS 檔案路徑（從 get_message_attachments 或 search_nas_files 取得）
        description: 描述
    """
    import mimetypes
    from pathlib import Path as FilePath
    from ..config import settings

    await ensure_db_connection()

    # 取得 NAS 路徑設定
    ctos_mount = settings.ctos_mount_path  # /mnt/nas/ctos
    linebot_files_path = settings.linebot_local_path  # /mnt/nas/ctos/ching-tech-os/linebot/files
    line_files_nas_path = settings.line_files_nas_path  # ching-tech-os/linebot/files

    async with get_connection() as conn:
        # 驗證專案存在
        project = await conn.fetchrow(
            "SELECT id, name FROM projects WHERE id = $1",
            project_id,
        )
        if not project:
            return f"錯誤：找不到專案 {project_id}"

        # 處理 NAS 路徑 - 支援多種格式
        # 1. nas://... - 完整 NAS 格式
        # 2. /mnt/nas/ctos/... - 完整掛載路徑
        # 3. users/... 或 groups/... - Line Bot 附件相對路徑
        # 4. projects/... - NAS 專案檔案相對路徑

        if nas_path.startswith("nas://"):
            # nas:// 格式
            relative_path = nas_path.replace("nas://", "")
            actual_path = FilePath(ctos_mount) / relative_path
            storage_path = nas_path
        elif nas_path.startswith(ctos_mount):
            # 完整掛載路徑
            actual_path = FilePath(nas_path)
            relative_path = nas_path.replace(f"{ctos_mount}/", "")
            storage_path = f"nas://{relative_path}"
        elif nas_path.startswith("users/") or nas_path.startswith("groups/"):
            # Line Bot 附件相對路徑（來自 get_message_attachments）
            # 實際路徑在 linebot_files_path（如 /mnt/nas/ctos/linebot/files/）
            actual_path = FilePath(linebot_files_path) / nas_path
            storage_path = f"nas://{line_files_nas_path}/{nas_path}"
        elif nas_path.startswith("projects/"):
            # NAS 專案檔案相對路徑（來自 search_nas_files）
            actual_path = FilePath(ctos_mount) / nas_path
            storage_path = f"nas://{nas_path}"
        else:
            # 嘗試作為 linebot/files 下的相對路徑
            actual_path = FilePath(linebot_files_path) / nas_path
            if actual_path.exists():
                storage_path = f"nas://{line_files_nas_path}/{nas_path}"
            else:
                # 嘗試作為 ctos_mount 下的相對路徑
                actual_path = FilePath(ctos_mount) / nas_path
                storage_path = f"nas://{nas_path}"

        # 檢查檔案存在
        if not actual_path.exists():
            return f"錯誤：找不到檔案 {nas_path}（嘗試路徑：{actual_path}）"

        # 取得檔案資訊
        filename = actual_path.name
        file_size = actual_path.stat().st_size
        file_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # 新增附件記錄
        await conn.execute(
            """
            INSERT INTO project_attachments
            (project_id, filename, file_type, file_size, storage_path, description, uploaded_by)
            VALUES ($1, $2, $3, $4, $5, $6, 'AI 助手')
            """,
            project_id,
            filename,
            file_type,
            file_size,
            storage_path,
            description,
        )

        return f"✅ 已為專案「{project['name']}」新增附件「{filename}」"


@mcp.tool()
async def get_project_attachments(
    project_id: str,
    limit: int = 20,
) -> str:
    """
    查詢專案附件列表

    Args:
        project_id: 專案 UUID
        limit: 最大數量，預設 20
    """
    await ensure_db_connection()

    async with get_connection() as conn:
        # 驗證專案存在
        project = await conn.fetchrow(
            "SELECT id, name FROM projects WHERE id = $1",
            project_id,
        )
        if not project:
            return f"錯誤：找不到專案 {project_id}"

        # 查詢附件
        rows = await conn.fetch(
            """
            SELECT id, filename, file_type, file_size, storage_path, description, uploaded_at, uploaded_by
            FROM project_attachments
            WHERE project_id = $1
            ORDER BY uploaded_at DESC
            LIMIT $2
            """,
            project_id,
            limit,
        )

        if not rows:
            return f"專案「{project['name']}」目前沒有附件"

        result = f"📎 {project['name']} 的附件（共 {len(rows)} 筆）：\n\n"

        for r in rows:
            # 格式化檔案大小
            size = r["file_size"] or 0
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / 1024 / 1024:.1f} MB"

            result += f"【{r['filename']}】\n"
            result += f"  類型：{r['file_type'] or '未知'}\n"
            result += f"  大小：{size_str}\n"
            if r["description"]:
                result += f"  說明：{r['description']}\n"
            # 顯示路徑（供 convert_pdf_to_images 等工具使用）
            if r["storage_path"]:
                result += f"  路徑：{r['storage_path']}\n"
            result += f"  ID：{r['id']}\n\n"

        return result.strip()


@mcp.tool()
async def update_project_attachment(
    attachment_id: str,
    project_id: str | None = None,
    description: str | None = None,
) -> str:
    """
    更新專案附件描述

    Args:
        attachment_id: 附件 UUID
        project_id: 專案 UUID（可選，用於驗證）
        description: 新描述
    """
    await ensure_db_connection()

    if description is None:
        return "錯誤：請提供要更新的描述（description）"

    async with get_connection() as conn:
        # 查詢附件
        sql = "SELECT * FROM project_attachments WHERE id = $1"
        params = [attachment_id]

        if project_id:
            sql += " AND project_id = $2"
            params.append(project_id)

        attachment = await conn.fetchrow(sql, *params)
        if not attachment:
            return f"錯誤：找不到附件 {attachment_id}"

        # 更新描述
        await conn.execute(
            "UPDATE project_attachments SET description = $1 WHERE id = $2",
            description,
            attachment_id,
        )

        return f"✅ 已更新附件「{attachment['filename']}」的描述"


@mcp.tool()
async def delete_project_attachment(
    attachment_id: str,
    project_id: str | None = None,
) -> str:
    """
    刪除專案附件

    Args:
        attachment_id: 附件 UUID
        project_id: 專案 UUID（可選，用於驗證）
    """
    await ensure_db_connection()

    async with get_connection() as conn:
        # 查詢附件
        sql = "SELECT * FROM project_attachments WHERE id = $1"
        params = [attachment_id]

        if project_id:
            sql += " AND project_id = $2"
            params.append(project_id)

        attachment = await conn.fetchrow(sql, *params)
        if not attachment:
            return f"錯誤：找不到附件 {attachment_id}"

        # 刪除附件記錄（不刪除實際檔案，因為是 NAS 引用）
        await conn.execute("DELETE FROM project_attachments WHERE id = $1", attachment_id)

        return f"✅ 已刪除附件「{attachment['filename']}」"


# ============================================================
# PDF 轉換工具
# ============================================================


@mcp.tool()
async def convert_pdf_to_images(
    pdf_path: str,
    pages: str = "all",
    output_format: str = "png",
    dpi: int = 150,
    max_pages: int = 20,
) -> str:
    """
    將 PDF 轉換為圖片

    Args:
        pdf_path: PDF 檔案路徑（NAS 路徑或暫存路徑）
        pages: 要轉換的頁面，預設 "all"
            - "0"：只查詢頁數，不轉換
            - "1"：只轉換第 1 頁
            - "1-3"：轉換第 1 到 3 頁
            - "1,3,5"：轉換第 1、3、5 頁
            - "all"：轉換全部頁面
        output_format: 輸出格式，可選 "png"（預設）或 "jpg"
        dpi: 解析度，預設 150，範圍 72-600
        max_pages: 最大頁數限制，預設 20
    """
    import json
    from pathlib import Path as FilePath

    from ..config import settings
    from .document_reader import (
        CorruptedFileError,
        PasswordProtectedError,
        UnsupportedFormatError,
        convert_pdf_to_images as do_convert,
    )

    # 驗證參數
    if output_format not in ("png", "jpg"):
        return json.dumps({
            "success": False,
            "error": f"不支援的輸出格式: {output_format}，請使用 png 或 jpg"
        }, ensure_ascii=False)

    if not 72 <= dpi <= 600:
        return json.dumps({
            "success": False,
            "error": f"DPI 必須在 72-600 之間，目前為 {dpi}"
        }, ensure_ascii=False)

    # 處理 PDF 路徑
    actual_path = pdf_path
    if pdf_path.startswith("nas://"):
        # nas://linebot/files/... -> /mnt/nas/ctos/linebot/files/...
        nas_relative = pdf_path[6:]  # 移除 "nas://"
        actual_path = f"{settings.ctos_mount_path}/{nas_relative}"
    elif not pdf_path.startswith("/"):
        # 相對路徑，嘗試 linebot/files 目錄
        actual_path = f"{settings.linebot_local_path}/{pdf_path}"

    # 檢查檔案存在
    if not FilePath(actual_path).exists():
        return json.dumps({
            "success": False,
            "error": f"PDF 檔案不存在: {pdf_path}"
        }, ensure_ascii=False)

    try:
        # 建立輸出目錄
        today = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")
        unique_id = str(uuid_module.uuid4())[:8]
        output_dir = f"{settings.linebot_local_path}/pdf-converted/{today}/{unique_id}"

        # 執行轉換
        result = do_convert(
            file_path=actual_path,
            output_dir=output_dir,
            pages=pages,
            dpi=dpi,
            output_format=output_format,
            max_pages=max_pages,
        )

        return json.dumps({
            "success": result.success,
            "total_pages": result.total_pages,
            "converted_pages": result.converted_pages,
            "images": result.images,
            "message": result.message,
        }, ensure_ascii=False)

    except FileNotFoundError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except PasswordProtectedError:
        return json.dumps({
            "success": False,
            "error": "此 PDF 有密碼保護，無法轉換"
        }, ensure_ascii=False)
    except UnsupportedFormatError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except CorruptedFileError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"PDF 轉換失敗: {e}")
        return json.dumps({
            "success": False,
            "error": f"轉換失敗: {str(e)}"
        }, ensure_ascii=False)


# ============================================================
# 工具存取介面（供 Line Bot 和其他服務使用）
# ============================================================


async def get_mcp_tools() -> list[dict]:
    """
    取得 MCP 工具定義列表，格式符合 Claude API

    Returns:
        工具定義列表，可直接用於 Claude API 的 tools 參數
    """
    tools = await mcp.list_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema,
        }
        for tool in tools
    ]


async def get_mcp_tool_names(exclude_group_only: bool = False) -> list[str]:
    """
    取得 MCP 工具名稱列表，格式為 mcp__ching-tech-os__{tool_name}

    Args:
        exclude_group_only: 是否排除群組專用工具（如 summarize_chat）

    Returns:
        工具名稱列表，可用於 Claude API 的 tools 參數
    """
    # 群組專用工具
    group_only_tools = {"summarize_chat"}

    tools = await mcp.list_tools()
    tool_names = []

    for tool in tools:
        if exclude_group_only and tool.name in group_only_tools:
            continue
        tool_names.append(f"mcp__ching-tech-os__{tool.name}")

    return tool_names


async def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    執行 MCP 工具

    Args:
        tool_name: 工具名稱
        arguments: 工具參數

    Returns:
        工具執行結果（文字）
    """
    try:
        result = await mcp.call_tool(tool_name, arguments)
        # result 是 (list[TextContent], dict) 的元組
        contents, _ = result
        if contents:
            return contents[0].text
        return "執行完成（無輸出）"
    except Exception as e:
        logger.error(f"執行工具 {tool_name} 失敗: {e}")
        return f"執行失敗：{str(e)}"


# ============================================================
# CLI 入口點（供 Claude Code 使用）
# ============================================================


def run_cli():
    """以 stdio 模式執行 MCP Server"""
    mcp.run()


if __name__ == "__main__":
    run_cli()
