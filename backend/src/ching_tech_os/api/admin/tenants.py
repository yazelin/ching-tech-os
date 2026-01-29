"""平台管理員租戶管理 API

供平台管理員（platform_admin）管理所有租戶。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ...models.auth import SessionData
from ...models.tenant import (
    TenantCreate,
    TenantInfo,
    TenantUpdate,
    TenantUsage,
    TenantListResponse,
    TenantAdminCreate,
    TenantAdminCreateResponse,
    TenantAdminInfo,
    TenantUserListResponse,
    LineBotSettingsUpdate,
    LineBotSettingsResponse,
    LineBotTestResponse,
)
from ...services.tenant import (
    create_tenant,
    get_tenant_by_id,
    update_tenant,
    delete_tenant,
    list_tenants,
    get_tenant_usage,
    add_tenant_admin,
    remove_tenant_admin,
    list_tenant_admins,
    list_tenant_users,
    TenantNotFoundError,
    TenantCodeExistsError,
    get_tenant_line_credentials,
    update_tenant_line_settings,
)
from ...services.linebot import invalidate_tenant_secrets_cache
from ..auth import get_current_session

router = APIRouter(prefix="/api/admin/tenants", tags=["admin-tenants"])


# === 輔助函數 ===


async def require_platform_admin(session: SessionData) -> SessionData:
    """要求平台管理員權限

    Raises:
        HTTPException: 若不是平台管理員
    """
    if session.role != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要平台管理員權限",
        )
    return session


# ============================================================
# Line 群組租戶管理（必須在 /{tenant_id} 路由之前定義）
# ============================================================


class LineGroupTenantUpdateRequest(BaseModel):
    """Line 群組租戶更新請求"""
    new_tenant_id: str


class LineGroupTenantResponse(BaseModel):
    """Line 群組租戶回應"""
    success: bool
    message: str
    group_id: str | None = None
    old_tenant_id: str | None = None
    new_tenant_id: str | None = None


@router.get("/line-groups")
async def list_all_bot_groups(
    limit: int = 50,
    offset: int = 0,
    tenant_id: str | None = None,
    session: SessionData = Depends(get_current_session),
):
    """列出所有 Line 群組（跨租戶）

    僅平台管理員可操作。
    可選擇性過濾特定租戶的群組。

    Args:
        limit: 最大數量
        offset: 偏移量
        tenant_id: 租戶 ID（可選，不指定則列出所有租戶的群組）
    """
    from uuid import UUID
    from ...database import get_connection

    await require_platform_admin(session)

    # 轉換 tenant_id 為 UUID
    tenant_uuid = None
    if tenant_id:
        try:
            tenant_uuid = UUID(tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="無效的租戶 ID 格式",
            )

    async with get_connection() as conn:
        if tenant_uuid:
            # 過濾特定租戶
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM bot_groups WHERE tenant_id = $1",
                tenant_uuid,
            )
            rows = await conn.fetch(
                """
                SELECT g.*, t.name as tenant_name
                FROM bot_groups g
                LEFT JOIN tenants t ON g.tenant_id = t.id
                WHERE g.tenant_id = $1
                ORDER BY g.updated_at DESC
                LIMIT $2 OFFSET $3
                """,
                tenant_uuid,
                limit,
                offset,
            )
        else:
            # 列出所有租戶的群組
            total = await conn.fetchval("SELECT COUNT(*) FROM bot_groups")
            rows = await conn.fetch(
                """
                SELECT g.*, t.name as tenant_name
                FROM bot_groups g
                LEFT JOIN tenants t ON g.tenant_id = t.id
                ORDER BY g.updated_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

        groups = []
        for row in rows:
            group = dict(row)
            # 轉換 UUID 為字串
            group["id"] = str(group["id"])
            group["tenant_id"] = str(group["tenant_id"])
            # 欄位名稱對應（前端使用 group_name）
            group["group_name"] = group.get("name")
            if group.get("project_id"):
                group["project_id"] = str(group["project_id"])
            # 轉換 datetime 為 ISO 字串
            if group.get("created_at"):
                group["created_at"] = group["created_at"].isoformat()
            if group.get("updated_at"):
                group["updated_at"] = group["updated_at"].isoformat()
            groups.append(group)

        return {
            "items": groups,
            "total": total,
        }


