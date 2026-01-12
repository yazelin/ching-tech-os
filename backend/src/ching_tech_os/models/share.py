"""公開分享連結相關資料模型"""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class ShareLinkCreate(BaseModel):
    """建立分享連結請求"""

    resource_type: Literal["knowledge", "project", "nas_file", "project_attachment"]
    resource_id: str
    expires_in: str | None = "24h"  # 1h, 24h, 7d, null（永久）


class ShareLinkResponse(BaseModel):
    """分享連結回應"""

    token: str
    url: str
    full_url: str
    resource_type: str
    resource_id: str
    resource_title: str
    expires_at: datetime | None
    access_count: int = 0
    created_at: datetime
    created_by: str | None = None  # 建立者（管理員檢視時會用到）
    is_expired: bool = False


class ShareLinkListResponse(BaseModel):
    """分享連結列表回應"""

    links: list[ShareLinkResponse]
    is_admin: bool = False  # 用戶是否為管理員（決定是否顯示全部切換）


class PublicKnowledgeData(BaseModel):
    """公開知識庫資料"""

    id: str
    title: str
    content: str
    attachments: list[dict] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PublicProjectData(BaseModel):
    """公開專案資料"""

    id: str
    name: str
    description: str | None
    status: str
    start_date: str | None
    end_date: str | None
    milestones: list[dict] = Field(default_factory=list)
    members: list[dict] = Field(default_factory=list)  # 只顯示姓名和角色


class PublicResourceResponse(BaseModel):
    """公開資源回應"""

    type: Literal["knowledge", "project", "nas_file", "project_attachment"]
    data: dict[str, Any]
    shared_by: str
    shared_at: datetime
    expires_at: datetime | None
