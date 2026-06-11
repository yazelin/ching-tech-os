"""認證相關資料模型"""

from datetime import datetime
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


class LoginResponse(BaseModel):
    """登入回應"""

    success: bool
    token: str | None = None
    username: str | None = None
    error: str | None = None
    role: str | None = None  # admin, user
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
    # 認證來源：session（web 登入）或 pat（長效 API token）
    auth_type: str = "session"
    # 唯讀 token：非 GET/HEAD/OPTIONS 的 app API 一律拒絕
    read_only: bool = False


class ErrorResponse(BaseModel):
    """錯誤回應"""

    success: bool = False
    error: str


class ApiTokenCreateRequest(BaseModel):
    """建立 API token 請求"""

    name: str
    # 允許存取的 app id 清單，空清單代表使用者全部 app 權限
    scopes: list[str] = ["knowledge-base"]
    # 有效天數，None 代表永不過期
    expires_days: int | None = 180
    read_only: bool = True


class ApiTokenInfo(BaseModel):
    """API token 資訊（不含 token 本體）"""

    id: int
    name: str
    scopes: list[str]
    read_only: bool
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime


class ApiTokenCreateResponse(BaseModel):
    """建立 API token 回應

    token 僅在建立時回傳一次，之後無法再取得。
    """

    success: bool
    token: str
    info: ApiTokenInfo


class ApiTokenListResponse(BaseModel):
    """API token 列表回應"""

    success: bool
    tokens: list[ApiTokenInfo]
