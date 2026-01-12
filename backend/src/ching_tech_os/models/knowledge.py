"""知識庫相關資料模型"""

from datetime import date
from pydantic import BaseModel, Field


class KnowledgeTags(BaseModel):
    """知識標籤"""

    projects: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    level: str | None = None


class KnowledgeSource(BaseModel):
    """知識來源資訊"""

    project: str | None = None
    path: str | None = None
    commit: str | None = None


class KnowledgeAttachment(BaseModel):
    """知識附件"""

    type: str  # image, video, document, etc.
    path: str
    size: str | None = None
    description: str | None = None


class AttachmentUpdate(BaseModel):
    """附件更新請求"""

    type: str | None = None  # file, image, video, document
    description: str | None = None


class KnowledgeMetadata(BaseModel):
    """知識元資料（對應 YAML Front Matter）"""

    id: str
    title: str
    type: str = "knowledge"  # context, knowledge, operations, reference
    category: str = "technical"  # technical, business, management
    scope: str = "global"  # global（全域）或 personal（個人）
    owner: str | None = None  # 擁有者帳號（None 表示全域知識）
    tags: KnowledgeTags = Field(default_factory=KnowledgeTags)
    source: KnowledgeSource = Field(default_factory=KnowledgeSource)
    related: list[str] = Field(default_factory=list)
    attachments: list[KnowledgeAttachment] = Field(default_factory=list)
    author: str = "system"
    created_at: date
    updated_at: date


class KnowledgeCreate(BaseModel):
    """建立知識請求"""

    title: str
    slug: str | None = None  # 若未提供則自動產生
    content: str
    type: str = "knowledge"
    category: str = "technical"
    scope: str = "personal"  # 預設為個人知識
    tags: KnowledgeTags = Field(default_factory=KnowledgeTags)
    source: KnowledgeSource | None = None
    related: list[str] = Field(default_factory=list)
    author: str = "system"


class KnowledgeUpdate(BaseModel):
    """更新知識請求"""

    title: str | None = None
    content: str | None = None
    type: str | None = None
    category: str | None = None
    tags: KnowledgeTags | None = None
    source: KnowledgeSource | None = None
    related: list[str] | None = None


class KnowledgeResponse(BaseModel):
    """知識回應（含內容）"""

    id: str
    title: str
    type: str
    category: str
    scope: str = "global"  # global 或 personal
    owner: str | None = None  # 擁有者帳號
    tags: KnowledgeTags
    source: KnowledgeSource
    related: list[str]
    attachments: list[KnowledgeAttachment]
    author: str
    created_at: date
    updated_at: date
    content: str  # Markdown 內容


class KnowledgeListItem(BaseModel):
    """知識列表項目（不含內容）"""

    id: str
    title: str
    type: str
    category: str
    scope: str = "global"  # global 或 personal
    owner: str | None = None  # 擁有者帳號
    tags: KnowledgeTags
    author: str
    updated_at: date
    snippet: str | None = None  # 搜尋時的匹配片段


class KnowledgeListResponse(BaseModel):
    """知識列表回應"""

    items: list[KnowledgeListItem]
    total: int
    query: str | None = None


class TagsResponse(BaseModel):
    """標籤列表回應"""

    projects: list[str]
    types: list[str]
    categories: list[str]
    roles: list[str]
    levels: list[str]
    topics: list[str]


class HistoryEntry(BaseModel):
    """版本歷史項目"""

    commit: str
    author: str
    date: str
    message: str


class HistoryResponse(BaseModel):
    """版本歷史回應"""

    id: str
    entries: list[HistoryEntry]


class VersionResponse(BaseModel):
    """特定版本內容回應"""

    id: str
    commit: str
    content: str


class IndexEntry(BaseModel):
    """索引中的知識項目"""

    id: str
    title: str
    filename: str
    type: str
    category: str
    scope: str = "global"  # global 或 personal
    owner: str | None = None  # 擁有者帳號
    tags: KnowledgeTags
    author: str
    created_at: str
    updated_at: str


class KnowledgeIndex(BaseModel):
    """知識庫索引"""

    version: int = 1
    last_updated: str | None = None
    next_id: int = 1
    entries: list[IndexEntry] = Field(default_factory=list)
    tags: TagsResponse = Field(
        default_factory=lambda: TagsResponse(
            projects=["common"],  # 專案從資料庫動態載入，這裡只保留通用選項
            types=["context", "knowledge", "operations", "reference"],
            categories=["technical", "business", "management"],
            roles=["engineer", "pm", "manager", "all"],
            levels=["beginner", "intermediate", "advanced"],
            topics=[],
        )
    )
