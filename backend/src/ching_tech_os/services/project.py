"""專案管理服務"""

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from ..config import settings
from ..database import get_connection
from ..models.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectDetailResponse,
    ProjectListItem,
    ProjectListResponse,
    ProjectMemberCreate,
    ProjectMemberUpdate,
    ProjectMemberResponse,
    ProjectMeetingCreate,
    ProjectMeetingUpdate,
    ProjectMeetingResponse,
    ProjectMeetingListItem,
    ProjectAttachmentCreate,
    ProjectAttachmentUpdate,
    ProjectAttachmentResponse,
    ProjectLinkCreate,
    ProjectLinkUpdate,
    ProjectLinkResponse,
    ProjectMilestoneCreate,
    ProjectMilestoneUpdate,
    ProjectMilestoneResponse,
    DeliveryScheduleCreate,
    DeliveryScheduleUpdate,
    DeliveryScheduleResponse,
)
from .local_file import LocalFileService, LocalFileError, create_project_file_service, create_linebot_file_service


class ProjectError(Exception):
    """專案操作錯誤"""
    pass


class ProjectNotFoundError(ProjectError):
    """專案不存在"""
    pass


# ============================================
# 專案 CRUD
# ============================================


async def list_projects(
    status: str | None = None,
    query: str | None = None,
) -> ProjectListResponse:
    """列出專案"""
    async with get_connection() as conn:
        # 建立查詢
        sql = """
            SELECT
                p.id, p.name, p.status, p.start_date, p.end_date, p.updated_at,
                (SELECT COUNT(*) FROM project_members WHERE project_id = p.id) as member_count,
                (SELECT COUNT(*) FROM project_meetings WHERE project_id = p.id) as meeting_count,
                (SELECT COUNT(*) FROM project_attachments WHERE project_id = p.id) as attachment_count
            FROM projects p
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if status:
            sql += f" AND p.status = ${param_idx}"
            params.append(status)
            param_idx += 1

        if query:
            sql += f" AND (p.name ILIKE ${param_idx} OR p.description ILIKE ${param_idx})"
            params.append(f"%{query}%")
            param_idx += 1

        sql += " ORDER BY p.updated_at DESC"

        rows = await conn.fetch(sql, *params)

        items = [
            ProjectListItem(
                id=row["id"],
                name=row["name"],
                status=row["status"],
                start_date=row["start_date"],
                end_date=row["end_date"],
                updated_at=row["updated_at"],
                member_count=row["member_count"],
                meeting_count=row["meeting_count"],
                attachment_count=row["attachment_count"],
            )
            for row in rows
        ]

        return ProjectListResponse(items=items, total=len(items))


async def get_project(project_id: UUID) -> ProjectDetailResponse:
    """取得專案詳情"""
    async with get_connection() as conn:
        # 取得專案基本資料
        row = await conn.fetchrow(
            "SELECT * FROM projects WHERE id = $1", project_id
        )
        if not row:
            raise ProjectNotFoundError(f"專案 {project_id} 不存在")

        # 取得成員
        members_rows = await conn.fetch(
            "SELECT * FROM project_members WHERE project_id = $1 ORDER BY created_at",
            project_id,
        )
        members = [ProjectMemberResponse(**dict(r)) for r in members_rows]

        # 取得會議（只取列表項目）
        meetings_rows = await conn.fetch(
            "SELECT id, title, meeting_date, location, attendees FROM project_meetings WHERE project_id = $1 ORDER BY meeting_date DESC",
            project_id,
        )
        meetings = [ProjectMeetingListItem(**dict(r)) for r in meetings_rows]

        # 取得附件
        attachments_rows = await conn.fetch(
            "SELECT * FROM project_attachments WHERE project_id = $1 ORDER BY uploaded_at DESC",
            project_id,
        )
        attachments = [ProjectAttachmentResponse(**dict(r)) for r in attachments_rows]

        # 取得連結
        links_rows = await conn.fetch(
            "SELECT * FROM project_links WHERE project_id = $1 ORDER BY created_at DESC",
            project_id,
        )
        links = [ProjectLinkResponse(**dict(r)) for r in links_rows]

        # 取得里程碑
        milestones_rows = await conn.fetch(
            "SELECT * FROM project_milestones WHERE project_id = $1 ORDER BY COALESCE(planned_date, '9999-12-31'), sort_order",
            project_id,
        )
        milestones = [ProjectMilestoneResponse(**dict(r)) for r in milestones_rows]

        # 取得發包/交貨記錄
        deliveries_rows = await conn.fetch(
            "SELECT * FROM project_delivery_schedules WHERE project_id = $1 ORDER BY COALESCE(expected_delivery_date, '9999-12-31'), created_at",
            project_id,
        )
        deliveries = [DeliveryScheduleResponse(**dict(r)) for r in deliveries_rows]

        return ProjectDetailResponse(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=row["status"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            members=members,
            meetings=meetings,
            attachments=attachments,
            links=links,
            milestones=milestones,
            deliveries=deliveries,
        )


async def create_project(data: ProjectCreate, created_by: str | None = None) -> ProjectResponse:
    """建立專案"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO projects (name, description, status, start_date, end_date, created_by)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            data.name,
            data.description,
            data.status,
            data.start_date,
            data.end_date,
            created_by,
        )
        return ProjectResponse(**dict(row))