@router.patch("/line-groups/{group_id}/tenant")
async def update_line_group_tenant(
    group_id: str,
    request: LineGroupTenantUpdateRequest,
    session: SessionData = Depends(get_current_session),
) -> LineGroupTenantResponse:
    """更新 Line 群組的租戶

    將群組從一個租戶移動到另一個租戶。
    僅平台管理員可操作。

    Args:
        group_id: 群組 UUID
        request: 包含新租戶 ID 的請求

    Returns:
        更新結果
    """
    from uuid import UUID
    from ..linebot_router import get_group_by_id
    from ...services.linebot import update_group_tenant

    await require_platform_admin(session)

    try:
        group_uuid = UUID(group_id)
        new_tenant_uuid = UUID(request.new_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無效的 UUID 格式",
        )

    # 確認新租戶存在
    new_tenant = await get_tenant_by_id(request.new_tenant_id)
    if new_tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目標租戶不存在",
        )

    # 取得群組（不指定 tenant_id，平台管理員可以看到所有租戶的群組）
    # 需要直接查詢，因為 get_group_by_id 會過濾 tenant_id
    from ...database import get_connection

    async with get_connection() as conn:
        group = await conn.fetchrow(
            "SELECT id, tenant_id FROM bot_groups WHERE id = $1",
            group_uuid,
        )

    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="群組不存在",
        )

    old_tenant_id = str(group["tenant_id"])

    # 如果已經是目標租戶，直接返回成功
    if str(group["tenant_id"]) == request.new_tenant_id:
        return LineGroupTenantResponse(
            success=True,
            message="群組已屬於此租戶",
            group_id=group_id,
            old_tenant_id=old_tenant_id,
            new_tenant_id=request.new_tenant_id,
        )

    # 更新租戶
    success = await update_group_tenant(
        group_uuid,
        new_tenant_uuid,
        current_tenant_id=group["tenant_id"],
    )

    if success:
        return LineGroupTenantResponse(
            success=True,
            message="群組租戶已更新",
            group_id=group_id,
            old_tenant_id=old_tenant_id,
            new_tenant_id=request.new_tenant_id,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新失敗",
        )


# === 租戶 CRUD API ===


@router.get("", response_model=TenantListResponse)
async def list_all_tenants(
    status_filter: str | None = Query(None, alias="status"),
    plan: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: SessionData = Depends(get_current_session),
) -> TenantListResponse:
    """列出所有租戶

    僅平台管理員可操作。
    """
    await require_platform_admin(session)

    tenants, total = await list_tenants(
        status=status_filter,
        plan=plan,
        limit=limit,
        offset=offset,
    )

    return TenantListResponse(tenants=tenants, total=total)


@router.post("", response_model=TenantInfo, status_code=status.HTTP_201_CREATED)
async def create_new_tenant(
    request: TenantCreate,
    session: SessionData = Depends(get_current_session),
) -> TenantInfo:
    """建立新租戶

    僅平台管理員可操作。
    """
    await require_platform_admin(session)

    try:
        return await create_tenant(request)
    except TenantCodeExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get("/{tenant_id}", response_model=TenantInfo)
