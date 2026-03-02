"""排程任務資料模型"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Trigger 設定 ──────────────────────────────────────────────


class CronTriggerConfig(BaseModel):
    """Cron 觸發規則"""

    minute: str = "*"
    hour: str = "*"
    day: str = "*"
    month: str = "*"
    day_of_week: str = "*"


class IntervalTriggerConfig(BaseModel):
    """Interval 觸發規則"""

    weeks: int = 0
    days: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0


# ── Executor 設定 ─────────────────────────────────────────────


class AgentExecutorConfig(BaseModel):
    """Agent 執行設定"""

    agent_name: str = Field(..., description="對應 ai_agents.name")
    prompt: str = Field(..., description="要求 Agent 執行的指令")
    ctos_user_id: int | None = Field(None, description="執行身份")


class SkillScriptExecutorConfig(BaseModel):
    """Skill Script 執行設定"""

    skill: str = Field(..., description="Skill 名稱")
    script: str = Field(..., description="Script 名稱")
    input: str = Field("", description="JSON 格式的輸入資料")
    ctos_user_id: int | None = Field(None, description="執行身份")


# ── 排程任務 ──────────────────────────────────────────────────


class ScheduledTaskBase(BaseModel):
    """排程任務共用欄位"""

    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    trigger_type: Literal["cron", "interval"]
    trigger_config: dict
    executor_type: Literal["agent", "skill_script"]
    executor_config: dict
    is_enabled: bool = True


class ScheduledTaskCreate(ScheduledTaskBase):
    """建立排程請求"""

    pass


class ScheduledTaskUpdate(BaseModel):
    """更新排程請求（全部欄位選填）"""

    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    trigger_type: Literal["cron", "interval"] | None = None
    trigger_config: dict | None = None
    executor_type: Literal["agent", "skill_script"] | None = None
    executor_config: dict | None = None
    is_enabled: bool | None = None


class ScheduledTaskToggle(BaseModel):
    """啟停用切換請求"""

    is_enabled: bool


class ScheduledTask(ScheduledTaskBase):
    """排程任務完整資料（DB 回傳）"""

    id: UUID
    created_by: int | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_run_success: bool | None = None
    last_run_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ScheduledTaskResponse(ScheduledTask):
    """API 回傳的排程任務（含 source 標記）"""

    source: Literal["dynamic", "system", "module"] = "dynamic"


class ScheduledTaskListResponse(BaseModel):
    """排程列表回應"""

    tasks: list[ScheduledTaskResponse]