async def update_project(project_id: UUID, data: ProjectUpdate) -> ProjectResponse:
    """更新專案"""
    async with get_connection() as conn:
        # 檢查專案是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM projects WHERE id = $1", project_id
        )
        if not exists:
            raise ProjectNotFoundError(f"專案 {project_id} 不存在")

        # 動態建立更新語句
        updates = []
        params = []
        param_idx = 1

        if data.name is not None:
            updates.append(f"name = ${param_idx}")
            params.append(data.name)
            param_idx += 1
        if data.description is not None:
            updates.append(f"description = ${param_idx}")
            params.append(data.description)
            param_idx += 1
        if data.status is not None:
            updates.append(f"status = ${param_idx}")
            params.append(data.status)
            param_idx += 1
        if data.start_date is not None:
            updates.append(f"start_date = ${param_idx}")
            params.append(data.start_date)
            param_idx += 1
        if data.end_date is not None:
            updates.append(f"end_date = ${param_idx}")
            params.append(data.end_date)
            param_idx += 1

        if not updates:
            # 沒有更新，直接返回現有資料
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE id = $1", project_id
            )
            return ProjectResponse(**dict(row))

        updates.append("updated_at = NOW()")
        params.append(project_id)

        sql = f"UPDATE projects SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(sql, *params)
        return ProjectResponse(**dict(row))


async def delete_project(project_id: UUID) -> None:
    """刪除專案"""
    async with get_connection() as conn:
        # 檢查專案是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM projects WHERE id = $1", project_id
        )
        if not exists:
            raise ProjectNotFoundError(f"專案 {project_id} 不存在")

        # 先取得附件列表以便刪除檔案
        attachments = await conn.fetch(
            "SELECT storage_path FROM project_attachments WHERE project_id = $1",
            project_id,
        )

        # 刪除專案（會級聯刪除所有關聯資料）
        await conn.execute("DELETE FROM projects WHERE id = $1", project_id)

        # 刪除附件檔案
        for att in attachments:
            _delete_attachment_file(att["storage_path"])


# ============================================
# 專案成員
# ============================================


async def list_members(project_id: UUID) -> list[ProjectMemberResponse]:
    """列出專案成員"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT pm.*, u.username as user_username, u.display_name as user_display_name
            FROM project_members pm
            LEFT JOIN users u ON pm.user_id = u.id
            WHERE pm.project_id = $1
            ORDER BY pm.created_at
            """,
            project_id,
        )
        return [ProjectMemberResponse(**dict(r)) for r in rows]


