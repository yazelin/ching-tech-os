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
)
from ..services.permissions import (
    is_admin,
    get_user_permissions_for_admin,
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
    permissions = get_user_permissions_for_admin(user["username"], preferences)

    return UserInfo(
        id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
        created_at=user["created_at"],
        last_login_at=user["last_login_at"],
        is_admin=is_admin(user["username"]),
        permissions=UserPermissions(**permissions),
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
    return UserInfo(**user)


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
    if not is_admin(session.username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理員權限",
        )
    return session


@admin_router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    session: SessionData = Depends(require_admin),
) -> AdminUserListResponse:
    """取得所有使用者列表（管理員限定）"""
    users = await get_all_users()

    result = []
    for user in users:
        preferences = _parse_preferences(user.get("preferences"))
        permissions = get_user_permissions_for_admin(user["username"], preferences)

        result.append(AdminUserInfo(
            id=user["id"],
            username=user["username"],
            display_name=user["display_name"],
            is_admin=is_admin(user["username"]),
            permissions=UserPermissions(**permissions),
            created_at=user["created_at"],
            last_login_at=user["last_login_at"],
        ))

    return AdminUserListResponse(users=result)


@admin_router.patch("/users/{user_id}/permissions", response_model=UpdatePermissionsResponse)
async def update_user_permissions_api(
    user_id: int,
    request: UpdatePermissionsRequest,
    session: SessionData = Depends(require_admin),
) -> UpdatePermissionsResponse:
    """更新使用者權限（管理員限定）"""
    # 檢查目標使用者是否存在
    target_user = await get_user_by_id(user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    # 不能修改管理員的權限
    if is_admin(target_user["username"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無法修改管理員的權限",
        )

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
    updated_perms = get_user_permissions_for_admin(
        target_user["username"],
        updated_prefs,
    )

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
