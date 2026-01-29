"""租戶自助服務 API

供租戶管理員管理自己的租戶設定。
"""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import settings
from ..models.auth import SessionData
from ..models.tenant import (
    TenantInfo,
    TenantUpdate,
    TenantUsage,
    TenantAdminCreate,
    TenantAdminInfo,
    TenantSettings,
    TenantExportRequest,
    TenantExportResponse,
    TenantImportRequest,
)
from ..services.tenant import (
    get_tenant_by_id,
    update_tenant,
    get_tenant_usage,
    add_tenant_admin,
    remove_tenant_admin,
    list_tenant_admins,
    is_tenant_admin,
    TenantNotFoundError,
)
from ..services.user import (
    create_user,
    list_tenant_users,
    get_user_detail,
    update_user_info,
    reset_user_password,
    deactivate_user,
    activate_user,
)
from ..services.password import hash_password, generate_temporary_password
from ..services.tenant_data import (
    export_tenant_data,
    import_tenant_data,
    validate_tenant_data,
)
from .auth import get_current_session, can_manage_user

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


# === 輔助函數 ===


async def require_tenant_admin(session: SessionData) -> SessionData:
    """要求租戶管理員權限

    Raises:
        HTTPException: 若不是租戶管理員
    """
    if session.role not in ("tenant_admin", "platform_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要租戶管理員權限",
        )
    return session


# === 租戶資訊 API ===


@router.get("/info", response_model=TenantInfo)
async def get_tenant_info(
    session: SessionData = Depends(get_current_session),
) -> TenantInfo:
    """取得目前租戶資訊

    任何登入使用者都可以查看自己租戶的基本資訊。
    """
    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    tenant = await get_tenant_by_id(session.tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    # 將資料轉換為 TenantInfo
    import json
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


@router.get("/usage", response_model=TenantUsage)
async def get_usage(
    session: SessionData = Depends(get_current_session),
) -> TenantUsage:
    """取得租戶使用量統計

    任何登入使用者都可以查看。
    """
    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    try:
        return await get_tenant_usage(session.tenant_id)
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )


# === 租戶設定 API（需要管理員權限）===


class UpdateTenantSettingsRequest(BaseModel):
    """更新租戶設定請求"""
    name: str | None = None
    settings: TenantSettings | None = None


@router.put("/settings", response_model=TenantInfo)
async def update_tenant_settings(
    request: UpdateTenantSettingsRequest,
    session: SessionData = Depends(get_current_session),
) -> TenantInfo:
    """更新租戶設定

    僅租戶管理員可操作。只能修改名稱和設定，不能修改 plan、status 等。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    try:
        # 只允許修改名稱和設定
        update_data = TenantUpdate(
            name=request.name,
            settings=request.settings,
        )
        return await update_tenant(session.tenant_id, update_data)
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )


# === 租戶管理員 API ===


@router.get("/admins", response_model=list[TenantAdminInfo])
async def get_admins(
    session: SessionData = Depends(get_current_session),
) -> list[TenantAdminInfo]:
    """列出租戶管理員

    僅租戶管理員可查看。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    return await list_tenant_admins(session.tenant_id)


@router.post("/admins", response_model=TenantAdminInfo, status_code=status.HTTP_201_CREATED)
async def add_admin(
    request: TenantAdminCreate,
    session: SessionData = Depends(get_current_session),
) -> TenantAdminInfo:
    """新增租戶管理員

    僅租戶管理員可操作。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    try:
        return await add_tenant_admin(session.tenant_id, request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


class RemoveAdminResponse(BaseModel):
    """移除管理員回應"""
    success: bool
    message: str


@router.delete("/admins/{user_id}", response_model=RemoveAdminResponse)
async def remove_admin(
    user_id: int,
    session: SessionData = Depends(get_current_session),
) -> RemoveAdminResponse:
    """移除租戶管理員

    僅租戶管理員可操作。不能移除自己。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 不能移除自己
    if session.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除自己的管理員身份",
        )

    success = await remove_tenant_admin(session.tenant_id, user_id)
    if success:
        return RemoveAdminResponse(success=True, message="已移除管理員")
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理員不存在",
        )