async def create_member(project_id: UUID, data: ProjectMemberCreate) -> ProjectMemberResponse:
    """新增專案成員"""
    async with get_connection() as conn:
        # 檢查專案是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM projects WHERE id = $1", project_id
        )
        if not exists:
            raise ProjectNotFoundError(f"專案 {project_id} 不存在")

        row = await conn.fetchrow(
            """
            INSERT INTO project_members (project_id, name, role, company, email, phone, notes, is_internal, user_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            project_id,
            data.name,
            data.role,
            data.company,
            data.email,
            data.phone,
            data.notes,
            data.is_internal,
            data.user_id,
        )
        # 如果有 user_id，查詢 user 資訊
        result = dict(row)
        if result.get("user_id"):
            user = await conn.fetchrow(
                "SELECT username, display_name FROM users WHERE id = $1",
                result["user_id"],
            )
            if user:
                result["user_username"] = user["username"]
                result["user_display_name"] = user["display_name"]
        return ProjectMemberResponse(**result)


async def update_member(
    project_id: UUID, member_id: UUID, data: ProjectMemberUpdate
) -> ProjectMemberResponse:
    """更新專案成員"""
    async with get_connection() as conn:
        # 檢查成員是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM project_members WHERE id = $1 AND project_id = $2",
            member_id, project_id,
        )
        if not exists:
            raise ProjectNotFoundError(f"成員 {member_id} 不存在")

        # 動態建立更新語句
        updates = []
        params = []
        param_idx = 1

        for field in ["name", "role", "company", "email", "phone", "notes", "is_internal", "user_id"]:
            value = getattr(data, field)
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            # 沒有更新，返回現有資料（含用戶資訊）
            row = await conn.fetchrow(
                """
                SELECT pm.*, u.username as user_username, u.display_name as user_display_name
                FROM project_members pm
                LEFT JOIN users u ON pm.user_id = u.id
                WHERE pm.id = $1
                """,
                member_id,
            )
            return ProjectMemberResponse(**dict(row))

        params.append(member_id)
        sql = f"UPDATE project_members SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(sql, *params)

        # 查詢關聯用戶資訊
        result = dict(row)
        result["user_username"] = None
        result["user_display_name"] = None
        if result.get("user_id"):
            user = await conn.fetchrow(
                "SELECT username, display_name FROM users WHERE id = $1",
                result["user_id"],
            )
            if user:
                result["user_username"] = user["username"]
                result["user_display_name"] = user["display_name"]
        return ProjectMemberResponse(**result)


async def delete_member(project_id: UUID, member_id: UUID) -> None:
    """刪除專案成員"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM project_members WHERE id = $1 AND project_id = $2",
            member_id, project_id,
        )
        if result == "DELETE 0":
            raise ProjectNotFoundError(f"成員 {member_id} 不存在")


# ============================================
# 會議記錄
# ============================================


async def list_meetings(project_id: UUID) -> list[ProjectMeetingListItem]:
    """列出會議記錄"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT id, title, meeting_date, location, attendees FROM project_meetings WHERE project_id = $1 ORDER BY meeting_date DESC",
            project_id,
        )
        return [ProjectMeetingListItem(**dict(r)) for r in rows]


async def get_meeting(project_id: UUID, meeting_id: UUID) -> ProjectMeetingResponse:
    """取得會議詳情"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM project_meetings WHERE id = $1 AND project_id = $2",
            meeting_id, project_id,
        )
        if not row:
            raise ProjectNotFoundError(f"會議 {meeting_id} 不存在")
        return ProjectMeetingResponse(**dict(row))


