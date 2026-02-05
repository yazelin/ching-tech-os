"""認證相關資料模型"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class DeviceInfo(BaseModel):
    """裝置資訊（前端提供）"""

    fingerprint: str | None = None
    device_type: str | None = None
    browser: str | None = None
    os: str | None = None
    screen_resolution: str | None = None
    timezone: str | None = None
    language: str | None = None


class LoginRequest(BaseModel):
    """登入請求"""

    username: str
    password: str
    device: DeviceInfo | None = None
    # 多租戶欄位（SaaS 模式必填，單租戶模式可省略）
    tenant_code: str | None = None


class TenantBriefInfo(BaseModel):
    """租戶簡要資訊（登入回應用）"""

    id: UUID
    code: str
    name: str
    plan: str


class LoginResponse(BaseModel):
    """登入回應"""

    success: bool
    token: str | None = None
    username: str | None = None
    error: str | None = None
    # 多租戶欄位
    tenant: TenantBriefInfo | None = None
    role: str | None = None  # user, tenant_admin, platform_admin
    # 密碼認證欄位
    must_change_password: bool = False  # 是否需要強制變更密碼


class LogoutResponse(BaseModel):
    """登出回應"""

    success: bool


class SessionData(BaseModel):
    """Session 資料"""

    username: str
    password: str  # SMB 操作需要
    nas_host: str
    user_id: int | None = None  # 資料庫中的使用者 ID
    created_at: datetime
    expires_at: datetime
    role: str = "user"  # admin, user
    # App 權限（登入時載入，避免每次 API 都查資料庫）
    app_permissions: dict[str, bool] = {}


class ErrorResponse(BaseModel):
    """錯誤回應"""

    success: bool = False
    error: str
