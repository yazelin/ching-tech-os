"""公開分享連結服務"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

from pathlib import Path

from ..config import settings
from ..database import get_connection
from ..models.share import (
    ShareLinkCreate,
    ShareLinkResponse,
    ShareLinkListResponse,
    PublicResourceResponse,
)
from .knowledge import get_knowledge, KnowledgeNotFoundError
from .project import get_project, ProjectNotFoundError


class NasFileNotFoundError(Exception):
    """NAS 檔案不存在"""
    pass


class NasFileAccessDenied(Exception):
    """NAS 檔案存取被拒絕"""
    pass


class ShareError(Exception):
    """分享連結操作錯誤"""
    pass


class ShareLinkNotFoundError(ShareError):
    """連結不存在"""
    pass


class ShareLinkExpiredError(ShareError):
    """連結已過期"""
    pass


class ResourceNotFoundError(ShareError):
    """資源不存在"""
    pass


def generate_token(length: int = 6) -> str:
    """產生隨機 token

    使用加密安全的隨機產生器
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def parse_expires_in(expires_in: str | None) -> datetime | None:
    """解析有效期設定

    Args:
        expires_in: 1h, 24h, 7d, null（永久）

    Returns:
        過期時間（UTC），None 表示永久
    """
    if expires_in is None or expires_in == "null":
        return None

    now = datetime.now(timezone.utc)

    if expires_in == "1h":
        return now + timedelta(hours=1)
    elif expires_in == "24h":
        return now + timedelta(hours=24)
    elif expires_in == "7d":
        return now + timedelta(days=7)
    else:
        # 預設 24 小時
        return now + timedelta(hours=24)


def get_full_url(token: str) -> str:
    """取得完整的分享連結 URL"""
    return f"{settings.public_url}/s/{token}"


def validate_nas_file_path(file_path: str) -> Path:
    """驗證 NAS 檔案路徑

    Args:
        file_path: 檔案路徑（完整路徑或相對路徑）

    Returns:
        驗證後的完整路徑

    Raises:
        NasFileAccessDenied: 路徑不在允許範圍內
        NasFileNotFoundError: 檔案不存在
    """
    from .path_manager import path_manager, StorageZone

    ctos_path = Path(settings.ctos_mount_path)

    # 特殊處理：nanobanana 輸出路徑（/tmp/.../nanobanana-output/xxx.jpg）
    # 這些檔案已被複製到 NAS，需要映射到實際位置
    if "/nanobanana-output/" in file_path or file_path.startswith("nanobanana-output/"):
        filename = file_path.split("nanobanana-output/")[-1]
        full_path = ctos_path / "linebot" / "files" / "ai-images" / filename
    elif file_path.startswith("ai-images/"):
        # ai-images/ 相對路徑
        filename = file_path.split("/", 1)[1] if "/" in file_path else file_path
        full_path = ctos_path / "linebot" / "files" / "ai-images" / filename
    else:
        # 使用 PathManager 解析其他路徑格式
        try:
            parsed = path_manager.parse(file_path)
        except ValueError as e:
            raise NasFileAccessDenied(f"無效的路徑：{e}")

        # 安全檢查：只允許 CTOS 和 SHARED 區域
        if parsed.zone not in (StorageZone.CTOS, StorageZone.SHARED):
            raise NasFileAccessDenied(f"不允許存取 {parsed.zone.value}:// 區域的檔案")

        full_path = Path(path_manager.to_filesystem(file_path))

    # 安全檢查：確保路徑在 /mnt/nas/ 下
    nas_path = Path(settings.nas_mount_path)
    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(nas_path.resolve())):
            raise NasFileAccessDenied(f"不允許存取此路徑：{file_path}")
    except NasFileAccessDenied:
        raise
    except Exception:
        raise NasFileAccessDenied(f"無效的路徑：{file_path}")

    if not full_path.exists():
        raise NasFileNotFoundError(f"檔案不存在：{file_path}")

    if not full_path.is_file():
        raise NasFileNotFoundError(f"路徑不是檔案：{file_path}")

    return full_path