async def get_tenant(
    tenant_id: str,
    session: SessionData = Depends(get_current_session),
) -> TenantInfo:
    """取得單一租戶資訊

    僅平台管理員可操作。
    """
    await require_platform_admin(session)

    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    # 轉換為 TenantInfo
    import json
    from ...models.tenant import TenantSettings

    settings_data = tenant["settings"]
    if isinstance(settings_data, str):
        settings_data = json.loads(settings_data)
    elif settings_data is None:
        settings_data = {}

    return TenantInfo(
        id=tenant["id"],
        code=tenant["code"],
        name=tenant["name"],
        status=tenant["status"],
        plan=tenant["plan"],
        storage_quota_mb=tenant["storage_quota_mb"],
        storage_used_mb=tenant["storage_used_mb"] or 0,
        settings=TenantSettings(**settings_data),
        trial_ends_at=tenant["trial_ends_at"],
        created_at=tenant["created_at"],
        updated_at=tenant["updated_at"],
    )


@router.put("/{tenant_id}", response_model=TenantInfo)
async def update_tenant_info(
    tenant_id: str,
    request: TenantUpdate,
    session: SessionData = Depends(get_current_session),
) -> TenantInfo:
    """更新租戶資訊

    僅平台管理員可操作。可修改所有欄位。
    """
    await require_platform_admin(session)

    try:
        return await update_tenant(tenant_id, request)
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )


@router.get("/{tenant_id}/usage", response_model=TenantUsage)
async def get_tenant_usage_info(
    tenant_id: str,
    session: SessionData = Depends(get_current_session),
) -> TenantUsage:
    """取得租戶使用量統計

    僅平台管理員可操作。
    """
    await require_platform_admin(session)

    try:
        return await get_tenant_usage(tenant_id)
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )


# === 租戶狀態操作 ===


class SuspendResponse(BaseModel):
    """停用回應"""
    success: bool
    message: str


@router.post("/{tenant_id}/suspend", response_model=SuspendResponse)
async def suspend_tenant(
    tenant_id: str,
    session: SessionData = Depends(get_current_session),
) -> SuspendResponse:
    """停用租戶

    僅平台管理員可操作。
    """
    await require_platform_admin(session)

    try:
        await update_tenant(tenant_id, TenantUpdate(status="suspended"))
        return SuspendResponse(success=True, message="租戶已停用")
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )


@router.post("/{tenant_id}/activate", response_model=SuspendResponse)
async def activate_tenant(
    tenant_id: str,
    session: SessionData = Depends(get_current_session),
) -> SuspendResponse:
    """啟用租戶

    僅平台管理員可操作。
    """
    await require_platform_admin(session)

    try:
        await update_tenant(tenant_id, TenantUpdate(status="active"))
        return SuspendResponse(success=True, message="租戶已啟用")
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )


class DeleteTenantResponse(BaseModel):
    """刪除租戶回應"""
    success: bool
    message: str


@router.delete("/{tenant_id}", response_model=DeleteTenantResponse)
async def delete_tenant_by_id(
    tenant_id: str,
    session: SessionData = Depends(get_current_session),
) -> DeleteTenantResponse:
    """刪除租戶

    僅平台管理員可操作。

    警告：此操作不可逆！會刪除租戶的所有資料，包括：
    - 使用者帳號
    - 專案及相關資料
    - 知識庫
    - AI 設定和記錄
    - Line 群組和使用者綁定
    - 庫存資料
    """
    await require_platform_admin(session)

    try:
        await delete_tenant(tenant_id)
        return DeleteTenantResponse(success=True, message="租戶已刪除")
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )


# === 租戶管理員操作 ===


@router.get("/{tenant_id}/admins", response_model=list[TenantAdminInfo])
async def get_tenant_admins(
    tenant_id: str,
    session: SessionData = Depends(get_current_session),
) -> list[TenantAdminInfo]:
    """列出租戶管理員

    僅平台管理員可操作。
    """
    await require_platform_admin(session)

    # 確認租戶存在
    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    return await list_tenant_admins(tenant_id)


