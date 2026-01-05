"""AI 相關的 Pydantic models

包含：
- Chat models（對話）
- Prompt models（Prompt 管理）
- Agent models（Agent 設定）
- Log models（AI 調用日誌）
"""

from datetime import datetime
from typing import Any
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


# ============================================================
# AI Prompt Models
# ============================================================


class AiPromptCreate(BaseModel):
    """建立 Prompt 請求"""

    name: str = Field(..., max_length=128, description="唯一識別名")
    display_name: str | None = Field(None, max_length=256, description="顯示名稱")
    category: str | None = Field(None, max_length=64, description="分類：system, task, template")
    content: str = Field(..., description="Prompt 內容")
    description: str | None = Field(None, description="使用說明")
    variables: dict[str, Any] | None = Field(None, description="可用變數說明")


class AiPromptUpdate(BaseModel):
    """更新 Prompt 請求"""

    name: str | None = Field(None, max_length=128)
    display_name: str | None = Field(None, max_length=256)
    category: str | None = Field(None, max_length=64)
    content: str | None = None
    description: str | None = None
    variables: dict[str, Any] | None = None


class AiPromptResponse(BaseModel):
    """Prompt 回應"""

    id: UUID
    name: str
    display_name: str | None
    category: str | None
    content: str
    description: str | None
    variables: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class AiPromptListItem(BaseModel):
    """Prompt 列表項目（不含完整 content）"""

    id: UUID
    name: str
    display_name: str | None
    category: str | None
    description: str | None
    updated_at: datetime


class AiPromptListResponse(BaseModel):
    """Prompt 列表回應"""

    items: list[AiPromptListItem]
    total: int


# ============================================================
# AI Agent Models
# ============================================================


class AiAgentCreate(BaseModel):
    """建立 Agent 請求"""

    name: str = Field(..., max_length=64, description="唯一識別名")
    display_name: str | None = Field(None, max_length=128, description="顯示名稱")
    description: str | None = Field(None, description="說明")
    model: str = Field(..., max_length=32, description="AI 模型名稱")
    system_prompt_id: UUID | None = Field(None, description="關聯的 Prompt ID")
    is_active: bool = Field(True, description="是否啟用")
    tools: list[str] | None = Field(None, description="允許使用的工具列表")
    settings: dict[str, Any] | None = Field(None, description="額外設定")


class AiAgentUpdate(BaseModel):
    """更新 Agent 請求"""

    name: str | None = Field(None, max_length=64)
    display_name: str | None = Field(None, max_length=128)
    description: str | None = None
    model: str | None = Field(None, max_length=32)
    system_prompt_id: UUID | None = None
    is_active: bool | None = None
    tools: list[str] | None = None
    settings: dict[str, Any] | None = None


class AiAgentResponse(BaseModel):
    """Agent 回應"""

    id: UUID
    name: str
    display_name: str | None
    description: str | None
    model: str
    system_prompt_id: UUID | None
    system_prompt: AiPromptResponse | None = None  # 關聯的 Prompt（詳情時填入）
    is_active: bool
    tools: list[str] | None
    settings: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class AiAgentListItem(BaseModel):
    """Agent 列表項目"""

    id: UUID
    name: str
    display_name: str | None
    model: str
    is_active: bool
    tools: list[str] | None
    updated_at: datetime


class AiAgentListResponse(BaseModel):
    """Agent 列表回應"""

    items: list[AiAgentListItem]
    total: int


# ============================================================
# AI Log Models
# ============================================================


class AiLogCreate(BaseModel):
    """建立 AI Log（內部使用）"""

    agent_id: UUID | None = None
    prompt_id: UUID | None = None
    context_type: str | None = Field(None, max_length=32)
    context_id: str | None = Field(None, max_length=64)
    input_prompt: str
    system_prompt: str | None = Field(None, description="實際使用的 system prompt 內容")
    allowed_tools: list[str] | None = Field(None, description="允許使用的工具列表")
    raw_response: str | None = None
    parsed_response: dict[str, Any] | None = None
    model: str | None = Field(None, max_length=32)
    success: bool = True
    error_message: str | None = None
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class AiLogResponse(BaseModel):
    """AI Log 回應"""

    id: UUID
    agent_id: UUID | None
    agent_name: str | None = None  # 從 agent 取得的名稱
    prompt_id: UUID | None
    context_type: str | None
    context_id: str | None
    input_prompt: str
    system_prompt: str | None = None  # 實際使用的 system prompt 內容
    allowed_tools: list[str] | None = None  # 允許使用的工具列表
    raw_response: str | None
    parsed_response: dict[str, Any] | None
    model: str | None
    success: bool
    error_message: str | None
    duration_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    created_at: datetime


class AiLogListItem(BaseModel):
    """AI Log 列表項目（不含完整內容）"""

    id: UUID
    agent_id: UUID | None
    agent_name: str | None
    context_type: str | None
    allowed_tools: list[str] | None = None  # 允許使用的工具列表
    used_tools: list[str] | None = None  # 實際使用的工具（從 parsed_response 解析）
    success: bool
    duration_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    created_at: datetime


class AiLogListResponse(BaseModel):
    """AI Log 列表回應"""

    items: list[AiLogListItem]
    total: int
    page: int
    page_size: int


class AiLogFilter(BaseModel):
    """AI Log 過濾條件"""

    agent_id: UUID | None = None
    context_type: str | None = None
    success: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class AiLogStats(BaseModel):
    """AI Log 統計"""

    total_calls: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_duration_ms: float | None
    total_input_tokens: int
    total_output_tokens: int


# ============================================================
# AI Test Models
# ============================================================


class AiTestRequest(BaseModel):
    """測試 Agent 請求"""

    agent_id: UUID = Field(..., description="要測試的 Agent ID")
    message: str = Field(..., description="測試訊息")


class AiTestResponse(BaseModel):
    """測試 Agent 回應"""

    success: bool
    response: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    log_id: UUID | None = None