async def get_resource_title(resource_type: str, resource_id: str) -> str:
    """取得資源標題"""
    try:
        if resource_type == "knowledge":
            knowledge = get_knowledge(resource_id)
            return knowledge.title
        elif resource_type == "project":
            project = await get_project(UUID(resource_id))
            return project.name
        elif resource_type == "nas_file":
            # 驗證路徑並回傳檔名
            full_path = validate_nas_file_path(resource_id)
            return full_path.name
        elif resource_type == "project_attachment":
            # 取得專案附件資訊
            attachment = await get_project_attachment_info(resource_id)
            return attachment["filename"]
        else:
            return "未知資源"
    except (KnowledgeNotFoundError, ProjectNotFoundError):
        raise ResourceNotFoundError(f"資源 {resource_type}/{resource_id} 不存在")
    except NasFileNotFoundError as e:
        raise ResourceNotFoundError(str(e))
    except NasFileAccessDenied as e:
        raise ResourceNotFoundError(str(e))


async def get_project_attachment_info(attachment_id: str) -> dict:
    """取得專案附件資訊"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, filename, storage_path, file_type, project_id, file_size FROM project_attachments WHERE id = $1",
            UUID(attachment_id),
        )
        if not row:
            raise ResourceNotFoundError(f"附件 {attachment_id} 不存在")
        return dict(row)


async def create_share_link(
    data: ShareLinkCreate,
    created_by: str,
) -> ShareLinkResponse:
    """建立分享連結"""
    # 驗證資源存在
    resource_title = await get_resource_title(data.resource_type, data.resource_id)

    # 產生唯一 token
    async with get_connection() as conn:
        # 嘗試產生唯一 token（最多 10 次）
        for _ in range(10):
            token = generate_token()
            # 檢查是否已存在
            existing = await conn.fetchval(
                "SELECT 1 FROM public_share_links WHERE token = $1",
                token,
            )
            if not existing:
                break
        else:
            raise ShareError("無法產生唯一的 token")

        # 計算過期時間
        expires_at = parse_expires_in(data.expires_in)

        # 儲存到資料庫
        now = datetime.now(timezone.utc)
        row = await conn.fetchrow(
            """
            INSERT INTO public_share_links (token, resource_type, resource_id, created_by, expires_at, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, token, resource_type, resource_id, created_by, expires_at, access_count, created_at
            """,
            token,
            data.resource_type,
            data.resource_id,
            created_by,
            expires_at,
            now,
        )

        return ShareLinkResponse(
            token=row["token"],
            url=f"/s/{row['token']}",
            full_url=get_full_url(row["token"]),
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            resource_title=resource_title,
            expires_at=row["expires_at"],
            access_count=row["access_count"],
            created_at=row["created_at"],
            is_expired=False,
        )


async def list_my_links(username: str) -> ShareLinkListResponse:
    """列出使用者的分享連結"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT token, resource_type, resource_id, created_by, expires_at, access_count, created_at
            FROM public_share_links
            WHERE created_by = $1
            ORDER BY created_at DESC
            """,
            username,
        )

        now = datetime.now(timezone.utc)
        links = []

        for row in rows:
            # 取得資源標題
            try:
                resource_title = await get_resource_title(
                    row["resource_type"], row["resource_id"]
                )
            except ResourceNotFoundError:
                resource_title = "（已刪除）"

            # 判斷是否過期
            is_expired = False
            if row["expires_at"]:
                is_expired = row["expires_at"] < now

            links.append(
                ShareLinkResponse(
                    token=row["token"],
                    url=f"/s/{row['token']}",
                    full_url=get_full_url(row["token"]),
                    resource_type=row["resource_type"],
                    resource_id=row["resource_id"],
                    resource_title=resource_title,
                    expires_at=row["expires_at"],
                    access_count=row["access_count"],
                    created_at=row["created_at"],
                    created_by=row["created_by"],
                    is_expired=is_expired,
                )
            )

        return ShareLinkListResponse(links=links)


async def list_all_links() -> ShareLinkListResponse:
    """列出所有分享連結（管理員用）"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT token, resource_type, resource_id, created_by, expires_at, access_count, created_at
            FROM public_share_links
            ORDER BY created_at DESC
            """
        )

        now = datetime.now(timezone.utc)
        links = []

        for row in rows:
            # 取得資源標題
            try:
                resource_title = await get_resource_title(
                    row["resource_type"], row["resource_id"]
                )
            except ResourceNotFoundError:
                resource_title = "（已刪除）"

            # 判斷是否過期
            is_expired = False
            if row["expires_at"]:
                is_expired = row["expires_at"] < now

            links.append(
                ShareLinkResponse(
                    token=row["token"],
                    url=f"/s/{row['token']}",
                    full_url=get_full_url(row["token"]),
                    resource_type=row["resource_type"],
                    resource_id=row["resource_id"],
                    resource_title=resource_title,
                    expires_at=row["expires_at"],
                    access_count=row["access_count"],
                    created_at=row["created_at"],
                    created_by=row["created_by"],
                    is_expired=is_expired,
                )
            )

        return ShareLinkListResponse(links=links)


async def revoke_link(token: str, username: str, is_admin: bool = False) -> None:
    """撤銷分享連結

    Args:
        token: 連結 token
        username: 操作者用戶名
        is_admin: 是否為管理員（管理員可撤銷任何人的連結）
    """
    async with get_connection() as conn:
        # 檢查連結是否存在
        row = await conn.fetchrow(
            "SELECT created_by FROM public_share_links WHERE token = $1",
            token,
        )

        if not row:
            raise ShareLinkNotFoundError(f"連結 {token} 不存在")

        # 非管理員只能撤銷自己的連結
        if not is_admin and row["created_by"] != username:
            raise ShareError("您沒有權限撤銷此連結")

        # 刪除連結
        await conn.execute(
            "DELETE FROM public_share_links WHERE token = $1",
            token,
        )


async def get_public_resource(token: str) -> PublicResourceResponse:
    """取得公開資源"""
    async with get_connection() as conn:
        # 查詢連結
        row = await conn.fetchrow(
            """
            SELECT token, resource_type, resource_id, created_by, expires_at, created_at
            FROM public_share_links
            WHERE token = $1
            """,
            token,
        )

        if not row:
            raise ShareLinkNotFoundError("連結不存在或已被撤銷")

        # 檢查是否過期
        now = datetime.now(timezone.utc)
        if row["expires_at"] and row["expires_at"] < now:
            raise ShareLinkExpiredError("此連結已過期")

        # 更新存取次數（異步，不阻塞）
        await conn.execute(
            "UPDATE public_share_links SET access_count = access_count + 1 WHERE token = $1",
            token,
        )

        # 取得資源內容
        resource_type = row["resource_type"]
        resource_id = row["resource_id"]

        if resource_type == "knowledge":
            try:
                knowledge = get_knowledge(resource_id)
                # 正規化附件路徑，將 ../assets/images/xxx 轉換為 local/images/xxx
                normalized_attachments = []
                for att in knowledge.attachments:
                    att_dict = att.model_dump()
                    path = att_dict.get("path", "")
                    # 將 ../assets/ 轉換為 local/
                    if path.startswith("../assets/"):
                        att_dict["path"] = "local/" + path[len("../assets/"):]
                    normalized_attachments.append(att_dict)

                data = {
                    "id": knowledge.id,
                    "title": knowledge.title,
                    "content": knowledge.content,
                    "attachments": normalized_attachments,
                    "related": knowledge.related,
                    "created_at": knowledge.created_at.isoformat() if knowledge.created_at else None,
                    "updated_at": knowledge.updated_at.isoformat() if knowledge.updated_at else None,
                }
            except KnowledgeNotFoundError:
                raise ResourceNotFoundError("原始內容已被刪除")

        elif resource_type == "project":
            try:
                project = await get_project(UUID(resource_id))
                # 只顯示安全的資訊
                data = {
                    "id": str(project.id),
                    "name": project.name,
                    "description": project.description,
                    "status": project.status,
                    "start_date": project.start_date.isoformat() if project.start_date else None,
                    "end_date": project.end_date.isoformat() if project.end_date else None,
                    "milestones": [
                        {
                            "name": m.name,
                            "milestone_type": m.milestone_type,
                            "planned_date": m.planned_date.isoformat() if m.planned_date else None,
                            "actual_date": m.actual_date.isoformat() if m.actual_date else None,
                            "status": m.status,
                        }
                        for m in project.milestones
                    ],
                    "members": [
                        {"name": m.name, "role": m.role}
                        for m in project.members
                    ],
                }
            except ProjectNotFoundError:
                raise ResourceNotFoundError("原始內容已被刪除")

        elif resource_type == "nas_file":
            try:
                # 驗證檔案存在且可存取
                full_path = validate_nas_file_path(resource_id)
                stat = full_path.stat()

                # 格式化大小
                size = stat.st_size
                if size >= 1024 * 1024:
                    size_str = f"{size / 1024 / 1024:.2f} MB"
                elif size >= 1024:
                    size_str = f"{size / 1024:.2f} KB"
                else:
                    size_str = f"{size} bytes"

                # 回傳檔案資訊（實際下載透過另一個端點）
                data = {
                    "file_name": full_path.name,
                    "file_path": str(full_path),
                    "file_size": size,
                    "file_size_str": size_str,
                    "download_url": f"/api/public/{token}/download",
                }
            except (NasFileNotFoundError, NasFileAccessDenied) as e:
                raise ResourceNotFoundError(str(e))
            except Exception as e:
                raise ResourceNotFoundError(f"無法存取檔案：{e}")

        elif resource_type == "project_attachment":
            try:
                # 取得附件資訊（已包含 file_size）
                attachment = await get_project_attachment_info(resource_id)
                filename = attachment["filename"]
                size = attachment.get("file_size") or 0

                if size >= 1024 * 1024:
                    size_str = f"{size / 1024 / 1024:.2f} MB"
                elif size >= 1024:
                    size_str = f"{size / 1024:.2f} KB"
                elif size > 0:
                    size_str = f"{size} bytes"
                else:
                    size_str = "未知"

                # 回傳檔案資訊（實際下載透過 /download 端點）
                data = {
                    "file_name": filename,
                    "file_type": attachment.get("file_type", ""),
                    "file_size": size,
                    "file_size_str": size_str,
                    "download_url": f"/api/public/{token}/download",
                }
            except ResourceNotFoundError:
                raise
            except Exception as e:
                raise ResourceNotFoundError(f"無法存取附件：{e}")

        else:
            raise ShareError(f"不支援的資源類型：{resource_type}")

        return PublicResourceResponse(
            type=resource_type,
            data=data,
            shared_by=row["created_by"],
            shared_at=row["created_at"],
            expires_at=row["expires_at"],
        )


async def get_link_info(token: str) -> dict:
    """取得連結資訊（用於驗證附件存取權限）"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT token, resource_type, resource_id, expires_at
            FROM public_share_links
            WHERE token = $1
            """,
            token,
        )

        if not row:
            raise ShareLinkNotFoundError("連結不存在")

        # 檢查是否過期
        now = datetime.now(timezone.utc)
        if row["expires_at"] and row["expires_at"] < now:
            raise ShareLinkExpiredError("此連結已過期")

        return {
            "resource_type": row["resource_type"],
            "resource_id": row["resource_id"],
        }


async def cleanup_expired_links() -> int:
    """清理過期的分享連結

    刪除所有 expires_at < 當前時間 的連結。
    expires_at 為 NULL（永久連結）的不會被刪除。

    Returns:
        刪除的連結數量
    """
    async with get_connection() as conn:
        now = datetime.now(timezone.utc)
        result = await conn.execute(
            """
            DELETE FROM public_share_links
            WHERE expires_at IS NOT NULL AND expires_at < $1
            """,
            now,
        )
        # result 格式為 "DELETE N"
        deleted_count = int(result.split()[-1]) if result else 0
        return deleted_count
