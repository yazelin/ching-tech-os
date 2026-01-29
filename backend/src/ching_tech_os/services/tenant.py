"""租戶服務"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from uuid import UUID

from ..config import settings, DEFAULT_TENANT_UUID
from .path_manager import path_manager
from ..database import get_connection
from ..models.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantInfo,
    TenantBrief,
    TenantSettings,
    TenantUsage,
    TenantAdminCreate,
    TenantAdminCreateResponse,
    TenantAdminInfo,
    TenantUserBrief,
    TenantUserListResponse,
)
from ..utils.crypto import encrypt_credential, decrypt_credential
from .password import hash_password, generate_temporary_password

logger = logging.getLogger(__name__)


class TenantNotFoundError(Exception):
    """租戶不存在"""
    pass


class TenantCodeExistsError(Exception):
    """租戶代碼已存在"""
    pass


class TenantSuspendedError(Exception):
    """租戶已停用"""
    pass


async def get_tenant_by_code(code: str) -> dict | None:
    """根據租戶代碼取得租戶資料

    Args:
        code: 租戶代碼（用於登入識別）

    Returns:
        租戶資料或 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, code, name, status, plan, settings,
                   storage_quota_mb, storage_used_mb, trial_ends_at,
                   created_at, updated_at
            FROM tenants
            WHERE code = $1
            """,
            code,
        )
        if row:
            return dict(row)
        return None


async def get_tenant_by_id(tenant_id: UUID | str) -> dict | None:
    """根據租戶 ID 取得租戶資料

    Args:
        tenant_id: 租戶 UUID

    Returns:
        租戶資料或 None
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, code, name, status, plan, settings,
                   storage_quota_mb, storage_used_mb, trial_ends_at,
                   created_at, updated_at
            FROM tenants
            WHERE id = $1
            """,
            tenant_id,
        )
        if row:
            return dict(row)
        return None


async def get_default_tenant() -> dict:
    """取得預設租戶（單租戶模式使用）

    Returns:
        預設租戶資料

    Raises:
        TenantNotFoundError: 預設租戶不存在（資料庫未正確初始化）
    """
    tenant = await get_tenant_by_id(DEFAULT_TENANT_UUID)
    if tenant is None:
        raise TenantNotFoundError("預設租戶不存在，請確認資料庫已正確初始化")
    return tenant


async def resolve_tenant_id(tenant_code: str | None = None) -> UUID:
    """解析租戶 ID

    多租戶模式：根據 tenant_code 解析
    單租戶模式：回傳預設租戶 ID

    Args:
        tenant_code: 租戶代碼（可選）

    Returns:
        租戶 UUID

    Raises:
        TenantNotFoundError: 租戶不存在
        TenantSuspendedError: 租戶已停用
    """
    if not settings.multi_tenant_mode:
        # 單租戶模式，回傳預設租戶
        return UUID(settings.default_tenant_id)

    if not tenant_code:
        # 多租戶模式未提供 tenant_code，使用預設
        return UUID(settings.default_tenant_id)

    tenant = await get_tenant_by_code(tenant_code)
    if tenant is None:
        raise TenantNotFoundError(f"租戶代碼 '{tenant_code}' 不存在")

    if tenant["status"] == "suspended":
        raise TenantSuspendedError(f"租戶 '{tenant_code}' 已被停用")

    return tenant["id"]


async def get_tenant_settings(tenant_id: UUID | str) -> TenantSettings:
    """取得租戶設定

    Args:
        tenant_id: 租戶 UUID

    Returns:
        TenantSettings 物件

    Raises:
        TenantNotFoundError: 租戶不存在
    """
    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise TenantNotFoundError(f"租戶 {tenant_id} 不存在")

    settings_data = tenant.get("settings", {})
    if isinstance(settings_data, str):
        settings_data = json.loads(settings_data)
    elif settings_data is None:
        settings_data = {}

    return TenantSettings(**settings_data)


async def create_tenant(data: TenantCreate) -> TenantInfo:
    """建立新租戶

    建立租戶時會自動從預設租戶複製 AI Agents 和 Prompts 設定。

    Args:
        data: 建立租戶請求資料

    Returns:
        新建的租戶資訊

    Raises:
        TenantCodeExistsError: 租戶代碼已存在
    """
    async with get_connection() as conn:
        # 檢查代碼是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM tenants WHERE code = $1",
            data.code,
        )
        if existing:
            raise TenantCodeExistsError(f"租戶代碼 '{data.code}' 已存在")

        # 計算試用結束時間
        trial_ends_at = None
        if data.trial_days:
            trial_ends_at = datetime.now() + timedelta(days=data.trial_days)

        # 預設設定
        default_settings = TenantSettings()

        now = datetime.now()
        row = await conn.fetchrow(
            """
            INSERT INTO tenants (code, name, status, plan, settings,
                               storage_quota_mb, trial_ends_at, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
            RETURNING id, code, name, status, plan, settings,
                      storage_quota_mb, storage_used_mb, trial_ends_at,
                      created_at, updated_at
            """,
            data.code,
            data.name,
            "trial" if data.trial_days else "active",
            data.plan,
            json.dumps(default_settings.model_dump()),
            data.storage_quota_mb,
            trial_ends_at,
            now,
        )

        new_tenant_id = row["id"]

        # 從預設租戶複製 AI Agents（包含關聯的 Prompts）
        await _copy_default_ai_settings(conn, new_tenant_id)

        logger.info(f"已建立租戶 {data.code} ({new_tenant_id})，並複製預設 AI 設定")

        return _row_to_tenant_info(row)


async def update_tenant(tenant_id: UUID | str, data: TenantUpdate) -> TenantInfo:
    """更新租戶資訊

    Args:
        tenant_id: 租戶 UUID
        data: 更新請求資料

    Returns:
        更新後的租戶資訊

    Raises:
        TenantNotFoundError: 租戶不存在
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        # 取得現有資料
        existing = await conn.fetchrow(
            "SELECT * FROM tenants WHERE id = $1",
            tenant_id,
        )
        if existing is None:
            raise TenantNotFoundError(f"租戶 {tenant_id} 不存在")

        # 建立更新欄位
        updates = []
        params = [tenant_id]
        param_idx = 2

        if data.name is not None:
            updates.append(f"name = ${param_idx}")
            params.append(data.name)
            param_idx += 1

        if data.status is not None:
            updates.append(f"status = ${param_idx}")
            params.append(data.status)
            param_idx += 1

        if data.plan is not None:
            updates.append(f"plan = ${param_idx}")
            params.append(data.plan)
            param_idx += 1

        if data.storage_quota_mb is not None:
            updates.append(f"storage_quota_mb = ${param_idx}")
            params.append(data.storage_quota_mb)
            param_idx += 1

        if data.settings is not None:
            updates.append(f"settings = ${param_idx}")
            # 加密 Line Bot 憑證後儲存
            settings_dict = data.settings.model_dump()
            settings_dict = _encrypt_settings_credentials(settings_dict)
            params.append(json.dumps(settings_dict))
            param_idx += 1

        if not updates:
            # 沒有要更新的欄位
            return _row_to_tenant_info(existing)

        updates.append("updated_at = NOW()")

        query = f"""
            UPDATE tenants
            SET {", ".join(updates)}
            WHERE id = $1
            RETURNING id, code, name, status, plan, settings,
                      storage_quota_mb, storage_used_mb, trial_ends_at,
                      created_at, updated_at
        """

        row = await conn.fetchrow(query, *params)
        return _row_to_tenant_info(row)


async def delete_tenant(tenant_id: UUID | str) -> bool:
    """刪除租戶及其所有資料

    警告：此操作不可逆！會刪除租戶的所有資料。

    大部分關聯資料會透過資料庫的 ON DELETE CASCADE 機制自動刪除。
    僅分區表（ai_logs, messages, login_records）因無法設定外鍵需手動刪除。

    Args:
        tenant_id: 租戶 UUID

    Returns:
        True 如果刪除成功

    Raises:
        TenantNotFoundError: 租戶不存在
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        # 確認租戶存在
        existing = await conn.fetchrow(
            "SELECT code, name FROM tenants WHERE id = $1",
            tenant_id,
        )
        if existing is None:
            raise TenantNotFoundError(f"租戶 {tenant_id} 不存在")

        tenant_code = existing["code"]
        tenant_name = existing["name"]

        logger.warning(f"開始刪除租戶 {tenant_code} ({tenant_name})，ID: {tenant_id}")

        # 使用交易確保一致性
        async with conn.transaction():
            # 手動刪除分區表資料（分區表無法設定外鍵，不支援 CASCADE）
            await conn.execute(
                "DELETE FROM ai_logs WHERE tenant_id = $1", tenant_id
            )
            await conn.execute(
                "DELETE FROM messages WHERE tenant_id = $1", tenant_id
            )
            await conn.execute(
                "DELETE FROM login_records WHERE tenant_id = $1", tenant_id
            )

            # 刪除租戶本身，其他關聯表會透過 ON DELETE CASCADE 自動刪除
            await conn.execute(
                "DELETE FROM tenants WHERE id = $1", tenant_id
            )

        logger.warning(f"已刪除租戶 {tenant_code} ({tenant_name})，ID: {tenant_id}")
        return True


async def list_tenants(
    status: str | None = None,
    plan: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TenantInfo], int]:
    """列出所有租戶

    Args:
        status: 狀態篩選
        plan: 方案篩選
        limit: 最大數量
        offset: 偏移量

    Returns:
        (租戶列表, 總數)
    """
    async with get_connection() as conn:
        conditions = []
        params = []
        param_idx = 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if plan:
            conditions.append(f"plan = ${param_idx}")
            params.append(plan)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # 計算總數
        count_query = f"SELECT COUNT(*) FROM tenants {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # 取得資料
        params.extend([limit, offset])
        data_query = f"""
            SELECT id, code, name, status, plan, settings,
                   storage_quota_mb, storage_used_mb, trial_ends_at,
                   created_at, updated_at
            FROM tenants
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """

        rows = await conn.fetch(data_query, *params)
        tenants = [_row_to_tenant_info(row) for row in rows]

        return tenants, total


def _calculate_directory_size(path: str) -> int:
    """計算目錄大小（同步函數）

    Args:
        path: 目錄路徑

    Returns:
        目錄大小（bytes）
    """
    total_size = 0
    try:
        if not os.path.exists(path):
            return 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    pass
    except (OSError, PermissionError) as e:
        logger.warning(f"計算目錄大小失敗 {path}: {e}")
    return total_size


async def calculate_tenant_storage(tenant_id: UUID | str) -> int:
    """計算租戶儲存空間使用量

    掃描租戶目錄下所有檔案，計算總大小。

    Args:
        tenant_id: 租戶 UUID

    Returns:
        儲存空間使用量（MB）
    """
    tid_str = str(tenant_id)
    tenant_base_path = path_manager.get_tenant_base_path(tid_str)

    # 在執行緒池中執行同步的目錄掃描
    loop = asyncio.get_event_loop()
    total_bytes = await loop.run_in_executor(
        None, _calculate_directory_size, tenant_base_path
    )

    # 轉換為 MB
    return total_bytes // (1024 * 1024)


async def get_tenant_usage(tenant_id: UUID | str) -> TenantUsage:
    """取得租戶使用量統計

    Args:
        tenant_id: 租戶 UUID

    Returns:
        使用量統計
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        # 取得租戶基本資訊
        tenant = await conn.fetchrow(
            "SELECT storage_quota_mb, storage_used_mb FROM tenants WHERE id = $1",
            tenant_id,
        )
        if tenant is None:
            raise TenantNotFoundError(f"租戶 {tenant_id} 不存在")

        # 統計使用者數量
        user_count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE tenant_id = $1",
            tenant_id,
        )

        # 統計專案數量
        project_count = await conn.fetchval(
            "SELECT COUNT(*) FROM projects WHERE tenant_id = $1",
            tenant_id,
        )

        # 統計知識庫數量（從檔案系統計算，這裡暫時回傳 0）
        knowledge_count = 0

        # 統計今日 AI 呼叫次數
        ai_calls_today = await conn.fetchval(
            """
            SELECT COUNT(*) FROM ai_logs
            WHERE tenant_id = $1 AND created_at >= CURRENT_DATE
            """,
            tenant_id,
        )

        # 統計本月 AI 呼叫次數
        ai_calls_month = await conn.fetchval(
            """
            SELECT COUNT(*) FROM ai_logs
            WHERE tenant_id = $1 AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
            """,
            tenant_id,
        )

        # 動態計算儲存空間使用量
        storage_used = await calculate_tenant_storage(tenant_id)
        storage_quota = tenant["storage_quota_mb"] or 1

        return TenantUsage(
            tenant_id=tenant_id,
            storage_used_mb=storage_used,
            storage_quota_mb=storage_quota,
            storage_percentage=round(storage_used / max(storage_quota, 1) * 100, 2),
            user_count=user_count or 0,
            project_count=project_count or 0,
            knowledge_count=knowledge_count,
            ai_calls_today=ai_calls_today or 0,
            ai_calls_this_month=ai_calls_month or 0,
        )


