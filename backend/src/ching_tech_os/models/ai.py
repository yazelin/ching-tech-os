"""AI 對話相關的 Pydantic models"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """對話訊息"""

    role: str = Field(..., description="訊息角色: user, assistant, system")
    content: str = Field(..., description="訊息內容")
    timestamp: int = Field(..., description="Unix timestamp")
    is_summary: bool = Field(default=False, description="是否為壓縮摘要")


class ChatCreate(BaseModel):
    """建立對話的請求"""

    title: str = Field(default="新對話", max_length=100)
    model: str = Field(default="claude-sonnet", max_length=50)
    prompt_name: str = Field(default="default", max_length=50)


class ChatUpdate(BaseModel):
    """更新對話的請求"""

    title: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=50)
    prompt_name: str | None = Field(default=None, max_length=50)


class ChatResponse(BaseModel):
    """對話回應（列表用，不含 messages）"""

    id: UUID
    user_id: int | None
    title: str
    model: str
    prompt_name: str
    created_at: datetime
    updated_at: datetime


class ChatDetailResponse(BaseModel):
    """對話詳情回應（含 messages）"""

    id: UUID
    user_id: int | None
    title: str
    model: str
    prompt_name: str
    messages: list[ChatMessage]
    created_at: datetime
    updated_at: datetime


class PromptInfo(BaseModel):
    """System Prompt 資訊"""

    name: str = Field(..., description="Prompt 名稱（檔名）")
    display_name: str = Field(..., description="顯示名稱（從檔案標題取得）")
    description: str = Field(default="", description="簡短描述")


class SendMessageRequest(BaseModel):
    """發送訊息請求（Socket.IO ai_chat 事件）"""

    chat_id: UUID = Field(..., alias="chatId")
    message: str
    model: str = Field(default="claude-sonnet")


class CompressChatRequest(BaseModel):
    """壓縮對話請求（Socket.IO compress_chat 事件）"""

    chat_id: UUID = Field(..., alias="chatId")
