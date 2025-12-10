"""認證相關資料模型"""

from datetime import datetime
from pydantic import BaseModel


class LoginRequest(BaseModel):
    """登入請求"""

    username: str
    password: str


class LoginResponse(BaseModel):
    """登入回應"""

    success: bool
    token: str | None = None
    username: str | None = None
    error: str | None = None


class LogoutResponse(BaseModel):
    """登出回應"""

    success: bool


class SessionData(BaseModel):
    """Session 資料"""

    username: str
    password: str  # SMB 操作需要
    nas_host: str
    created_at: datetime
    expires_at: datetime


class ErrorResponse(BaseModel):
    """錯誤回應"""

    success: bool = False
    error: str