# === 資料匯出/匯入 API ===


@router.post("/export")
async def export_data(
    request: TenantExportRequest,
    session: SessionData = Depends(get_current_session),
) -> StreamingResponse:
    """匯出租戶資料

    匯出租戶的所有資料（資料庫 + 檔案）為 ZIP 檔案。
    僅租戶管理員可操作。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    try:
        zip_content, summary = await export_tenant_data(
            session.tenant_id,
            include_files=request.include_files,
            include_ai_logs=request.include_ai_logs,
        )

        # 取得租戶資訊作為檔名
        tenant = await get_tenant_by_id(session.tenant_id)
        tenant_code = tenant["code"] if tenant else "tenant"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{tenant_code}_export_{timestamp}.zip"

        return StreamingResponse(
            iter([zip_content]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(zip_content)),
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"匯出失敗: {str(e)}",
        )


class ImportResponse(BaseModel):
    """匯入回應"""
    success: bool
    message: str
    summary: dict


@router.post("/import", response_model=ImportResponse)
async def import_data(
    file: UploadFile = File(...),
    merge_mode: str = "replace",
    session: SessionData = Depends(get_current_session),
) -> ImportResponse:
    """匯入租戶資料

    從 ZIP 檔案匯入租戶資料。
    僅租戶管理員可操作。

    Args:
        file: ZIP 檔案
        merge_mode: 合併模式（replace: 取代現有資料, merge: 合併）
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 驗證檔案類型
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請上傳 ZIP 檔案",
        )

    # 驗證合併模式
    if merge_mode not in ("replace", "merge"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="合併模式必須是 replace 或 merge",
        )

    try:
        # 讀取上傳的檔案內容
        zip_content = await file.read()

        # 執行匯入
        summary = await import_tenant_data(
            session.tenant_id,
            zip_content,
            merge_mode=merge_mode,
        )

        # 檢查是否有錯誤
        errors = summary.get("errors", [])
        if errors:
            return ImportResponse(
                success=True,
                message=f"匯入完成，但有 {len(errors)} 個錯誤",
                summary=summary,
            )

        return ImportResponse(
            success=True,
            message="匯入完成",
            summary=summary,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"匯入失敗: {str(e)}",
        )


class ValidateResponse(BaseModel):
    """驗證回應"""
    success: bool
    message: str
    result: dict