async def create_meeting(
    project_id: UUID, data: ProjectMeetingCreate, created_by: str | None = None
) -> ProjectMeetingResponse:
    """新增會議記錄"""
    async with get_connection() as conn:
        # 檢查專案是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM projects WHERE id = $1", project_id
        )
        if not exists:
            raise ProjectNotFoundError(f"專案 {project_id} 不存在")

        # 處理日期時間時區問題
        meeting_date = data.meeting_date
        if meeting_date is not None and isinstance(meeting_date, datetime):
            if meeting_date.tzinfo is None:
                # 如果沒有時區資訊，假設是本地時間 (UTC+8)
                from datetime import timedelta
                meeting_date = meeting_date.replace(tzinfo=timezone(timedelta(hours=8)))

        row = await conn.fetchrow(
            """
            INSERT INTO project_meetings (project_id, title, meeting_date, location, attendees, content, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            project_id,
            data.title,
            meeting_date,
            data.location,
            data.attendees,
            data.content,
            created_by,
        )
        return ProjectMeetingResponse(**dict(row))


async def update_meeting(
    project_id: UUID, meeting_id: UUID, data: ProjectMeetingUpdate
) -> ProjectMeetingResponse:
    """更新會議記錄"""
    async with get_connection() as conn:
        # 檢查會議是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM project_meetings WHERE id = $1 AND project_id = $2",
            meeting_id, project_id,
        )
        if not exists:
            raise ProjectNotFoundError(f"會議 {meeting_id} 不存在")

        # 動態建立更新語句
        updates = []
        params = []
        param_idx = 1

        for field in ["title", "meeting_date", "location", "attendees", "content"]:
            value = getattr(data, field)
            if value is not None:
                # 處理日期時間時區問題（資料庫使用 timestamptz）
                if field == "meeting_date" and isinstance(value, datetime):
                    if value.tzinfo is None:
                        # 如果沒有時區資訊，假設是本地時間 (UTC+8)
                        from datetime import timedelta
                        value = value.replace(tzinfo=timezone(timedelta(hours=8)))
                    # 如果已有時區資訊（例如 UTC），直接使用，資料庫會正確儲存
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            row = await conn.fetchrow(
                "SELECT * FROM project_meetings WHERE id = $1", meeting_id
            )
            return ProjectMeetingResponse(**dict(row))

        updates.append("updated_at = NOW()")
        params.append(meeting_id)
        sql = f"UPDATE project_meetings SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(sql, *params)
        return ProjectMeetingResponse(**dict(row))


async def delete_meeting(project_id: UUID, meeting_id: UUID) -> None:
    """刪除會議記錄"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM project_meetings WHERE id = $1 AND project_id = $2",
            meeting_id, project_id,
        )
        if result == "DELETE 0":
            raise ProjectNotFoundError(f"會議 {meeting_id} 不存在")


# ============================================
# 專案附件
# ============================================


def _get_file_type(filename: str) -> str:
    """判斷檔案類型"""
    ext = Path(filename).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"):
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in (".dwg", ".dxf", ".step", ".stp", ".iges", ".igs"):
        return "cad"
    if ext in (".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"):
        return "document"
    return "other"


def _delete_attachment_file(storage_path: str) -> None:
    """刪除附件檔案"""
    from .path_manager import path_manager, StorageZone
    try:
        parsed = path_manager.parse(storage_path)
        if parsed.zone == StorageZone.CTOS:
            # CTOS 區檔案：使用 path_manager 解析完整路徑
            try:
                full_path = Path(path_manager.to_filesystem(storage_path))
                if full_path.exists():
                    full_path.unlink()
            except Exception:
                pass  # 忽略刪除錯誤
        elif parsed.zone == StorageZone.LOCAL:
            # 本機檔案
            try:
                file_path = Path(settings.project_attachments_path) / parsed.path
                if file_path.exists():
                    file_path.unlink()
            except Exception:
                pass  # 忽略刪除錯誤
    except Exception:
        pass  # 路徑解析失敗，忽略


