"""專案管理相關資料模型"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# 專案成員
# ============================================


class ProjectMemberBase(BaseModel):
    """專案成員基礎欄位"""

    name: str
    role: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    is_internal: bool = True
    user_id: int | None = None  # 關聯的 CTOS 用戶 ID


class ProjectMemberCreate(ProjectMemberBase):
    """建立專案成員請求"""

    pass


class ProjectMemberUpdate(BaseModel):
    """更新專案成員請求"""

    name: str | None = None
    role: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    is_internal: bool | None = None
    user_id: int | None = None  # 關聯的 CTOS 用戶 ID


class ProjectMemberResponse(ProjectMemberBase):
    """專案成員回應"""

    id: UUID
    project_id: UUID
    created_at: datetime
    user_username: str | None = None  # 關聯用戶的 username
    user_display_name: str | None = None  # 關聯用戶的顯示名稱


# ============================================
# 會議記錄
# ============================================


class ProjectMeetingBase(BaseModel):
    """會議記錄基礎欄位"""

    title: str
    meeting_date: datetime
    location: str | None = None
    attendees: list[str] = Field(default_factory=list)
    content: str | None = None


class ProjectMeetingCreate(ProjectMeetingBase):
    """建立會議記錄請求"""

    pass


class ProjectMeetingUpdate(BaseModel):
    """更新會議記錄請求"""

    title: str | None = None
    meeting_date: datetime | None = None
    location: str | None = None
    attendees: list[str] | None = None
    content: str | None = None


class ProjectMeetingResponse(ProjectMeetingBase):
    """會議記錄回應"""

    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None


class ProjectMeetingListItem(BaseModel):
    """會議記錄列表項目"""

    id: UUID
    title: str
    meeting_date: datetime
    location: str | None = None
    attendees: list[str] = Field(default_factory=list)


# ============================================
# 專案附件
# ============================================


class ProjectAttachmentBase(BaseModel):
    """專案附件基礎欄位"""

    filename: str
    file_type: str | None = None
    file_size: int | None = None
    storage_path: str
    description: str | None = None


class ProjectAttachmentCreate(BaseModel):
    """建立專案附件請求（內部使用）"""

    filename: str
    file_type: str | None = None
    file_size: int | None = None
    storage_path: str
    description: str | None = None
    uploaded_by: str | None = None


class ProjectAttachmentUpdate(BaseModel):
    """更新專案附件請求"""

    description: str | None = None


class ProjectAttachmentResponse(ProjectAttachmentBase):
    """專案附件回應"""

    id: UUID
    project_id: UUID
    uploaded_at: datetime
    uploaded_by: str | None = None


# ============================================
# 專案連結
# ============================================


class ProjectLinkBase(BaseModel):
    """專案連結基礎欄位"""

    title: str
    url: str
    description: str | None = None


class ProjectLinkCreate(ProjectLinkBase):
    """建立專案連結請求"""

    pass


class ProjectLinkUpdate(BaseModel):
    """更新專案連結請求"""

    title: str | None = None
    url: str | None = None
    description: str | None = None


class ProjectLinkResponse(ProjectLinkBase):
    """專案連結回應"""

    id: UUID
    project_id: UUID
    created_at: datetime

    @property
    def link_type(self) -> str:
        """自動判斷連結類型"""
        if self.url.startswith("/") or self.url.startswith("nas://"):
            return "nas"
        return "external"


# ============================================
# 專案里程碑
# ============================================


class ProjectMilestoneBase(BaseModel):
    """里程碑基礎欄位"""

    name: str
    milestone_type: str = "custom"  # design, manufacture, delivery, field_test, acceptance, custom
    planned_date: date | None = None
    actual_date: date | None = None
    status: str = "pending"  # pending, in_progress, completed, delayed
    notes: str | None = None
    sort_order: int = 0


class ProjectMilestoneCreate(ProjectMilestoneBase):
    """建立里程碑請求"""

    pass


class ProjectMilestoneUpdate(BaseModel):
    """更新里程碑請求"""

    name: str | None = None
    milestone_type: str | None = None
    planned_date: date | None = None
    actual_date: date | None = None
    status: str | None = None
    notes: str | None = None
    sort_order: int | None = None


class ProjectMilestoneResponse(ProjectMilestoneBase):
    """里程碑回應"""

    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime


# ============================================
# 專案發包/交貨期程
# ============================================


class DeliveryScheduleBase(BaseModel):
    """發包/交貨期程基礎欄位"""

    vendor: str  # 廠商名稱
    item: str  # 料件名稱
    quantity: str | None = None  # 數量（含單位，如「2 台」）
    order_date: date | None = None  # 發包日期
    expected_delivery_date: date | None = None  # 預計交貨日期
    actual_delivery_date: date | None = None  # 實際到貨日期
    status: str = "pending"  # pending, ordered, delivered, completed
    notes: str | None = None


class DeliveryScheduleCreate(BaseModel):
    """建立發包記錄請求"""

    vendor: str
    item: str
    quantity: str | None = None
    order_date: date | None = None
    expected_delivery_date: date | None = None
    status: str = "pending"
    notes: str | None = None


class DeliveryScheduleUpdate(BaseModel):
    """更新發包記錄請求"""

    vendor: str | None = None
    item: str | None = None
    quantity: str | None = None
    order_date: date | None = None
    expected_delivery_date: date | None = None
    actual_delivery_date: date | None = None
    status: str | None = None
    notes: str | None = None


class DeliveryScheduleResponse(DeliveryScheduleBase):
    """發包記錄回應"""

    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None


# ============================================
# 專案
# ============================================


class ProjectBase(BaseModel):
    """專案基礎欄位"""

    name: str
    description: str | None = None
    status: str = "active"
    start_date: date | None = None
    end_date: date | None = None


class ProjectCreate(ProjectBase):
    """建立專案請求"""

    pass


class ProjectUpdate(BaseModel):
    """更新專案請求"""

    name: str | None = None
    description: str | None = None
    status: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ProjectResponse(ProjectBase):
    """專案回應"""

    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None


class ProjectDetailResponse(ProjectResponse):
    """專案詳情回應（包含關聯資料）"""

    members: list[ProjectMemberResponse] = Field(default_factory=list)
    meetings: list[ProjectMeetingListItem] = Field(default_factory=list)
    attachments: list[ProjectAttachmentResponse] = Field(default_factory=list)
    links: list[ProjectLinkResponse] = Field(default_factory=list)
    milestones: list[ProjectMilestoneResponse] = Field(default_factory=list)
    deliveries: list[DeliveryScheduleResponse] = Field(default_factory=list)


class ProjectListItem(BaseModel):
    """專案列表項目"""

    id: UUID
    name: str
    status: str
    start_date: date | None = None
    end_date: date | None = None
    updated_at: datetime
    member_count: int = 0
    meeting_count: int = 0
    attachment_count: int = 0


class ProjectListResponse(BaseModel):
    """專案列表回應"""

    items: list[ProjectListItem]
    total: int
