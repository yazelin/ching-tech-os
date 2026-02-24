"""使用者 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..models.auth import SessionData
from ..models.user import (
    UserInfo,
    UserPermissions,
    UpdateUserRequest,
    AdminUserInfo,
    AdminUserListResponse,
    UpdatePermissionsRequest,
    UpdatePermissionsResponse,
    DefaultPermissionsResponse,
    CreateUserRequest,
    CreateUserResponse,
    UpdateUserInfoRequest,
    UpdateUserStatusRequest,
    ResetPasswordRequest,
    UserOperationResponse,
)
from ..services.user import (
    get_user_by_username,
    get_user_by_id,
    get_all_users,
    update_user_display_name,
    get_user_preferences,
    update_user_preferences,
    update_user_permissions,
    _parse_preferences,
    create_user,
    update_user_info,
    deactivate_user,
    activate_user,
    clear_user_password,
    delete_user,
)
from ..services.password import hash_password, validate_password_strength
from ..services.permissions import (
    get_user_permissions_for_role,
    get_default_permissions,
    get_app_display_names,
)
from .auth import get_current_session

router = APIRouter(prefix="/api/user", tags=["user"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


# === 偏好設定相關模型 ===


class PreferencesResponse(BaseModel):
    """偏好設定回應"""

    theme: str = "dark"


class PreferencesUpdateRequest(BaseModel):
    """偏好設定更新請求"""

    theme: str | None = None


class PreferencesUpdateResponse(BaseModel):
    """偏好設定更新回應"""

    success: bool
    preferences: PreferencesResponse


class SimpleUserInfo(BaseModel):
    """簡化的用戶資訊（供下拉選單使用）"""

    id: int
    username: str
    display_name: str | None


class SimpleUserListResponse(BaseModel):
    """用戶列表回應"""

    users: list[SimpleUserInfo]


@router.get("/list", response_model=SimpleUserListResponse)
async def list_users_simple(
    session: SessionData = Depends(get_current_session),
) -> SimpleUserListResponse:
    """取得所有用戶列表（簡化版，供下拉選單使用）"""
    users = await get_all_users()

    result = [
        SimpleUserInfo(
            id=user["id"],
            username=user["username"],
            display_name=user["display_name"],
        )
        for user in users
    ]

    return SimpleUserListResponse(users=result)


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    session: SessionData = Depends(get_current_session),
) -> UserInfo:
    """取得目前登入使用者的資訊，包含權限"""
    user = await get_user_by_username(session.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    # 取得權限資訊
    preferences = _parse_preferences(user.get("preferences"))
    permissions = get_user_permissions_for_role(session.role, preferences)

    # 判斷是否已設定密碼
    has_password = bool(user.get("password_hash"))

    # is_admin 改為基於 role 判斷
    user_is_admin = session.role == "admin"

    return UserInfo(
        id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
        created_at=user["created_at"],
        last_login_at=user["last_login_at"],
        is_admin=user_is_admin,
        permissions=UserPermissions(**permissions),
        role=session.role,
        has_password=has_password,
    )


@router.patch("/me", response_model=UserInfo)
async def update_current_user(
    request: UpdateUserRequest,
    session: SessionData = Depends(get_current_session),
) -> UserInfo:
    """更新目前登入使用者的資訊"""
    if request.display_name is not None:
        user = await update_user_display_name(session.username, request.display_name)
    else:
        user = await get_user_by_username(session.username)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    # 取得權限資訊
    preferences = _parse_preferences(user.get("preferences"))
    permissions = get_user_permissions_for_role(session.role, preferences)

    # is_admin 改為基於 role 判斷
    user_is_admin = session.role == "admin"

    return UserInfo(
        id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
        created_at=user["created_at"],
        last_login_at=user["last_login_at"],
        is_admin=user_is_admin,
        permissions=UserPermissions(**permissions),
        role=session.role,
    )


# === 偏好設定 API ===


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    session: SessionData = Depends(get_current_session),
) -> PreferencesResponse:
    """取得使用者偏好設定"""
    if session.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="使用者資料不完整",
        )

    preferences = await get_user_preferences(session.user_id)
    return PreferencesResponse(theme=preferences.get("theme", "dark"))


@router.put("/preferences", response_model=PreferencesUpdateResponse)
async def update_preferences(
    request: PreferencesUpdateRequest,
    session: SessionData = Depends(get_current_session),
) -> PreferencesUpdateResponse:
    """更新使用者偏好設定"""
    if session.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="使用者資料不完整",
        )

    # 只更新有提供的欄位
    update_data = {}
    if request.theme is not None:
        if request.theme not in ("dark", "light"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="無效的主題值，必須為 'dark' 或 'light'",
            )
        update_data["theme"] = request.theme

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未提供任何更新欄位",
        )

    preferences = await update_user_preferences(session.user_id, update_data)
    return PreferencesUpdateResponse(
        success=True,
        preferences=PreferencesResponse(theme=preferences.get("theme", "dark")),
    )


# ============================================================
# 管理員 API
# ============================================================


async def require_admin(session: SessionData = Depends(get_current_session)) -> SessionData:
    """要求管理員權限的 dependency"""
    if session.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理員權限",
        )
    return session


@admin_router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    session: SessionData = Depends(require_admin),
) -> AdminUserListResponse:
    """取得使用者列表（管理員限定）"""
    result = []
    users = await get_all_users(include_inactive=True)

    for user in users:
        preferences = _parse_preferences(user.get("preferences"))
        user_role = user.get("role") or "user"
        permissions = get_user_permissions_for_role(user_role, preferences)
        result.append(AdminUserInfo(
            id=user["id"],
            username=user["username"],
            display_name=user["display_name"],
            is_admin=user_role == "admin",
            permissions=UserPermissions(**permissions),
            created_at=user["created_at"],
            last_login_at=user["last_login_at"],
            is_active=user.get("is_active", True),
            role=user_role,
            has_password=bool(user.get("password_hash")),
        ))

    return AdminUserListResponse(users=result)


@admin_router.patch("/users/{user_id}/permissions", response_model=UpdatePermissionsResponse)
async def update_user_permissions_api(
    user_id: int,
    request: UpdatePermissionsRequest,
    session: SessionData = Depends(require_admin),
) -> UpdatePermissionsResponse:
    """更新使用者權限（管理員限定）

    - 管理員可修改所有人的權限
    - 不能修改自己的權限
    """
    # 不能修改自己的權限
    if session.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無法修改自己的權限",
        )

    # 檢查目標使用者是否存在
    target_user = await get_user_by_id(user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    target_role = target_user.get("role", "user")

    # 建立更新的權限資料
    permissions_update = {}
    if request.apps is not None:
        permissions_update["apps"] = request.apps
    if request.knowledge is not None:
        permissions_update["knowledge"] = request.knowledge

    if not permissions_update:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未提供任何權限更新",
        )

    # 更新權限
    updated_prefs = await update_user_permissions(user_id, permissions_update)
    updated_perms = get_user_permissions_for_role(target_role, updated_prefs)

    return UpdatePermissionsResponse(
        success=True,
        permissions=UserPermissions(**updated_perms),
    )


@admin_router.get("/default-permissions", response_model=DefaultPermissionsResponse)
async def get_default_permissions_api(
    session: SessionData = Depends(require_admin),
) -> DefaultPermissionsResponse:
    """取得預設權限設定（管理員限定）"""
    defaults = get_default_permissions()
    return DefaultPermissionsResponse(
        apps=defaults["apps"],
        knowledge=defaults["knowledge"],
        app_names=get_app_display_names(),
    )


@admin_router.post("/users", response_model=CreateUserResponse)
async def create_user_api(
    request: CreateUserRequest,
    session: SessionData = Depends(require_admin),
) -> CreateUserResponse:
    """建立使用者（管理員限定）"""
    # 驗證角色
    if request.role not in ("user", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色必須為 'user' 或 'admin'",
        )

    # 驗證密碼強度
    is_valid, error_msg = validate_password_strength(request.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # 建立使用者
    try:
        password_hashed = hash_password(request.password)
        user_id = await create_user(
            username=request.username,
            password_hash=password_hashed,
            display_name=request.display_name,
            role=request.role,
            must_change_password=True,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return CreateUserResponse(
        success=True,
        id=user_id,
        username=request.username,
        display_name=request.display_name,
        role=request.role,
    )


@admin_router.patch("/users/{user_id}", response_model=UserOperationResponse)
async def update_user_info_api(
    user_id: int,
    request: UpdateUserInfoRequest,
    session: SessionData = Depends(require_admin),
) -> UserOperationResponse:
    """編輯使用者資訊（管理員限定）"""
    # 檢查目標使用者是否存在
    target_user = await get_user_by_id(user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    # 管理員不能降級自己的角色
    if session.user_id == user_id and request.role and request.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能降級自己的角色",
        )

    # 驗證角色
    if request.role and request.role not in ("user", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色必須為 'user' 或 'admin'",
        )

    updated = await update_user_info(
        user_id=user_id,
        display_name=request.display_name,
        email=request.email,
        role=request.role,
    )

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新失敗",
        )

    return UserOperationResponse(success=True, message="使用者資訊已更新")


@admin_router.post("/users/{user_id}/reset-password", response_model=UserOperationResponse)
async def reset_user_password_api(
    user_id: int,
    request: ResetPasswordRequest,
    session: SessionData = Depends(require_admin),
) -> UserOperationResponse:
    """重設使用者密碼（管理員限定）"""
    # 檢查目標使用者是否存在
    target_user = await get_user_by_id(user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    # 驗證密碼強度
    is_valid, error_msg = validate_password_strength(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    from ..services.user import reset_user_password
    password_hashed = hash_password(request.new_password)
    success = await reset_user_password(user_id, password_hashed, must_change=True)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重設密碼失敗",
        )

    return UserOperationResponse(success=True, message="密碼已重設，使用者下次登入需要變更密碼")


@admin_router.patch("/users/{user_id}/status", response_model=UserOperationResponse)
async def update_user_status_api(
    user_id: int,
    request: UpdateUserStatusRequest,
    session: SessionData = Depends(require_admin),
) -> UserOperationResponse:
    """停用/啟用使用者帳號（管理員限定）"""
    # 管理員不能停用自己
    if session.user_id == user_id and not request.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能停用自己的帳號",
        )

    # 檢查目標使用者是否存在
    target_user = await get_user_by_id(user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    if request.is_active:
        success = await activate_user(user_id)
        msg = "帳號已啟用"
    else:
        success = await deactivate_user(user_id)
        msg = "帳號已停用"

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失敗",
        )

    return UserOperationResponse(success=True, message=msg)


@admin_router.post("/users/{user_id}/clear-password", response_model=UserOperationResponse)
async def clear_user_password_api(
    user_id: int,
    session: SessionData = Depends(require_admin),
) -> UserOperationResponse:
    """清除使用者密碼，恢復 NAS 認證（管理員限定）"""
    from ..config import settings

    # 管理員不能清除自己的密碼
    if session.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能清除自己的密碼",
        )

    # 檢查 NAS 認證是否啟用
    if not settings.enable_nas_auth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NAS 認證未啟用，清除密碼後使用者將無法登入",
        )

    # 檢查目標使用者是否存在
    target_user = await get_user_by_id(user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    success = await clear_user_password(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="清除密碼失敗",
        )

    return UserOperationResponse(success=True, message="密碼已清除，使用者將改為 NAS 認證登入")


@admin_router.delete("/users/{user_id}", response_model=UserOperationResponse)
async def delete_user_api(
    user_id: int,
    session: SessionData = Depends(require_admin),
) -> UserOperationResponse:
    """刪除使用者（管理員限定，永久刪除）"""
    # 管理員不能刪除自己
    if session.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能刪除自己的帳號",
        )

    # 檢查目標使用者是否存在
    target_user = await get_user_by_id(user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    success = await delete_user(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刪除失敗",
        )

    return UserOperationResponse(success=True, message="使用者已永久刪除")