# === 租戶管理員 ===


async def add_tenant_admin(
    tenant_id: UUID | str,
    data: TenantAdminCreate,
) -> TenantAdminCreateResponse:
    """新增租戶管理員

    支援兩種模式：
    1. 選擇現有使用者（提供 user_id）
    2. 建立新帳號（提供 username，password 可選）

    Args:
        tenant_id: 租戶 UUID
        data: 管理員資料

    Returns:
        建立結果（包含可能的臨時密碼）
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    temporary_password = None
    user_id = data.user_id
    username = None
    display_name = None

    async with get_connection() as conn:
        # 模式一：選擇現有使用者
        if user_id is not None:
            user = await conn.fetchrow(
                "SELECT id, username, display_name FROM users WHERE id = $1 AND tenant_id = $2",
                user_id,
                tenant_id,
            )
            if user is None:
                raise ValueError(f"使用者 {user_id} 不存在或不屬於此租戶")
            username = user["username"]
            display_name = user["display_name"]

        # 模式二：建立新帳號
        elif data.username:
            username = data.username
            display_name = data.display_name or data.username

            # 檢查帳號是否已存在
            existing_user = await conn.fetchrow(
                "SELECT id FROM users WHERE username = $1 AND tenant_id = $2",
                data.username,
                tenant_id,
            )
            if existing_user:
                raise ValueError(f"帳號 {data.username} 已存在")

            # 處理密碼
            if data.password:
                password_hash = hash_password(data.password)
                must_change = data.must_change_password
            else:
                # 自動產生臨時密碼
                temporary_password = generate_temporary_password()
                password_hash = hash_password(temporary_password)
                must_change = True

            # 建立使用者
            now = datetime.now()
            user_row = await conn.fetchrow(
                """
                INSERT INTO users (
                    username, display_name, password_hash, must_change_password,
                    tenant_id, role, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                data.username,
                display_name,
                password_hash,
                must_change,
                tenant_id,
                "tenant_admin",
                now,
            )
            user_id = user_row["id"]

        else:
            raise ValueError("必須提供 user_id 或 username")

        # 檢查是否已是管理員
        existing = await conn.fetchrow(
            "SELECT id FROM tenant_admins WHERE tenant_id = $1 AND user_id = $2",
            tenant_id,
            user_id,
        )
        if existing:
            raise ValueError(f"使用者已是此租戶的管理員")

        # 新增管理員記錄
        now = datetime.now()
        row = await conn.fetchrow(
            """
            INSERT INTO tenant_admins (tenant_id, user_id, role, created_at)
            VALUES ($1, $2, $3, $4)
            RETURNING id, tenant_id, user_id, role, created_at
            """,
            tenant_id,
            user_id,
            data.role,
            now,
        )

        admin_info = TenantAdminInfo(
            id=row["id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            role=row["role"],
            username=username,
            display_name=display_name,
            created_at=row["created_at"],
        )

        return TenantAdminCreateResponse(
            success=True,
            admin=admin_info,
            temporary_password=temporary_password,
        )


async def remove_tenant_admin(
    tenant_id: UUID | str, user_id: int, delete_user: bool = False
) -> bool:
    """移除租戶管理員

    Args:
        tenant_id: 租戶 UUID
        user_id: 使用者 ID
        delete_user: 是否同時刪除使用者帳號

    Returns:
        是否成功移除
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        # 先刪除 tenant_admins 記錄
        result = await conn.execute(
            "DELETE FROM tenant_admins WHERE tenant_id = $1 AND user_id = $2",
            tenant_id,
            user_id,
        )
        admin_deleted = "DELETE 1" in result

        if not admin_deleted:
            return False

        # 如果需要同時刪除使用者帳號
        if delete_user:
            await conn.execute(
                "DELETE FROM users WHERE id = $1 AND tenant_id = $2",
                user_id,
                tenant_id,
            )
            logger.info(f"已刪除使用者帳號 user_id={user_id}, tenant_id={tenant_id}")

        return True


async def list_tenant_admins(tenant_id: UUID | str) -> list[TenantAdminInfo]:
    """列出租戶管理員

    Args:
        tenant_id: 租戶 UUID

    Returns:
        管理員列表
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT ta.id, ta.tenant_id, ta.user_id, ta.role, ta.created_at,
                   u.username, u.display_name
            FROM tenant_admins ta
            JOIN users u ON ta.user_id = u.id
            WHERE ta.tenant_id = $1
            ORDER BY ta.created_at
            """,
            tenant_id,
        )

        return [
            TenantAdminInfo(
                id=row["id"],
                tenant_id=row["tenant_id"],
                user_id=row["user_id"],
                role=row["role"],
                username=row["username"],
                display_name=row["display_name"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


async def list_tenant_users(
    tenant_id: UUID | str, include_inactive: bool = False
) -> TenantUserListResponse:
    """列出租戶內的所有使用者

    供平台管理員查詢，用於選擇要指派為管理員的使用者。

    Args:
        tenant_id: 租戶 UUID
        include_inactive: 是否包含已停用的使用者

    Returns:
        使用者列表
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        # 查詢使用者，同時檢查是否已是管理員
        query = """
            SELECT u.id, u.username, u.display_name, u.role, u.is_active,
                   CASE WHEN ta.id IS NOT NULL THEN true ELSE false END as is_admin
            FROM users u
            LEFT JOIN tenant_admins ta ON u.id = ta.user_id AND ta.tenant_id = $1
            WHERE u.tenant_id = $1
        """
        if not include_inactive:
            query += " AND u.is_active = true"
        query += " ORDER BY u.username"

        rows = await conn.fetch(query, tenant_id)

        users = [
            TenantUserBrief(
                id=row["id"],
                username=row["username"],
                display_name=row["display_name"],
                role=row["role"] or "user",
                is_admin=row["is_admin"],
            )
            for row in rows
        ]

        return TenantUserListResponse(users=users)


async def is_tenant_admin(tenant_id: UUID | str, user_id: int) -> bool:
    """檢查使用者是否為租戶管理員

    Args:
        tenant_id: 租戶 UUID
        user_id: 使用者 ID

    Returns:
        是否為管理員
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM tenant_admins WHERE tenant_id = $1 AND user_id = $2",
            tenant_id,
            user_id,
        )
        return row is not None


async def get_tenant_admin_role(tenant_id: UUID | str, user_id: int) -> str | None:
    """取得使用者的租戶管理員角色

    Args:
        tenant_id: 租戶 UUID
        user_id: 使用者 ID

    Returns:
        角色（admin/owner）或 None
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT role FROM tenant_admins WHERE tenant_id = $1 AND user_id = $2",
            tenant_id,
            user_id,
        )
        return row["role"] if row else None


