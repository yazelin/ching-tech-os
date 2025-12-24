"""Line Bot 相關的 Pydantic models

包含：
- LineGroup（群組）
- LineUser（用戶）
- LineMessage（訊息）
- LineFile（檔案）
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================
# Line Group Models
# ============================================================


class LineGroupBase(BaseModel):
    """Line 群組基礎模型"""

    name: str | None = None
    picture_url: str | None = None


class LineGroupCreate(LineGroupBase):
    """建立 Line 群組"""

    line_group_id: str = Field(..., max_length=64)


class LineGroupUpdate(BaseModel):
    """更新 Line 群組"""

    name: str | None = None
    picture_url: str | None = None
    project_id: UUID | None = None
    is_active: bool | None = None
    allow_ai_response: bool | None = None


class LineGroupResponse(LineGroupBase):
    """Line 群組回應"""

    id: UUID
    line_group_id: str
    member_count: int
    project_id: UUID | None
    project_name: str | None = None
    is_active: bool
    allow_ai_response: bool = False
    joined_at: datetime
    left_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LineGroupListResponse(BaseModel):
    """Line 群組列表回應"""

    items: list[LineGroupResponse]
    total: int


# ============================================================
# Line User Models
# ============================================================


class LineUserBase(BaseModel):
    """Line 用戶基礎模型"""

    display_name: str | None = None
    picture_url: str | None = None
    status_message: str | None = None
    language: str | None = None


class LineUserCreate(LineUserBase):
    """建立 Line 用戶"""

    line_user_id: str = Field(..., max_length=64)


class LineUserUpdate(BaseModel):
    """更新 Line 用戶"""

    display_name: str | None = None
    picture_url: str | None = None
    status_message: str | None = None
    user_id: int | None = None
    is_friend: bool | None = None


class LineUserResponse(LineUserBase):
    """Line 用戶回應"""

    id: UUID
    line_user_id: str
    user_id: int | None
    is_friend: bool
    created_at: datetime
    updated_at: datetime
    # 綁定狀態（來自 JOIN users）
    bound_username: str | None = None
    bound_display_name: str | None = None


class LineUserListResponse(BaseModel):
    """Line 用戶列表回應"""

    items: list[LineUserResponse]
    total: int


# ============================================================
# Line Message Models
# ============================================================


class LineMessageCreate(BaseModel):
    """建立 Line 訊息（內部使用）"""

    message_id: str = Field(..., max_length=64)
    line_user_id: UUID
    line_group_id: UUID | None = None
    message_type: str = Field(..., max_length=32)
    content: str | None = None
    reply_token: str | None = None
    is_from_bot: bool = False


class LineMessageResponse(BaseModel):
    """Line 訊息回應"""

    id: UUID
    message_id: str
    line_user_id: UUID
    user_display_name: str | None = None
    user_picture_url: str | None = None
    line_group_id: UUID | None
    message_type: str
    content: str | None
    file_id: UUID | None
    file_info: dict | None = None
    is_from_bot: bool
    ai_processed: bool
    created_at: datetime


class LineMessageListResponse(BaseModel):
    """Line 訊息列表回應"""

    items: list[LineMessageResponse]
    total: int
    page: int
    page_size: int


class LineMessageFilter(BaseModel):
    """Line 訊息過濾條件"""

    line_group_id: UUID | None = None
    line_user_id: UUID | None = None
    message_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


# ============================================================
# Line File Models
# ============================================================


class LineFileCreate(BaseModel):
    """建立 Line 檔案（內部使用）"""

    message_id: UUID
    file_type: str = Field(..., max_length=32)
    file_name: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    nas_path: str | None = None
    thumbnail_path: str | None = None
    duration: int | None = None


class LineFileResponse(BaseModel):
    """Line 檔案回應"""

    id: UUID
    message_id: UUID
    file_type: str
    file_name: str | None
    file_size: int | None
    mime_type: str | None
    nas_path: str | None
    thumbnail_path: str | None
    duration: int | None
    created_at: datetime
    # 關聯資訊（來自 JOIN）
    line_group_id: UUID | None = None
    line_user_id: UUID | None = None
    user_display_name: str | None = None
    group_name: str | None = None


class LineFileListResponse(BaseModel):
    """Line 檔案列表回應"""

    items: list[LineFileResponse]
    total: int


# ============================================================
# Webhook Event Models
# ============================================================


class WebhookEvent(BaseModel):
    """Line Webhook 事件（簡化模型）"""

    type: str
    timestamp: int
    source: dict[str, Any]
    reply_token: str | None = None
    message: dict[str, Any] | None = None


class WebhookRequest(BaseModel):
    """Line Webhook 請求"""

    destination: str
    events: list[WebhookEvent]


# ============================================================
# Project Binding Models
# ============================================================


class ProjectBindingRequest(BaseModel):
    """群組專案綁定請求"""

    project_id: UUID


# ============================================================
# Line Binding Models（用戶與 CTOS 帳號綁定）
# ============================================================


class BindingCodeResponse(BaseModel):
    """綁定驗證碼回應"""

    code: str
    expires_at: datetime


class BindingStatusResponse(BaseModel):
    """綁定狀態回應"""

    is_bound: bool
    line_display_name: str | None = None
    line_picture_url: str | None = None
    bound_at: datetime | None = None
