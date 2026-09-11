"""公開分享連結服務"""

import secrets
import string
import bcrypt
from dataclasses import dataclass, replace
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
    PasswordRequiredResponse,
)
from .knowledge import get_knowledge, KnowledgeNotFoundError

# 密碼錯誤最大嘗試次數
MAX_PASSWORD_ATTEMPTS = 5

# 讀不到的資源不能分享（issue #205）
SHARE_ACCESS_DENIED_MESSAGE = "您沒有讀取此資源的權限，無法建立分享連結"


from .errors import ServiceError


class NasFileNotFoundError(ServiceError):
    """NAS 檔案不存在"""

    def __init__(self, message: str = "NAS 檔案不存在"):
        super().__init__(message, "NOT_FOUND", 404)


class NasFileAccessDenied(ServiceError):
    """NAS 檔案存取被拒絕"""

    def __init__(self, message: str = "NAS 檔案存取被拒絕"):
        super().__init__(message, "PERMISSION_DENIED", 403)


class ShareError(ServiceError):
    """分享連結操作錯誤"""

    def __init__(self, message: str = "分享連結操作錯誤"):
        super().__init__(message, "SHARE_ERROR", 500)


class ShareLinkNotFoundError(ShareError):
    """連結不存在"""

    def __init__(self, message: str = "連結不存在"):
        super().__init__(message)
        self.code = "NOT_FOUND"
        self.status_code = 404


class ShareLinkExpiredError(ShareError):
    """連結已過期"""

    def __init__(self, message: str = "連結已過期"):
        super().__init__(message)
        self.code = "SHARE_EXPIRED"
        self.status_code = 410


class ShareLinkLockedError(ShareError):
    """連結已鎖定（密碼錯誤次數過多）"""

    def __init__(self, message: str = "連結已鎖定"):
        super().__init__(message)
        self.code = "SHARE_LOCKED"
        self.status_code = 423


class PasswordRequiredError(ShareError):
    """需要密碼"""

    def __init__(self, message: str = "需要密碼"):
        super().__init__(message)
        self.code = "PASSWORD_REQUIRED"
        self.status_code = 401


class PasswordIncorrectError(ShareError):
    """密碼錯誤"""

    def __init__(self, message: str = "密碼錯誤"):
        super().__init__(message)
        self.code = "PASSWORD_INCORRECT"
        self.status_code = 401


class ResourceNotFoundError(ShareError):
    """資源不存在"""

    def __init__(self, message: str = "資源不存在"):
        super().__init__(message)
        self.code = "NOT_FOUND"
        self.status_code = 404


class ShareAccessDenied(ShareError):
    """沒有權限把這個資源變成公開連結（issue #205）"""

    def __init__(self, message: str = SHARE_ACCESS_DENIED_MESSAGE):
        super().__init__(message)
        self.code = "PERMISSION_DENIED"
        self.status_code = 403