async def list_attachments(project_id: UUID) -> list[ProjectAttachmentResponse]:
    """列出專案附件"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM project_attachments WHERE project_id = $1 ORDER BY uploaded_at DESC",
            project_id,
        )
        return [ProjectAttachmentResponse(**dict(r)) for r in rows]


async def upload_attachment(
    project_id: UUID,
    filename: str,
    data: bytes,
    description: str | None = None,
    uploaded_by: str | None = None,
) -> ProjectAttachmentResponse:
    """上傳附件"""
    async with get_connection() as conn:
        # 檢查專案是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM projects WHERE id = $1", project_id
        )
        if not exists:
            raise ProjectNotFoundError(f"專案 {project_id} 不存在")

        file_size = len(data)
        file_type = _get_file_type(filename)

        # 判斷儲存位置
        if file_size < 1024 * 1024:  # < 1MB 存本機
            # 建立目錄
            local_dir = Path(settings.project_attachments_path) / str(project_id)
            local_dir.mkdir(parents=True, exist_ok=True)

            # 儲存檔案
            local_path = local_dir / filename
            with open(local_path, "wb") as f:
                f.write(data)

            storage_path = f"{project_id}/{filename}"
        else:  # >= 1MB 存 NAS（透過掛載路徑）
            nas_path = f"attachments/{project_id}/{filename}"
            try:
                file_service = create_project_file_service()
                # write_file 會自動建立目錄
                file_service.write_file(nas_path, data)
            except LocalFileError as e:
                raise ProjectError(f"上傳至 NAS 失敗：{e}") from e

            storage_path = f"ctos://projects/{nas_path}"

        # 寫入資料庫
        row = await conn.fetchrow(
            """
            INSERT INTO project_attachments (project_id, filename, file_type, file_size, storage_path, description, uploaded_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            project_id,
            filename,
            file_type,
            file_size,
            storage_path,
            description,
            uploaded_by,
        )
        return ProjectAttachmentResponse(**dict(row))


async def get_attachment_content(project_id: UUID, attachment_id: UUID) -> tuple[bytes, str]:
    """取得附件內容"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT storage_path, filename FROM project_attachments WHERE id = $1 AND project_id = $2",
            attachment_id, project_id,
        )
        if not row:
            raise ProjectNotFoundError(f"附件 {attachment_id} 不存在")

        storage_path = row["storage_path"]
        filename = row["filename"]

        # 使用 PathManager 解析路徑
        from .path_manager import path_manager, StorageZone
        try:
            parsed = path_manager.parse(storage_path)

            if parsed.zone == StorageZone.CTOS:
                # CTOS 區檔案（透過掛載路徑存取）
                try:
                    fs_path = path_manager.to_filesystem(storage_path)
                    file_path = Path(fs_path)
                    if not file_path.exists():
                        raise ProjectError(f"檔案不存在：{storage_path}")
                    with open(file_path, "rb") as f:
                        return f.read(), filename
                except LocalFileError as e:
                    raise ProjectError(f"讀取檔案失敗：{e}") from e
            elif parsed.zone == StorageZone.LOCAL:
                # 本機檔案
                file_path = Path(settings.project_attachments_path) / parsed.path
                if not file_path.exists():
                    raise ProjectError(f"檔案不存在：{storage_path}")
                with open(file_path, "rb") as f:
                    return f.read(), filename
            else:
                raise ProjectError(f"不支援的儲存區域：{parsed.zone.value}")
        except ValueError as e:
            raise ProjectError(f"無效的路徑格式：{storage_path}") from e


async def update_attachment(
    project_id: UUID, attachment_id: UUID, data: ProjectAttachmentUpdate
) -> ProjectAttachmentResponse:
    """更新附件資訊"""
    async with get_connection() as conn:
        # 檢查附件是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM project_attachments WHERE id = $1 AND project_id = $2",
            attachment_id, project_id,
        )
        if not exists:
            raise ProjectNotFoundError(f"附件 {attachment_id} 不存在")

        if data.description is not None:
            row = await conn.fetchrow(
                "UPDATE project_attachments SET description = $1 WHERE id = $2 RETURNING *",
                data.description, attachment_id,
            )
        else:
            row = await conn.fetchrow(
                "SELECT * FROM project_attachments WHERE id = $1", attachment_id
            )
        return ProjectAttachmentResponse(**dict(row))


async def delete_attachment(project_id: UUID, attachment_id: UUID) -> None:
    """刪除附件"""
    async with get_connection() as conn:
        # 取得附件資訊
        row = await conn.fetchrow(
            "SELECT storage_path FROM project_attachments WHERE id = $1 AND project_id = $2",
            attachment_id, project_id,
        )
        if not row:
            raise ProjectNotFoundError(f"附件 {attachment_id} 不存在")

        # 刪除檔案
        _delete_attachment_file(row["storage_path"])

        # 刪除資料庫記錄
        await conn.execute(
            "DELETE FROM project_attachments WHERE id = $1", attachment_id
        )


# ============================================
# 專案連結
# ============================================


async def list_links(project_id: UUID) -> list[ProjectLinkResponse]:
    """列出專案連結"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM project_links WHERE project_id = $1 ORDER BY created_at DESC",
            project_id,
        )
        return [ProjectLinkResponse(**dict(r)) for r in rows]


