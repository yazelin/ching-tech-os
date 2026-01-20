"""使用者相關資料模型"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class UserPermissions(BaseModel):
    """使用者權限結構"""

    apps: dict[str, bool]
    knowledge: dict[str, bool]


class UserInfo(BaseModel):
    """使用者資訊"""

    id: int
    username: str
    display_name: str | None
    created_at: datetime
    last_login_at: datetime | None
    is_admin: bool = False
    permissions: UserPermissions | None = None
    # 多租戶欄位
    tenant_id: UUID | None = None
    role: str = "user"  # user, tenant_admin, platform_admin


class UpdateUserRequest(BaseModel):
    """更新使用者請求"""

    display_name: str | None = None


class AdminUserInfo(BaseModel):
    """管理員查看的使用者資訊"""

    id: int
    username: str
    display_name: str | None
    is_admin: bool
    permissions: UserPermissions
    created_at: datetime
    last_login_at: datetime | None
    # 多租戶欄位
    tenant_id: UUID | None = None
    role: str = "user"


class AdminUserListResponse(BaseModel):
    """使用者列表回應"""

    users: list[AdminUserInfo]


class UpdatePermissionsRequest(BaseModel):
    """更新權限請求"""

    apps: dict[str, bool] | None = None
    knowledge: dict[str, bool] | None = None


class UpdatePermissionsResponse(BaseModel):
    """更新權限回應"""

    success: bool
    permissions: UserPermissions


class DefaultPermissionsResponse(BaseModel):
    """預設權限回應"""

    apps: dict[str, bool]
    knowledge: dict[str, bool]
    app_names: dict[str, str]