@router.get("/validate", response_model=ValidateResponse)
async def validate_data(
    session: SessionData = Depends(get_current_session),
) -> ValidateResponse:
    """驗證租戶資料完整性

    檢查租戶資料的完整性，包括資料庫記錄和檔案系統。
    僅租戶管理員可操作。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    try:
        result = await validate_tenant_data(session.tenant_id)

        errors = result.get("errors", [])
        warnings = result.get("warnings", [])

        if errors:
            return ValidateResponse(
                success=False,
                message=f"驗證失敗: {len(errors)} 個錯誤",
                result=result,
            )
        elif warnings:
            return ValidateResponse(
                success=True,
                message=f"驗證通過，但有 {len(warnings)} 個警告",
                result=result,
            )
        else:
            return ValidateResponse(
                success=True,
                message="驗證通過",
                result=result,
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"驗證失敗: {str(e)}",
        )


# === 使用者管理 API（需要租戶管理員權限）===


class UserInfo(BaseModel):
    """使用者資訊"""
    id: int
    username: str
    display_name: str | None = None
    email: str | None = None
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None
    # 允許額外欄位（preferences, tenant_id 等）被忽略
    model_config = {"extra": "ignore"}


class CreateUserRequest(BaseModel):
    """建立使用者請求"""
    username: str
    display_name: str | None = None
    email: str | None = None
    role: str = "user"  # user 或 tenant_admin
    password: str | None = None  # 若不提供，會自動產生臨時密碼
    must_change_password: bool = True  # 首次登入是否需變更密碼


class CreateUserResponse(BaseModel):
    """建立使用者回應"""
    success: bool
    user: UserInfo | None = None
    temporary_password: str | None = None  # 自動產生的臨時密碼
    error: str | None = None


class UpdateUserRequest(BaseModel):
    """更新使用者請求"""
    display_name: str | None = None
    email: str | None = None
    role: str | None = None  # user 或 tenant_admin


class UserListResponse(BaseModel):
    """使用者列表回應"""
    users: list[UserInfo]
    total: int


class ResetPasswordRequest(BaseModel):
    """重設密碼請求"""
    new_password: str | None = None  # 若不提供，會自動產生


class ResetPasswordResponse(BaseModel):
    """重設密碼回應"""
    success: bool
    temporary_password: str | None = None
    error: str | None = None


class ToggleUserResponse(BaseModel):
    """啟用/停用使用者回應"""
    success: bool
    message: str


@router.get("/users", response_model=UserListResponse)
async def list_users(
    include_inactive: bool = False,
    session: SessionData = Depends(get_current_session),
) -> UserListResponse:
    """列出租戶的所有使用者

    僅租戶管理員可操作。

    Args:
        include_inactive: 是否包含停用的使用者
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    users = await list_tenant_users(session.tenant_id, include_inactive)

    return UserListResponse(
        users=[UserInfo(**u) for u in users],
        total=len(users),
    )


@router.post("/users", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    request: CreateUserRequest,
    session: SessionData = Depends(get_current_session),
) -> CreateUserResponse:
    """建立新使用者

    僅租戶管理員可操作。
    若未提供密碼，會自動產生臨時密碼，使用者首次登入時需要變更。

    Args:
        request: 建立使用者請求
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 驗證角色
    if request.role not in ("user", "tenant_admin"):
        return CreateUserResponse(
            success=False,
            error="角色必須是 user 或 tenant_admin",
        )

    # 處理密碼
    temporary_password = None
    if request.password:
        password_hash = hash_password(request.password)
        must_change = request.must_change_password
    else:
        temporary_password = generate_temporary_password()
        password_hash = hash_password(temporary_password)
        must_change = True  # 自動產生的密碼一定要變更

    try:
        user_id = await create_user(
            username=request.username,
            tenant_id=session.tenant_id,
            password_hash=password_hash,
            display_name=request.display_name,
            email=request.email,
            role=request.role,
            must_change_password=must_change,
        )

        # 取得完整使用者資料
        user_data = await get_user_detail(user_id, session.tenant_id)
        if user_data is None:
            return CreateUserResponse(
                success=False,
                error="建立使用者失敗",
            )

        return CreateUserResponse(
            success=True,
            user=UserInfo(**user_data),
            temporary_password=temporary_password,
        )

    except ValueError as e:
        return CreateUserResponse(
            success=False,
            error=str(e),
        )
    except Exception as e:
        # 記錄詳細錯誤以便除錯
        import logging
        logging.exception(f"建立使用者失敗: {e}")
        return CreateUserResponse(
            success=False,
            error=f"建立使用者失敗: {str(e)}",
        )


@router.get("/users/{user_id}", response_model=UserInfo)
async def get_user(
    user_id: int,
    session: SessionData = Depends(get_current_session),
) -> UserInfo:
    """取得使用者詳細資料

    僅租戶管理員可操作。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    user_data = await get_user_detail(user_id, session.tenant_id)
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    return UserInfo(**user_data)