async def create_link(project_id: UUID, data: ProjectLinkCreate) -> ProjectLinkResponse:
    """新增專案連結"""
    async with get_connection() as conn:
        # 檢查專案是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM projects WHERE id = $1", project_id
        )
        if not exists:
            raise ProjectNotFoundError(f"專案 {project_id} 不存在")

        row = await conn.fetchrow(
            """
            INSERT INTO project_links (project_id, title, url, description)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            project_id,
            data.title,
            data.url,
            data.description,
        )
        return ProjectLinkResponse(**dict(row))


async def update_link(
    project_id: UUID, link_id: UUID, data: ProjectLinkUpdate
) -> ProjectLinkResponse:
    """更新專案連結"""
    async with get_connection() as conn:
        # 檢查連結是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM project_links WHERE id = $1 AND project_id = $2",
            link_id, project_id,
        )
        if not exists:
            raise ProjectNotFoundError(f"連結 {link_id} 不存在")

        # 動態建立更新語句
        updates = []
        params = []
        param_idx = 1

        for field in ["title", "url", "description"]:
            value = getattr(data, field)
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            row = await conn.fetchrow(
                "SELECT * FROM project_links WHERE id = $1", link_id
            )
            return ProjectLinkResponse(**dict(row))

        params.append(link_id)
        sql = f"UPDATE project_links SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(sql, *params)
        return ProjectLinkResponse(**dict(row))


async def delete_link(project_id: UUID, link_id: UUID) -> None:
    """刪除專案連結"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM project_links WHERE id = $1 AND project_id = $2",
            link_id, project_id,
        )
        if result == "DELETE 0":
            raise ProjectNotFoundError(f"連結 {link_id} 不存在")


# ============================================
# 專案里程碑
# ============================================


async def list_milestones(project_id: UUID) -> list[ProjectMilestoneResponse]:
    """列出專案里程碑"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM project_milestones WHERE project_id = $1 ORDER BY COALESCE(planned_date, '9999-12-31'), sort_order",
            project_id,
        )
        return [ProjectMilestoneResponse(**dict(r)) for r in rows]


async def create_milestone(
    project_id: UUID, data: ProjectMilestoneCreate
) -> ProjectMilestoneResponse:
    """新增專案里程碑"""
    async with get_connection() as conn:
        # 檢查專案是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM projects WHERE id = $1", project_id
        )
        if not exists:
            raise ProjectNotFoundError(f"專案 {project_id} 不存在")

        row = await conn.fetchrow(
            """
            INSERT INTO project_milestones (project_id, name, milestone_type, planned_date, actual_date, status, notes, sort_order)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            project_id,
            data.name,
            data.milestone_type,
            data.planned_date,
            data.actual_date,
            data.status,
            data.notes,
            data.sort_order,
        )
        return ProjectMilestoneResponse(**dict(row))


