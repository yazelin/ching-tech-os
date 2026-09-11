"""專案模組資料模型

對應 migration 028 的四張表：projects / project_members / milestones / tasks。
狀態值用 Literal 鎖住，避免前端送進沒定義的狀態。
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field
from typing import Literal

# 規格第一節定義的狀態集合
ProjectStatus = Literal["planning", "active", "on_hold", "completed", "cancelled"]
MilestoneStatus = Literal["pending", "in_progress", "completed"]
TaskStatus = Literal["todo", "doing", "done"]
MemberRole = Literal["owner", "member"]


# ============================================================
# 專案主檔
# ============================================================


class ProjectBase(BaseModel):
    """專案基礎欄位"""

    name: str
    customer: str | None = None
    status: ProjectStatus = "active"
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class ProjectCreate(ProjectBase):
    """建立專案請求"""


class ProjectUpdate(BaseModel):
    """更新專案請求（只更新有給的欄位）"""

    name: str | None = None
    customer: str | None = None
    status: ProjectStatus | None = None
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class ProjectListItem(BaseModel):
    """專案列表項目"""

    id: UUID
    name: str
    customer: str | None = None
    status: str
    owner_id: int | None = None
    owner_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime
    updated_at: datetime
    # 進度百分比 = done 任務數 ÷ 任務總數，沒有任務時為 0
    progress: int = 0
    member_count: int = 0
    overdue_milestones: int = 0


class ProjectListResponse(BaseModel):
    """專案列表回應"""

    items: list[ProjectListItem]
    total: int


# ============================================================
# 成員
# ============================================================


class ProjectMemberCreate(BaseModel):
    """加入成員請求"""

    user_id: int


class ProjectMemberResponse(BaseModel):
    """成員回應（JOIN users 取得顯示名稱）"""

    user_id: int
    username: str | None = None
    display_name: str | None = None
    role: str = "member"


# ============================================================
# 里程碑
# ============================================================


class MilestoneBase(BaseModel):
    """里程碑基礎欄位"""

    name: str
    due_date: date
    completed_at: date | None = None
    status: MilestoneStatus = "pending"
    sort_order: int = 0


class MilestoneCreate(MilestoneBase):
    """建立里程碑請求"""


class MilestoneUpdate(BaseModel):
    """更新里程碑請求"""

    name: str | None = None
    due_date: date | None = None
    completed_at: date | None = None
    status: MilestoneStatus | None = None
    sort_order: int | None = None


class MilestoneResponse(MilestoneBase):
    """里程碑回應"""

    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
    # 逾期 = due_date < 今天 且 status <> completed
    is_overdue: bool = False


# ============================================================
# 任務
# ============================================================


class TaskBase(BaseModel):
    """任務基礎欄位"""

    title: str
    description: str | None = None
    milestone_id: UUID | None = None
    assignee_id: int | None = None
    status: TaskStatus = "todo"
    due_date: date | None = None
    sort_order: int = 0


class TaskCreate(TaskBase):
    """建立任務請求"""


class TaskUpdate(BaseModel):
    """更新任務請求"""

    title: str | None = None
    description: str | None = None
    milestone_id: UUID | None = None
    assignee_id: int | None = None
    status: TaskStatus | None = None
    due_date: date | None = None
    sort_order: int | None = None


class TaskResponse(TaskBase):
    """任務回應"""

    id: UUID
    project_id: UUID
    assignee_name: str | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================
# 綁定群組與明細
# ============================================================


class ProjectBotGroupResponse(BaseModel):
    """綁定到專案的 Bot 群組（bot_groups.name 取別名 group_name）"""

    id: UUID
    platform_type: str = "line"
    group_name: str | None = None


class ProjectDetailResponse(BaseModel):
    """專案明細"""

    id: UUID
    name: str
    customer: str | None = None
    status: str
    owner_id: int | None = None
    owner_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    progress: int = 0
    members: list[ProjectMemberResponse] = Field(default_factory=list)
    milestones: list[MilestoneResponse] = Field(default_factory=list)
    tasks: list[TaskResponse] = Field(default_factory=list)
    bot_groups: list[ProjectBotGroupResponse] = Field(default_factory=list)
    knowledge_count: int = 0


# ============================================================
# Dashboard 摘要
# ============================================================


class OverdueMilestoneItem(BaseModel):
    """逾期里程碑（dashboard 用）"""

    project_id: UUID
    project_name: str
    milestone_id: UUID
    name: str
    due_date: date
    days_overdue: int


class ProjectSummaryResponse(BaseModel):
    """dashboard 摘要"""

    active_count: int = 0
    overdue_milestones: list[OverdueMilestoneItem] = Field(default_factory=list)
