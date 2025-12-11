"""訊息中心相關資料模型"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageSeverity(str, Enum):
    """訊息嚴重程度"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MessageSource(str, Enum):
    """訊息來源分類"""

    SYSTEM = "system"  # 系統層級（啟動、關閉、資源）
    SECURITY = "security"  # 安全相關（登入、權限、異常存取）
    APP = "app"  # 應用程式（各功能模組）
    USER = "user"  # 使用者操作（通知、提醒）


class MessageCreate(BaseModel):
    """建立訊息請求（內部使用）"""

    severity: MessageSeverity
    source: MessageSource
    title: str = Field(..., max_length=200)
    content: str | None = None
    metadata: dict[str, Any] | None = None
    user_id: int | None = None
    category: str | None = Field(None, max_length=50)
    session_id: str | None = Field(None, max_length=100)


class MessageResponse(BaseModel):
    """訊息回應"""

    id: int
    created_at: datetime
    severity: MessageSeverity
    source: MessageSource
    category: str | None
    title: str
    content: str | None
    metadata: dict[str, Any] | None
    user_id: int | None
    session_id: str | None
    is_read: bool


class MessageListItem(BaseModel):
    """訊息列表項目（簡化版）"""

    id: int
    created_at: datetime
    severity: MessageSeverity
    source: MessageSource
    category: str | None
    title: str
    is_read: bool


class MessageListResponse(BaseModel):
    """訊息列表回應（含分頁）"""

    items: list[MessageListItem]
    total: int
    page: int
    limit: int
    total_pages: int


class MessageFilter(BaseModel):
    """訊息查詢條件"""

    severity: list[MessageSeverity] | None = None
    source: list[MessageSource] | None = None
    category: str | None = None
    user_id: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    search: str | None = None
    is_read: bool | None = None
    page: int = 1
    limit: int = 20


class UnreadCountResponse(BaseModel):
    """未讀數量回應"""

    count: int


class MarkReadRequest(BaseModel):
    """標記已讀請求"""

    ids: list[int] | None = None
    all: bool = False


class MarkReadResponse(BaseModel):
    """標記已讀回應"""

    marked_count: int


# WebSocket 事件模型
class MessageNewEvent(BaseModel):
    """新訊息事件（WebSocket 推送）"""

    id: int
    severity: MessageSeverity
    source: MessageSource
    category: str | None
    title: str
    created_at: datetime


class UnreadCountEvent(BaseModel):
    """未讀數量更新事件（WebSocket 推送）"""

    count: int
