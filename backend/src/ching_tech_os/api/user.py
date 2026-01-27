"""使用者 API"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    get_all_users_cross_tenant,
    update_user_display_name,
    get_user_preferences,
    update_user_preferences,
    update_user_permissions,
    _parse_preferences,
)
from ..services.permissions import (
    get_user_permissions_for_role,
    get_default_permissions,
    get_app_display_names,
)
from .auth import (
    get_current_session,
    require_tenant_admin_or_above,
    require_can_manage_target,
    can_manage_user,
)

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
    users = await get_all_users(tenant_id=session.tenant_id)

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
    user = await get_user_by_username(session.username, tenant_id=session.tenant_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    # 取得權限資訊（使用 session.role，因為登入時已從 tenant_admins 表判斷）
    preferences = _parse_preferences(user.get("preferences"))
    permissions = get_user_permissions_for_role(session.role, preferences)

    # 判斷是否已設定密碼
    has_password = bool(user.get("password_hash"))

    # is_admin 改為基於 role 判斷
    user_is_admin = session.role in ("tenant_admin", "platform_admin")

    return UserInfo(
        id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
        created_at=user["created_at"],
        last_login_at=user["last_login_at"],
        is_admin=user_is_admin,
        permissions=UserPermissions(**permissions),
        tenant_id=session.tenant_id,
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
        user = await update_user_display_name(
            session.username, request.display_name, tenant_id=session.tenant_id
        )
    else:
        user = await get_user_by_username(session.username, tenant_id=session.tenant_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在",
        )

    # 取得權限資訊（使用 session.role，因為登入時已從 tenant_admins 表判斷）
    preferences = _parse_preferences(user.get("preferences"))
    permissions = get_user_permissions_for_role(session.role, preferences)

    # is_admin 改為基於 role 判斷
    user_is_admin = session.role in ("tenant_admin", "platform_admin")

    return UserInfo(
        id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
        created_at=user["created_at"],
        last_login_at=user["last_login_at"],
        is_admin=user_is_admin,
        permissions=UserPermissions(**permissions),
        tenant_id=session.tenant_id,
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


# 新增租戶 API router
tenant_router = APIRouter(prefix="/api/tenant", tags=["tenant"])


async def require_admin(session: SessionData = Depends(get_current_session)) -> SessionData:
    """要求管理員權限的 dependency（租戶管理員或平台管理員）"""
    if session.role not in ("tenant_admin", "platform_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理員權限",
        )
    return session


@admin_router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    tenant_id: str | None = Query(None, description="租戶 ID 篩選（僅平台管理員可用）"),
    session: SessionData = Depends(require_admin),
) -> AdminUserListResponse:
    """取得使用者列表（管理員限定）

    - 平台管理員：可查詢所有租戶（可選 tenant_id 篩選）
    - 租戶管理員：僅能查詢同租戶使用者
    """
    result = []

    if session.role == "platform_admin":
        # 平台管理員：可查詢所有租戶或指定租戶
        users = await get_all_users_cross_tenant(filter_tenant_id=tenant_id)
        for user in users:
            preferences = _parse_preferences(user.get("preferences"))
            user_role = user.get("role") or "user"
            permissions = get_user_permissions_for_role(user_role, preferences)
            result.append(AdminUserInfo(
                id=user["id"],
                username=user["username"],
                display_name=user["display_name"],
                is_admin=user.get("role") in ("tenant_admin", "platform_admin"),
                permissions=UserPermissions(**permissions),
                created_at=user["created_at"],
                last_login_at=user["last_login_at"],
                is_active=user.get("is_active", True),
                tenant_id=user.get("tenant_id"),
                role=user.get("role", "user"),
                tenant_name=user.get("tenant_name"),
            ))
    else:
        # 租戶管理員：僅能查詢同租戶
        if tenant_id is not None and str(session.tenant_id) != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權限查詢其他租戶的使用者",
            )
        users = await get_all_users(tenant_id=session.tenant_id)
        for user in users:
            preferences = _parse_preferences(user.get("preferences"))
            user_role = user.get("role") or "user"
            permissions = get_user_permissions_for_role(user_role, preferences)
            result.append(AdminUserInfo(
                id=user["id"],
                username=user["username"],
                display_name=user["display_name"],
                is_admin=user_role in ("tenant_admin", "platform_admin"),
                permissions=UserPermissions(**permissions),
                created_at=user["created_at"],
                last_login_at=user["last_login_at"],
                is_active=user.get("is_active", True),
                tenant_id=user.get("tenant_id"),
                role=user_role,
            ))

    return AdminUserListResponse(users=result)


@tenant_router.get("/users", response_model=AdminUserListResponse)
async def list_tenant_users_api(
    include_inactive: bool = Query(False, description="是否包含停用的使用者"),
    session: SessionData = Depends(require_tenant_admin_or_above),
) -> AdminUserListResponse:
    """取得同租戶的使用者列表（租戶管理員專用）

    自動限制為同租戶的使用者，租戶管理員只能看到一般使用者。

    Args:
        include_inactive: 是否包含停用的使用者
    """
    users = await get_all_users(tenant_id=session.tenant_id, include_inactive=include_inactive)

    result = []
    for user in users:
        # 租戶管理員只能看到自己和 user 角色的使用者
        user_role = user.get("role", "user")
        if session.role == "tenant_admin" and user_role == "platform_admin":
            continue  # 跳過平台管理員

        preferences = _parse_preferences(user.get("preferences"))
        permissions = get_user_permissions_for_role(user_role, preferences)
        result.append(AdminUserInfo(
            id=user["id"],
            username=user["username"],
            display_name=user["display_name"],
            is_admin=user_role in ("tenant_admin", "platform_admin"),
            permissions=UserPermissions(**permissions),
            created_at=user["created_at"],
            last_login_at=user["last_login_at"],
            is_active=user.get("is_active", True),
            tenant_id=user.get("tenant_id"),
            role=user_role,
        ))

    return AdminUserListResponse(users=result)


@admin_router.patch("/users/{user_id}/permissions", response_model=UpdatePermissionsResponse)
async def update_user_permissions_api(
    user_id: int,
    request: UpdatePermissionsRequest,
    session: SessionData = Depends(require_admin),
) -> UpdatePermissionsResponse:
    """更新使用者權限（管理員限定）

    權限階層：platform_admin > tenant_admin > user
    - 平台管理員可修改所有人的權限（包括其他 platform_admin 和 tenant_admin）
    - 租戶管理員只能修改同租戶的一般使用者權限
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
    target_tenant_id = target_user.get("tenant_id")

    # 權限階層檢查：確認操作者可以管理目標使用者
    await require_can_manage_target(
        session,
        target_role,
        str(target_tenant_id) if target_tenant_id else None,
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