@router.get("/{tenant_id}/users", response_model=TenantUserListResponse)
async def list_tenant_users_by_platform(
    tenant_id: str,
    include_inactive: bool = Query(False, description="是否包含已停用的使用者"),
    session: SessionData = Depends(get_current_session),
) -> TenantUserListResponse:
    """列出租戶內的所有使用者

    僅平台管理員可操作。
    用於選擇要指派為管理員的使用者。
    """
    await require_platform_admin(session)

    # 確認租戶存在
    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    return await list_tenant_users(tenant_id, include_inactive)


@router.post("/{tenant_id}/admins", response_model=TenantAdminCreateResponse, status_code=status.HTTP_201_CREATED)
async def add_tenant_admin_by_platform(
    tenant_id: str,
    request: TenantAdminCreate,
    session: SessionData = Depends(get_current_session),
) -> TenantAdminCreateResponse:
    """新增租戶管理員

    僅平台管理員可操作。
    支援兩種模式：
    - 選擇現有使用者（提供 user_id）
    - 建立新帳號（提供 username，password 可選，不提供則自動產生）
    """
    await require_platform_admin(session)

    # 確認租戶存在
    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    try:
        return await add_tenant_admin(tenant_id, request)
    except ValueError as e:
        return TenantAdminCreateResponse(
            success=False,
            error=str(e),
        )


@router.delete("/{tenant_id}/admins/{user_id}", response_model=SuspendResponse)
async def remove_tenant_admin_by_platform(
    tenant_id: str,
    user_id: int,
    delete_user: bool = Query(False, description="是否同時刪除使用者帳號"),
    session: SessionData = Depends(get_current_session),
) -> SuspendResponse:
    """移除租戶管理員

    僅平台管理員可操作。

    Query Parameters:
        delete_user: 是否同時刪除使用者帳號（預設 False）
    """
    await require_platform_admin(session)

    # 確認租戶存在
    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    success = await remove_tenant_admin(tenant_id, user_id, delete_user=delete_user)
    if success:
        message = "已移除管理員並刪除帳號" if delete_user else "已移除管理員"
        return SuspendResponse(success=True, message=message)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理員不存在",
        )


# ============================================================
# Line Bot 設定 API
# ============================================================


@router.get("/{tenant_id}/linebot", response_model=LineBotSettingsResponse)
async def get_tenant_linebot_settings(
    tenant_id: str,
    session: SessionData = Depends(get_current_session),
) -> LineBotSettingsResponse:
    """取得租戶 Line Bot 設定

    僅平台管理員可操作。
    回傳設定狀態，不包含敏感憑證。
    """
    await require_platform_admin(session)

    # 確認租戶存在
    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    # 取得 Line Bot 憑證（解密後）
    credentials = await get_tenant_line_credentials(tenant_id)

    if credentials:
        return LineBotSettingsResponse(
            configured=True,
            channel_id=credentials.get("channel_id"),
        )
    else:
        return LineBotSettingsResponse(
            configured=False,
            channel_id=None,
        )


@router.put("/{tenant_id}/linebot", response_model=LineBotSettingsResponse)
async def update_tenant_linebot_settings(
    tenant_id: str,
    request: LineBotSettingsUpdate,
    session: SessionData = Depends(get_current_session),
) -> LineBotSettingsResponse:
    """更新租戶 Line Bot 設定

    僅平台管理員可操作。
    更新 Line Bot 憑證（會自動加密儲存）。
    """
    await require_platform_admin(session)

    # 確認租戶存在
    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    # 更新設定
    success = await update_tenant_line_settings(
        tenant_id,
        channel_id=request.channel_id,
        channel_secret=request.channel_secret,
        access_token=request.access_token,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新失敗",
        )

    # 清除租戶 secrets 快取（讓新設定立即生效）
    invalidate_tenant_secrets_cache()

    # 取得更新後的設定
    credentials = await get_tenant_line_credentials(tenant_id)

    return LineBotSettingsResponse(
        configured=bool(credentials),
        channel_id=credentials.get("channel_id") if credentials else None,
    )