@router.patch("/users/{user_id}", response_model=UserInfo)
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    session: SessionData = Depends(get_current_session),
) -> UserInfo:
    """更新使用者資料

    僅租戶管理員可操作。
    權限階層：platform_admin > tenant_admin > user
    租戶管理員只能修改一般使用者的資料。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 先取得目標使用者資料，檢查權限階層
    target_user = await get_user_detail(user_id, session.tenant_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    # 權限階層檢查
    target_role = target_user.get("role", "user")
    if not can_manage_user(session.role, target_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限操作此使用者",
        )

    # 如果要變更角色，檢查新角色是否在允許範圍內
    if request.role is not None:
        # 租戶管理員不能將使用者設為 platform_admin
        if request.role == "platform_admin" and session.role != "platform_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權限設定此角色",
            )
        # 租戶管理員不能將使用者設為 tenant_admin（除非自己是 platform_admin）
        if request.role == "tenant_admin" and session.role == "tenant_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="租戶管理員無法指派新的租戶管理員，請使用租戶管理員新增功能",
            )

    try:
        user_data = await update_user_info(
            user_id=user_id,
            tenant_id=session.tenant_id,
            display_name=request.display_name,
            email=request.email,
            role=request.role,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    return UserInfo(**user_data)


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    user_id: int,
    request: ResetPasswordRequest,
    session: SessionData = Depends(get_current_session),
) -> ResetPasswordResponse:
    """重設使用者密碼

    僅租戶管理員可操作。
    若未提供新密碼，會自動產生臨時密碼。
    權限階層：租戶管理員只能重設一般使用者的密碼。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 先取得目標使用者資料，檢查權限階層
    target_user = await get_user_detail(user_id, session.tenant_id)
    if target_user is None:
        return ResetPasswordResponse(
            success=False,
            error="使用者不存在",
        )

    # 權限階層檢查
    target_role = target_user.get("role", "user")
    if not can_manage_user(session.role, target_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限操作此使用者",
        )

    # 處理密碼
    temporary_password = None
    if request.new_password:
        password_hash = hash_password(request.new_password)
        must_change = False
    else:
        temporary_password = generate_temporary_password()
        password_hash = hash_password(temporary_password)
        must_change = True

    success = await reset_user_password(
        user_id=user_id,
        tenant_id=session.tenant_id,
        new_password_hash=password_hash,
        must_change=must_change,
    )

    if not success:
        return ResetPasswordResponse(
            success=False,
            error="使用者不存在",
        )

    return ResetPasswordResponse(
        success=True,
        temporary_password=temporary_password,
    )


@router.post("/users/{user_id}/deactivate", response_model=ToggleUserResponse)
async def deactivate_user_endpoint(
    user_id: int,
    session: SessionData = Depends(get_current_session),
) -> ToggleUserResponse:
    """停用使用者帳號

    僅租戶管理員可操作。不能停用自己。
    權限階層：租戶管理員只能停用一般使用者。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 不能停用自己
    if session.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能停用自己的帳號",
        )

    # 驗證使用者屬於該租戶
    user_data = await get_user_detail(user_id, session.tenant_id)
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    # 權限階層檢查
    target_role = user_data.get("role", "user")
    if not can_manage_user(session.role, target_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限操作此使用者",
        )

    success = await deactivate_user(user_id)
    if success:
        return ToggleUserResponse(success=True, message="帳號已停用")
    else:
        return ToggleUserResponse(success=False, message="停用失敗")


@router.post("/users/{user_id}/activate", response_model=ToggleUserResponse)
async def activate_user_endpoint(
    user_id: int,
    session: SessionData = Depends(get_current_session),
) -> ToggleUserResponse:
    """啟用使用者帳號

    僅租戶管理員可操作。
    權限階層：租戶管理員只能啟用一般使用者。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 驗證使用者屬於該租戶
    user_data = await get_user_detail(user_id, session.tenant_id)
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    # 權限階層檢查
    target_role = user_data.get("role", "user")
    if not can_manage_user(session.role, target_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限操作此使用者",
        )

    success = await activate_user(user_id)
    if success:
        return ToggleUserResponse(success=True, message="帳號已啟用")
    else:
        return ToggleUserResponse(success=False, message="啟用失敗")


