"""租戶服務"""

import json
from datetime import datetime, timedelta
from uuid import UUID

from ..config import settings, DEFAULT_TENANT_UUID
from ..database import get_connection
from ..models.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantInfo,
    TenantBrief,
    TenantSettings,
    TenantUsage,
    TenantAdminCreate,
    TenantAdminInfo,
)


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


async def create_tenant(data: TenantCreate) -> TenantInfo:
    """建立新租戶

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
            params.append(json.dumps(data.settings.model_dump()))
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

        storage_used = tenant["storage_used_mb"] or 0
        storage_quota = tenant["storage_quota_mb"] or 1

        return TenantUsage(
            tenant_id=tenant_id,
            storage_used_mb=storage_used,
            storage_quota_mb=storage_quota,
            storage_percentage=round(storage_used / storage_quota * 100, 2),
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
) -> TenantAdminInfo:
    """新增租戶管理員

    Args:
        tenant_id: 租戶 UUID
        data: 管理員資料

    Returns:
        管理員資訊
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        # 檢查使用者是否存在且屬於該租戶
        user = await conn.fetchrow(
            "SELECT id, username, display_name FROM users WHERE id = $1 AND tenant_id = $2",
            data.user_id,
            tenant_id,
        )
        if user is None:
            raise ValueError(f"使用者 {data.user_id} 不存在或不屬於此租戶")

        # 檢查是否已是管理員
        existing = await conn.fetchrow(
            "SELECT id FROM tenant_admins WHERE tenant_id = $1 AND user_id = $2",
            tenant_id,
            data.user_id,
        )
        if existing:
            raise ValueError(f"使用者 {data.user_id} 已是此租戶的管理員")

        now = datetime.now()
        row = await conn.fetchrow(
            """
            INSERT INTO tenant_admins (tenant_id, user_id, role, created_at)
            VALUES ($1, $2, $3, $4)
            RETURNING id, tenant_id, user_id, role, created_at
            """,
            tenant_id,
            data.user_id,
            data.role,
            now,
        )

        return TenantAdminInfo(
            id=row["id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            role=row["role"],
            username=user["username"],
            display_name=user["display_name"],
            created_at=row["created_at"],
        )


async def remove_tenant_admin(tenant_id: UUID | str, user_id: int) -> bool:
    """移除租戶管理員

    Args:
        tenant_id: 租戶 UUID
        user_id: 使用者 ID

    Returns:
        是否成功移除
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM tenant_admins WHERE tenant_id = $1 AND user_id = $2",
            tenant_id,
            user_id,
        )
        return "DELETE 1" in result


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


def _row_to_tenant_info(row) -> TenantInfo:
    """將資料庫列轉換為 TenantInfo"""
    settings_data = row["settings"]
    if isinstance(settings_data, str):
        settings_data = json.loads(settings_data)
    elif settings_data is None:
        settings_data = {}

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