# === 輔助函數 ===


def _row_to_tenant_info(row, decrypt_secrets: bool = False) -> TenantInfo:
    """將資料庫列轉換為 TenantInfo

    Args:
        row: 資料庫列
        decrypt_secrets: 是否解密 Line Bot 憑證（預設 False，API 回應不需要）
    """
    settings_data = row["settings"]
    if isinstance(settings_data, str):
        settings_data = json.loads(settings_data)
    elif settings_data is None:
        settings_data = {}

    # 解密 Line Bot 憑證（如果需要）
    if decrypt_secrets:
        settings_data = _decrypt_settings_credentials(settings_data)
    else:
        # 不回傳加密的憑證，只回傳是否已設定
        settings_data = _mask_settings_credentials(settings_data)

    return TenantInfo(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        status=row["status"],
        plan=row["plan"],
        storage_quota_mb=row["storage_quota_mb"],
        storage_used_mb=row["storage_used_mb"] or 0,
        settings=TenantSettings(**settings_data),
        trial_ends_at=row["trial_ends_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_tenant_brief(row) -> TenantBrief:
    """將資料庫列轉換為 TenantBrief"""
    return TenantBrief(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        status=row["status"],
        plan=row["plan"],
    )


def _encrypt_settings_credentials(settings_dict: dict) -> dict:
    """加密 settings 中的 Bot 憑證（Line + Telegram）"""
    result = settings_dict.copy()

    if result.get("line_channel_secret"):
        result["line_channel_secret"] = encrypt_credential(result["line_channel_secret"])

    if result.get("line_channel_access_token"):
        result["line_channel_access_token"] = encrypt_credential(result["line_channel_access_token"])

    if result.get("telegram_bot_token"):
        result["telegram_bot_token"] = encrypt_credential(result["telegram_bot_token"])

    return result


def _decrypt_settings_credentials(settings_dict: dict) -> dict:
    """解密 settings 中的 Bot 憑證（Line + Telegram）"""
    result = settings_dict.copy()

    if result.get("line_channel_secret"):
        try:
            result["line_channel_secret"] = decrypt_credential(result["line_channel_secret"])
        except ValueError as e:
            logger.warning(f"解密 line_channel_secret 失敗: {e}")
            result["line_channel_secret"] = None

    if result.get("line_channel_access_token"):
        try:
            result["line_channel_access_token"] = decrypt_credential(result["line_channel_access_token"])
        except ValueError as e:
            logger.warning(f"解密 line_channel_access_token 失敗: {e}")
            result["line_channel_access_token"] = None

    if result.get("telegram_bot_token"):
        try:
            result["telegram_bot_token"] = decrypt_credential(result["telegram_bot_token"])
        except ValueError as e:
            logger.warning(f"解密 telegram_bot_token 失敗: {e}")
            result["telegram_bot_token"] = None

    return result


def _mask_settings_credentials(settings_dict: dict) -> dict:
    """遮蔽 settings 中的 Bot 憑證（用於 API 回應）

    憑證欄位會被設為 None，但會新增 has_xxx 欄位表示是否已設定
    """
    result = settings_dict.copy()

    # 記錄是否已設定（之後可在 API 回應中使用）
    # 注意：這裡只是清除敏感資料，不回傳加密後的值
    result["line_channel_secret"] = None
    result["line_channel_access_token"] = None
    result["telegram_bot_token"] = None

    return result


# === Line Bot 憑證專用函數 ===


async def get_tenant_line_credentials(tenant_id: UUID | str) -> dict | None:
    """取得租戶的 Line Bot 憑證（解密後）

    用於 Webhook 驗證和發送訊息。

    Args:
        tenant_id: 租戶 UUID

    Returns:
        包含 channel_id, channel_secret, access_token 的字典，或 None
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT settings FROM tenants WHERE id = $1",
            tenant_id,
        )
        if row is None:
            return None

        settings_data = row["settings"]
        if isinstance(settings_data, str):
            settings_data = json.loads(settings_data)
        elif settings_data is None:
            return None

        # 解密憑證
        channel_id = settings_data.get("line_channel_id")
        channel_secret = settings_data.get("line_channel_secret")
        access_token = settings_data.get("line_channel_access_token")

        if not channel_secret or not access_token:
            return None

        try:
            return {
                "channel_id": channel_id,
                "channel_secret": decrypt_credential(channel_secret),
                "access_token": decrypt_credential(access_token),
            }
        except ValueError as e:
            logger.warning(f"解密租戶 {tenant_id} 的 Line Bot 憑證失敗: {e}")
            return None


async def get_all_tenant_line_secrets() -> list[dict]:
    """取得所有已設定 Line Bot 的租戶的 channel_secret

    用於 Webhook 多租戶驗證。

    Returns:
        包含 tenant_id, channel_id, channel_secret 的列表
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, settings
            FROM tenants
            WHERE status != 'suspended'
              AND settings->>'line_channel_secret' IS NOT NULL
              AND settings->>'line_channel_secret' != ''
            """
        )

        results = []
        for row in rows:
            settings_data = row["settings"]
            if isinstance(settings_data, str):
                settings_data = json.loads(settings_data)

            channel_secret = settings_data.get("line_channel_secret")
            if channel_secret:
                try:
                    results.append({
                        "tenant_id": row["id"],
                        "channel_id": settings_data.get("line_channel_id"),
                        "channel_secret": decrypt_credential(channel_secret),
                    })
                except ValueError as e:
                    logger.warning(f"解密租戶 {row['id']} 的 Line Bot secret 失敗: {e}")

        return results


async def update_tenant_line_settings(
    tenant_id: UUID | str,
    channel_id: str | None,
    channel_secret: str | None,
    access_token: str | None,
) -> bool:
    """更新租戶的 Line Bot 設定

    Args:
        tenant_id: 租戶 UUID
        channel_id: Line Channel ID
        channel_secret: Line Channel Secret（明文，會被加密儲存）
        access_token: Line Access Token（明文，會被加密儲存）

    Returns:
        是否成功更新
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        # 取得現有 settings
        row = await conn.fetchrow(
            "SELECT settings FROM tenants WHERE id = $1",
            tenant_id,
        )
        if row is None:
            return False

        settings_data = row["settings"]
        if isinstance(settings_data, str):
            settings_data = json.loads(settings_data)
        elif settings_data is None:
            settings_data = {}

        # 更新 Line Bot 設定
        settings_data["line_channel_id"] = channel_id

        if channel_secret:
            settings_data["line_channel_secret"] = encrypt_credential(channel_secret)
        else:
            settings_data["line_channel_secret"] = None

        if access_token:
            settings_data["line_channel_access_token"] = encrypt_credential(access_token)
        else:
            settings_data["line_channel_access_token"] = None

        # 儲存
        await conn.execute(
            """
            UPDATE tenants
            SET settings = $2, updated_at = NOW()
            WHERE id = $1
            """,
            tenant_id,
            json.dumps(settings_data),
        )

        return True


# === Telegram Bot 憑證專用函數 ===


async def get_tenant_telegram_credentials(tenant_id: UUID | str) -> dict | None:
    """取得租戶的 Telegram Bot 憑證（解密後）

    Args:
        tenant_id: 租戶 UUID

    Returns:
        包含 bot_token, admin_chat_id 的字典，或 None
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT settings FROM tenants WHERE id = $1",
            tenant_id,
        )
        if row is None:
            return None

        settings_data = row["settings"]
        if isinstance(settings_data, str):
            settings_data = json.loads(settings_data)
        elif settings_data is None:
            return None

        bot_token = settings_data.get("telegram_bot_token")
        admin_chat_id = settings_data.get("telegram_admin_chat_id")

        if not bot_token:
            return None

        try:
            return {
                "bot_token": decrypt_credential(bot_token),
                "admin_chat_id": admin_chat_id,
            }
        except ValueError as e:
            logger.warning(f"解密租戶 {tenant_id} 的 Telegram Bot 憑證失敗: {e}")
            return None


async def update_tenant_telegram_settings(
    tenant_id: UUID | str,
    bot_token: str | None,
    admin_chat_id: str | None,
) -> bool:
    """更新租戶的 Telegram Bot 設定

    Args:
        tenant_id: 租戶 UUID
        bot_token: Telegram Bot Token（明文，會被加密儲存）
        admin_chat_id: 管理員 Chat ID

    Returns:
        是否成功更新
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT settings FROM tenants WHERE id = $1",
            tenant_id,
        )
        if row is None:
            return False

        settings_data = row["settings"]
        if isinstance(settings_data, str):
            settings_data = json.loads(settings_data)
        elif settings_data is None:
            settings_data = {}

        # 更新 Telegram Bot 設定
        if bot_token:
            settings_data["telegram_bot_token"] = encrypt_credential(bot_token)
        else:
            settings_data["telegram_bot_token"] = None

        settings_data["telegram_admin_chat_id"] = admin_chat_id

        await conn.execute(
            """
            UPDATE tenants
            SET settings = $2, updated_at = NOW()
            WHERE id = $1
            """,
            tenant_id,
            json.dumps(settings_data),
        )

        return True


async def _copy_default_ai_settings(conn, new_tenant_id: UUID) -> None:
    """從預設租戶複製 AI 設定到新租戶

    複製項目：
    - AI Agents（linebot-group, linebot-personal 等）
    - AI Prompts（Agent 使用的 system prompts）

    注意：新租戶的 Agents 會引用預設租戶的 Prompts，
    這樣可以讓所有租戶共享相同的 prompt 模板。
    租戶可以之後建立自己的 prompts 並更新 agent 設定。

    Args:
        conn: 資料庫連線
        new_tenant_id: 新租戶 UUID
    """
    # 複製預設租戶的 AI Agents
    # system_prompt_id 保留指向預設租戶的 prompts（共享）
    await conn.execute(
        """
        INSERT INTO ai_agents (
            name, display_name, description, model,
            system_prompt_id, is_active, settings, tools, tenant_id
        )
        SELECT
            name, display_name, description, model,
            system_prompt_id, is_active, settings, tools, $1
        FROM ai_agents
        WHERE tenant_id = $2
          AND name IN ('linebot-group', 'linebot-personal')
        """,
        new_tenant_id,
        DEFAULT_TENANT_UUID,
    )

    logger.debug(f"已為租戶 {new_tenant_id} 複製預設 AI Agents")