def generate_token(length: int = 6) -> str:
    """產生隨機 token

    使用加密安全的隨機產生器
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_password(length: int = 4) -> str:
    """產生隨機數字密碼

    使用加密安全的隨機產生器，只使用數字方便手機輸入
    預設 4 位數，與前端 UI 一致
    """
    return "".join(secrets.choice(string.digits) for _ in range(length))


def hash_password(password: str) -> str:
    """使用 bcrypt 加密密碼"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """驗證密碼"""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


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


def validate_nas_file_path(
    file_path: str,
    source_permissions: dict[str, bool] | None = None,
) -> Path:
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
    from .shared_source_permissions import SharedSourceAccessDeniedError

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

        try:
            full_path = Path(
                path_manager.to_filesystem(
                    file_path,
                    source_permissions=source_permissions,
                )
            )
        except SharedSourceAccessDeniedError as e:
            raise NasFileAccessDenied(str(e)) from e
        except ValueError as e:
            raise NasFileAccessDenied(f"無效的路徑：{e}") from e

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


# ============================================================
# 建立連結前的資源存取檢查（issue #205）
# ============================================================


@dataclass(frozen=True)
class ShareActor:
    """要建立分享連結的人。

    REST 用 `from_session()`（session 已經有 username／role），MCP 用
    `from_ctos_user_id()`（身分由 `resolve_ctos_user_id()` 從伺服器注入的環境變數
    取得，模型帶什麼都不算數）。兩條路徑共用 `check_resource_access()`。

    `username`／`role`／`preferences`／`source_permissions` 沒給的話會在真的要用到
    時才查（content 類型的連結完全不需要查）。
    """

    user_id: int | None = None
    username: str | None = None
    role: str | None = None
    preferences: dict | None = None
    source_permissions: dict[str, bool] | None = None
    is_bound: bool = False

    @classmethod
    def from_session(cls, session) -> "ShareActor":
        """從網頁 session 建立（已登入＝已綁定）。"""
        return cls(
            user_id=getattr(session, "user_id", None),
            username=getattr(session, "username", None),
            role=getattr(session, "role", None) or "user",
            is_bound=True,
        )

    @classmethod
    def from_ctos_user_id(
        cls,
        ctos_user_id: int | None,
        source_permissions: dict[str, bool] | None = None,
    ) -> "ShareActor":
        """從 MCP 工具的 `ctos_user_id` 建立；None＝未綁定。"""
        if ctos_user_id is None:
            return cls(source_permissions=source_permissions)
        return cls(
            user_id=ctos_user_id,
            source_permissions=source_permissions,
            is_bound=True,
        )


async def _resolve_source_permissions(ctos_user_id: int | None) -> dict[str, bool]:
    """取得使用者可存取的 shared 子來源（與 `read_document`／`send_nas_file` 同一條路）。"""
    from .path_manager import path_manager
    from .shared_source_permissions import get_allowed_shared_mounts_for_user

    mounts = await get_allowed_shared_mounts_for_user(
        path_manager.get_shared_mounts(),
        ctos_user_id,
    )
    return {name: True for name in mounts}


async def _resolve_actor(actor: ShareActor) -> ShareActor | None:
    """補齊 username／role／preferences；帳號已不存在時回 None（等同未綁定）。"""
    if actor.username is not None and actor.role is not None and actor.preferences is not None:
        return actor

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT username, role, preferences FROM users WHERE id = $1",
            actor.user_id,
        )
    if row is None:
        return None

    from .user import _parse_preferences

    return replace(
        actor,
        username=actor.username or row["username"],
        role=actor.role or (row["role"] or "user"),
        preferences=_parse_preferences(row["preferences"]),
    )


async def check_resource_access(
    resource_type: str,
    resource_id: str,
    actor: ShareActor | None = None,
) -> None:
    """建立分享連結前的資源存取檢查（REST 與 MCP 共用這一層）。

    `get_resource_title()` 只驗「資源存在」，所以原本任何呼叫者都能把別人的知識
    條目或讀不到的 NAS 檔案變成公開連結（issue #205）。這裡做的是真正的存取檢查，
    而且刻意走與「讀」完全相同的路：

    - `knowledge`：與 `knowledge_tools.get_knowledge_item` 的條目層級同一條路——
      已綁定走 `check_knowledge_permission_async(..., action="read")`
      （personal 只有 owner、project 要成員、global 依權限），
      未綁定只放行 `scope=global` 且 `is_public`。
    - `nas_file`：與 `read_document`／`send_nas_file` 同一條路——
      `validate_nas_file_path(..., source_permissions=...)`，未綁定一律拒絕。
    - `content`：內容由呼叫端自己提供，沒有「別人的資源」可洩漏，不檢查。

    Raises:
        ResourceNotFoundError: 資源不存在
        ShareAccessDenied: 讀不到就不能分享
    """
    if resource_type == "content":
        return

    actor = actor if actor is not None else ShareActor()

    if resource_type == "knowledge":
        try:
            item = get_knowledge(resource_id)
        except KnowledgeNotFoundError:
            raise ResourceNotFoundError(f"資源 knowledge/{resource_id} 不存在")

        if not actor.is_bound:
            # 未綁定：與未綁定讀取知識庫的範圍一致，只有公開的全域條目
            if item.scope == "global" and getattr(item, "is_public", False):
                return
            raise ShareAccessDenied(SHARE_ACCESS_DENIED_MESSAGE)

        resolved = await _resolve_actor(actor)
        if resolved is None:
            # 帳號已不存在＝等同未綁定
            raise ShareAccessDenied(SHARE_ACCESS_DENIED_MESSAGE)

        from .permissions import check_knowledge_permission_async

        allowed = await check_knowledge_permission_async(
            resolved.role or "user",
            resolved.username,
            resolved.preferences,
            item.owner,
            item.scope,
            "read",
            user_id=resolved.user_id,
            project_id=getattr(item, "project_id", None),
        )
        if not allowed:
            raise ShareAccessDenied(
                f"您沒有讀取 {resource_id} 的權限，無法建立分享連結"
            )
        return

    if resource_type == "nas_file":
        if not actor.is_bound:
            raise ShareAccessDenied(SHARE_ACCESS_DENIED_MESSAGE)

        source_permissions = actor.source_permissions
        if source_permissions is None:
            source_permissions = await _resolve_source_permissions(actor.user_id)

        try:
            validate_nas_file_path(resource_id, source_permissions=source_permissions)
        except NasFileNotFoundError as e:
            raise ResourceNotFoundError(str(e))
        except NasFileAccessDenied as e:
            raise ShareAccessDenied(str(e))
        return

    # project／project_attachment：新前端的專案分享不走這支，公開端也不支援這些類型
    raise ShareAccessDenied(f"不支援分享的資源類型：{resource_type}")


async def get_resource_title(resource_type: str, resource_id: str, filename: str | None = None) -> str:
    """取得資源標題"""
    from uuid import UUID as UUIDType
    try:
        if resource_type == "knowledge":
            knowledge = get_knowledge(resource_id)
            return knowledge.title
        elif resource_type == "nas_file":
            # 驗證路徑並回傳檔名
            full_path = validate_nas_file_path(resource_id)
            return full_path.name
        elif resource_type == "content":
            # content 類型使用 filename 或預設標題
            return filename or "分享內容"
        else:
            return "未知資源"
    except KnowledgeNotFoundError:
        raise ResourceNotFoundError(f"資源 {resource_type}/{resource_id} 不存在")
    except NasFileNotFoundError as e:
        raise ResourceNotFoundError(str(e))
    except NasFileAccessDenied as e:
        raise ResourceNotFoundError(str(e))


async def create_share_link(
    data: ShareLinkCreate,
    created_by: str,
    actor: ShareActor | None = None,
) -> ShareLinkResponse:
    """建立分享連結

    Args:
        data: 分享連結資料
        created_by: 建立者用戶名
        actor: 建立者身分，用來做資源存取檢查（issue #205）。
            不給＝當成未綁定處理（最嚴格的那一檔），不是略過檢查。
    """
    # content 類型驗證
    if data.resource_type == "content":
        if not data.content:
            raise ShareError("content 類型必須提供 content 參數")
        resource_title = data.filename or "分享內容"
    else:
        # 存取檢查：讀不到的資源不能變成公開連結
        await check_resource_access(data.resource_type, data.resource_id, actor)
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

        # 處理密碼
        password_raw = None
        password_hashed = None
        if data.password:
            # 如果提供密碼，使用提供的密碼
            password_raw = data.password
            password_hashed = hash_password(password_raw)
        elif data.resource_type == "content":
            # content 類型預設產生密碼
            password_raw = generate_password()
            password_hashed = hash_password(password_raw)

        # 儲存到資料庫
        now = datetime.now(timezone.utc)
        row = await conn.fetchrow(
            """
            INSERT INTO public_share_links
            (token, resource_type, resource_id, created_by, expires_at, created_at,
             content, content_type, filename, password_hash)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id, token, resource_type, resource_id, created_by, expires_at, access_count, created_at
            """,
            token,
            data.resource_type,
            data.resource_id or "",
            created_by,
            expires_at,
            now,
            data.content if data.resource_type == "content" else None,
            data.content_type if data.resource_type == "content" else None,
            data.filename if data.resource_type == "content" else None,
            password_hashed,
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
            has_password=password_hashed is not None,
            password=password_raw,  # 僅建立時回傳
        )


async def list_my_links(username: str) -> ShareLinkListResponse:
    """列出使用者的分享連結

    Args:
        username: 用戶名
    """
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


async def get_public_resource(token: str, password: str | None = None) -> PublicResourceResponse | PasswordRequiredResponse:
    """取得公開資源

    Args:
        token: 分享連結 token
        password: 密碼（如果連結有密碼保護）

    Returns:
        PublicResourceResponse: 資源內容
        PasswordRequiredResponse: 需要密碼（401）

    Raises:
        ShareLinkNotFoundError: 連結不存在
        ShareLinkExpiredError: 連結已過期
        ShareLinkLockedError: 連結已鎖定
        PasswordIncorrectError: 密碼錯誤
    """
    async with get_connection() as conn:
        # 查詢連結（包含密碼相關欄位）
        row = await conn.fetchrow(
            """
            SELECT token, resource_type, resource_id, created_by, expires_at, created_at,
                   content, content_type, filename, password_hash, attempt_count, locked_at
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

        # 檢查是否鎖定
        if row["locked_at"]:
            raise ShareLinkLockedError("此連結因密碼錯誤次數過多而被鎖定")

        # 密碼驗證
        if row["password_hash"]:
            if not password:
                # 需要密碼但未提供
                return PasswordRequiredResponse(
                    requires_password=True,
                    message="此連結需要密碼才能存取",
                    is_locked=False,
                )

            if not verify_password(password, row["password_hash"]):
                # 密碼錯誤，增加嘗試次數
                new_attempt_count = row["attempt_count"] + 1
                if new_attempt_count >= MAX_PASSWORD_ATTEMPTS:
                    # 鎖定連結
                    await conn.execute(
                        """
                        UPDATE public_share_links
                        SET attempt_count = $1, locked_at = $2
                        WHERE token = $3
                        """,
                        new_attempt_count,
                        now,
                        token,
                    )
                    raise ShareLinkLockedError("密碼錯誤次數過多，連結已被鎖定")
                else:
                    await conn.execute(
                        """
                        UPDATE public_share_links
                        SET attempt_count = $1
                        WHERE token = $2
                        """,
                        new_attempt_count,
                        token,
                    )
                    raise PasswordIncorrectError(f"密碼錯誤，還剩 {MAX_PASSWORD_ATTEMPTS - new_attempt_count} 次嘗試機會")

            # 密碼正確，重設嘗試次數
            if row["attempt_count"] > 0:
                await conn.execute(
                    """
                    UPDATE public_share_links
                    SET attempt_count = 0
                    WHERE token = $1
                    """,
                    token,
                )

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

        elif resource_type == "content":
            # 直接儲存的內容
            data = {
                "content": row["content"],
                "content_type": row["content_type"] or "text/plain",
                "filename": row["filename"] or "content.txt",
            }

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