# ============================================================
# NAS 登入驗證設定 API
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


# ============================================================
# Line Bot 設定 API
# ============================================================


class LineBotSettingsUpdate(BaseModel):
    """更新 Line Bot 設定請求"""
    channel_id: str | None = None
    channel_secret: str | None = None
    access_token: str | None = None


class LineBotSettingsResponse(BaseModel):
    """Line Bot 設定回應（不包含敏感資訊）"""
    configured: bool
    channel_id: str | None = None


class LineBotTestResponse(BaseModel):
    """Line Bot 測試回應"""
    success: bool
    bot_info: dict | None = None
    error: str | None = None


class LineBotDeleteResponse(BaseModel):
    """Line Bot 刪除回應"""
    success: bool
    message: str


@router.post("/nas-auth/test", response_model=NasAuthTestResponse)
async def test_nas_auth_connection(
    request: NasAuthTestRequest,
    session: SessionData = Depends(get_current_session),
) -> NasAuthTestResponse:
    """測試 NAS 認證連線

    僅租戶管理員可操作。
    使用系統服務帳號測試指定的 NAS 主機/共享是否可連線。
    """
    from ..services.smb import create_smb_service, SMBAuthError, SMBConnectionError

    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
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


@router.get("/bot", response_model=LineBotSettingsResponse)
async def get_linebot_settings(
    session: SessionData = Depends(get_current_session),
) -> LineBotSettingsResponse:
    """取得租戶 Line Bot 設定

    僅租戶管理員可操作。
    回傳設定狀態，不包含敏感憑證。
    """
    from ..services.tenant import get_tenant_line_credentials

    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 取得 Line Bot 憑證（解密後）
    credentials = await get_tenant_line_credentials(session.tenant_id)

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