@router.post("/{tenant_id}/linebot/test", response_model=LineBotTestResponse)
async def test_tenant_linebot(
    tenant_id: str,
    session: SessionData = Depends(get_current_session),
) -> LineBotTestResponse:
    """測試租戶 Line Bot 憑證

    僅平台管理員可操作。
    使用租戶的憑證呼叫 Line API 確認設定是否正確。
    """
    from uuid import UUID
    from linebot.v3.messaging import AsyncApiClient, AsyncMessagingApi, Configuration

    await require_platform_admin(session)

    # 確認租戶存在
    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    # 取得 Line Bot 憑證
    credentials = await get_tenant_line_credentials(tenant_id)

    if not credentials:
        return LineBotTestResponse(
            success=False,
            error="尚未設定 Line Bot 憑證",
        )

    access_token = credentials.get("access_token")
    if not access_token:
        return LineBotTestResponse(
            success=False,
            error="缺少 Access Token",
        )

    # 測試憑證
    try:
        config = Configuration(access_token=access_token)
        async with AsyncApiClient(config) as api_client:
            api = AsyncMessagingApi(api_client)
            bot_info = await api.get_bot_info()

            return LineBotTestResponse(
                success=True,
                bot_info={
                    "display_name": bot_info.display_name,
                    "basic_id": bot_info.basic_id,
                    "premium_id": bot_info.premium_id,
                    "chat_mode": bot_info.chat_mode,
                },
            )
    except Exception as e:
        return LineBotTestResponse(
            success=False,
            error=str(e),
        )


@router.delete("/{tenant_id}/linebot", response_model=SuspendResponse)
async def delete_tenant_linebot_settings(
    tenant_id: str,
    session: SessionData = Depends(get_current_session),
) -> SuspendResponse:
    """清除租戶 Line Bot 設定

    僅平台管理員可操作。
    清除所有 Line Bot 憑證。
    """
    await require_platform_admin(session)

    # 確認租戶存在
    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    # 清除設定（傳入空值）
    success = await update_tenant_line_settings(
        tenant_id,
        channel_id=None,
        channel_secret=None,
        access_token=None,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="清除失敗",
        )

    # 清除租戶 secrets 快取
    invalidate_tenant_secrets_cache()

    return SuspendResponse(success=True, message="Line Bot 設定已清除")


# ============================================================
# NAS 認證設定 API
# ============================================================


class NasAuthTestRequest(BaseModel):
    """NAS 認證測試請求"""
    host: str | None = None  # None 使用系統預設
    port: int | None = None  # None 使用 445
    share: str | None = None  # None 使用系統預設


class NasAuthTestResponse(BaseModel):
    """NAS 認證測試回應"""
    success: bool
    message: str | None = None
    error: str | None = None


@router.post("/{tenant_id}/nas-auth/test", response_model=NasAuthTestResponse)
async def test_tenant_nas_auth(
    tenant_id: str,
    request: NasAuthTestRequest,
    session: SessionData = Depends(get_current_session),
) -> NasAuthTestResponse:
    """測試 NAS 認證連線

    僅平台管理員可操作。
    使用系統服務帳號測試指定的 NAS 主機/共享是否可連線。
    """
    from ...services.smb import create_smb_service, SMBAuthError, SMBConnectionError
    from ...config import settings

    await require_platform_admin(session)

    # 確認租戶存在
    tenant = await get_tenant_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    # 使用系統服務帳號測試連線
    try:
        smb = create_smb_service(
            settings.nas_user,
            settings.nas_password,
            host=request.host,
            port=request.port,
            share=request.share,
        )
        smb.test_auth()
        return NasAuthTestResponse(
            success=True,
            message="NAS 連線測試成功",
        )
    except SMBAuthError as e:
        return NasAuthTestResponse(
            success=False,
            error=f"認證失敗：{e}",
        )
    except SMBConnectionError as e:
        return NasAuthTestResponse(
            success=False,
            error=f"連線失敗：{e}",
        )