async def update_milestone(
    project_id: UUID, milestone_id: UUID, data: ProjectMilestoneUpdate
) -> ProjectMilestoneResponse:
    """更新專案里程碑"""
    async with get_connection() as conn:
        # 檢查里程碑是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM project_milestones WHERE id = $1 AND project_id = $2",
            milestone_id, project_id,
        )
        if not exists:
            raise ProjectNotFoundError(f"里程碑 {milestone_id} 不存在")

        # 動態建立更新語句
        updates = []
        params = []
        param_idx = 1

        for field in ["name", "milestone_type", "planned_date", "actual_date", "status", "notes", "sort_order"]:
            value = getattr(data, field)
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            row = await conn.fetchrow(
                "SELECT * FROM project_milestones WHERE id = $1", milestone_id
            )
            return ProjectMilestoneResponse(**dict(row))

        updates.append("updated_at = NOW()")
        params.append(milestone_id)
        sql = f"UPDATE project_milestones SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(sql, *params)
        return ProjectMilestoneResponse(**dict(row))


async def delete_milestone(project_id: UUID, milestone_id: UUID) -> None:
    """刪除專案里程碑"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM project_milestones WHERE id = $1 AND project_id = $2",
            milestone_id, project_id,
        )
        if result == "DELETE 0":
            raise ProjectNotFoundError(f"里程碑 {milestone_id} 不存在")


# ============================================
# 專案發包/交貨期程
# ============================================


async def list_deliveries(project_id: UUID) -> list[DeliveryScheduleResponse]:
    """列出專案發包記錄"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM project_delivery_schedules WHERE project_id = $1 ORDER BY COALESCE(expected_delivery_date, '9999-12-31'), created_at",
            project_id,
        )
        return [DeliveryScheduleResponse(**dict(r)) for r in rows]


async def create_delivery(
    project_id: UUID, data: DeliveryScheduleCreate, created_by: str | None = None
) -> DeliveryScheduleResponse:
    """新增專案發包記錄"""
    async with get_connection() as conn:
        # 檢查專案是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM projects WHERE id = $1", project_id
        )
        if not exists:
            raise ProjectNotFoundError(f"專案 {project_id} 不存在")

        row = await conn.fetchrow(
            """
            INSERT INTO project_delivery_schedules (project_id, vendor, item, quantity, order_date, expected_delivery_date, status, notes, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            project_id,
            data.vendor,
            data.item,
            data.quantity,
            data.order_date,
            data.expected_delivery_date,
            data.status,
            data.notes,
            created_by,
        )
        return DeliveryScheduleResponse(**dict(row))


async def update_delivery(
    project_id: UUID, delivery_id: UUID, data: DeliveryScheduleUpdate
) -> DeliveryScheduleResponse:
    """更新專案發包記錄"""
    async with get_connection() as conn:
        # 檢查發包記錄是否存在
        exists = await conn.fetchval(
            "SELECT 1 FROM project_delivery_schedules WHERE id = $1 AND project_id = $2",
            delivery_id, project_id,
        )
        if not exists:
            raise ProjectNotFoundError(f"發包記錄 {delivery_id} 不存在")

        # 動態建立更新語句
        updates = []
        params = []
        param_idx = 1

        for field in ["vendor", "item", "quantity", "order_date", "expected_delivery_date", "actual_delivery_date", "status", "notes"]:
            value = getattr(data, field)
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            row = await conn.fetchrow(
                "SELECT * FROM project_delivery_schedules WHERE id = $1", delivery_id
            )
            return DeliveryScheduleResponse(**dict(row))

        updates.append("updated_at = NOW()")
        params.append(delivery_id)
        sql = f"UPDATE project_delivery_schedules SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *"
        row = await conn.fetchrow(sql, *params)
        return DeliveryScheduleResponse(**dict(row))


async def delete_delivery(project_id: UUID, delivery_id: UUID) -> None:
    """刪除專案發包記錄"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM project_delivery_schedules WHERE id = $1 AND project_id = $2",
            delivery_id, project_id,
        )
        if result == "DELETE 0":
            raise ProjectNotFoundError(f"發包記錄 {delivery_id} 不存在")