@router.put("/bot", response_model=LineBotSettingsResponse)
async def update_linebot_settings(
    request: LineBotSettingsUpdate,
    session: SessionData = Depends(get_current_session),
) -> LineBotSettingsResponse:
    """更新租戶 Line Bot 設定

    僅租戶管理員可操作。
    更新 Line Bot 憑證（會自動加密儲存）。
    """
    from ..services.tenant import get_tenant_line_credentials, update_tenant_line_settings
    from ..services.linebot import invalidate_tenant_secrets_cache

    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 更新設定
    success = await update_tenant_line_settings(
        session.tenant_id,
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
    credentials = await get_tenant_line_credentials(session.tenant_id)

    return LineBotSettingsResponse(
        configured=bool(credentials),
        channel_id=credentials.get("channel_id") if credentials else None,
    )


@router.post("/bot/test", response_model=LineBotTestResponse)
async def test_linebot_connection(
    session: SessionData = Depends(get_current_session),
) -> LineBotTestResponse:
    """測試租戶 Line Bot 憑證

    僅租戶管理員可操作。
    使用租戶的憑證呼叫 Line API 確認設定是否正確。
    """
    from linebot.v3.messaging import AsyncApiClient, AsyncMessagingApi, Configuration
    from ..services.tenant import get_tenant_line_credentials

    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 取得 Line Bot 憑證
    credentials = await get_tenant_line_credentials(session.tenant_id)

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


@router.delete("/bot", response_model=LineBotDeleteResponse)
async def delete_linebot_settings(
    session: SessionData = Depends(get_current_session),
) -> LineBotDeleteResponse:
    """清除租戶 Line Bot 設定

    僅租戶管理員可操作。
    清除所有 Line Bot 憑證。
    """
    from ..services.tenant import update_tenant_line_settings
    from ..services.linebot import invalidate_tenant_secrets_cache

    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 清除設定（傳入空值）
    success = await update_tenant_line_settings(
        session.tenant_id,
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

    return LineBotDeleteResponse(success=True, message="Line Bot 設定已清除")


# ============================================================
# Telegram Bot 設定 API
# ============================================================


class TelegramBotSettingsUpdate(BaseModel):
    """更新 Telegram Bot 設定請求"""
    bot_token: str | None = None
    admin_chat_id: str | None = None


class TelegramBotSettingsResponse(BaseModel):
    """Telegram Bot 設定回應（不包含敏感資訊）"""
    configured: bool
    admin_chat_id: str | None = None


class TelegramBotTestResponse(BaseModel):
    """Telegram Bot 測試回應"""
    success: bool
    bot_info: dict | None = None
    error: str | None = None


class TelegramBotDeleteResponse(BaseModel):
    """Telegram Bot 刪除回應"""
    success: bool
    message: str


@router.get("/telegram-bot", response_model=TelegramBotSettingsResponse)
async def get_telegram_bot_settings(
    session: SessionData = Depends(get_current_session),
) -> TelegramBotSettingsResponse:
    """取得租戶 Telegram Bot 設定"""
    from ..services.tenant import get_tenant_telegram_credentials

    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    credentials = await get_tenant_telegram_credentials(session.tenant_id)

    if credentials:
        return TelegramBotSettingsResponse(
            configured=True,
            admin_chat_id=credentials.get("admin_chat_id"),
        )
    else:
        return TelegramBotSettingsResponse(configured=False)


@router.put("/telegram-bot", response_model=TelegramBotSettingsResponse)
async def update_telegram_bot_settings(
    request: TelegramBotSettingsUpdate,
    session: SessionData = Depends(get_current_session),
) -> TelegramBotSettingsResponse:
    """更新租戶 Telegram Bot 設定"""
    from ..services.tenant import get_tenant_telegram_credentials, update_tenant_telegram_settings

    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    success = await update_tenant_telegram_settings(
        session.tenant_id,
        bot_token=request.bot_token,
        admin_chat_id=request.admin_chat_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新失敗",
        )

    credentials = await get_tenant_telegram_credentials(session.tenant_id)

    return TelegramBotSettingsResponse(
        configured=bool(credentials),
        admin_chat_id=credentials.get("admin_chat_id") if credentials else None,
    )


@router.post("/telegram-bot/test", response_model=TelegramBotTestResponse)
async def test_telegram_bot_connection(
    session: SessionData = Depends(get_current_session),
) -> TelegramBotTestResponse:
    """測試租戶 Telegram Bot 憑證（呼叫 Telegram getMe API）"""
    import httpx
    from ..services.tenant import get_tenant_telegram_credentials

    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    credentials = await get_tenant_telegram_credentials(session.tenant_id)

    if not credentials:
        return TelegramBotTestResponse(
            success=False,
            error="尚未設定 Telegram Bot 憑證",
        )

    bot_token = credentials.get("bot_token")
    if not bot_token:
        return TelegramBotTestResponse(
            success=False,
            error="缺少 Bot Token",
        )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getMe",
                timeout=10,
            )
            data = resp.json()

            if data.get("ok"):
                result = data["result"]
                return TelegramBotTestResponse(
                    success=True,
                    bot_info={
                        "id": result.get("id"),
                        "first_name": result.get("first_name"),
                        "username": result.get("username"),
                        "is_bot": result.get("is_bot"),
                    },
                )
            else:
                return TelegramBotTestResponse(
                    success=False,
                    error=data.get("description", "未知錯誤"),
                )
    except Exception as e:
        return TelegramBotTestResponse(
            success=False,
            error=str(e),
        )


@router.delete("/telegram-bot", response_model=TelegramBotDeleteResponse)
async def delete_telegram_bot_settings(
    session: SessionData = Depends(get_current_session),
) -> TelegramBotDeleteResponse:
    """清除租戶 Telegram Bot 設定"""
    from ..services.tenant import update_tenant_telegram_settings

    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    success = await update_tenant_telegram_settings(
        session.tenant_id,
        bot_token=None,
        admin_chat_id=None,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="清除失敗",
        )

    return TelegramBotDeleteResponse(success=True, message="Telegram Bot 設定已清除")
