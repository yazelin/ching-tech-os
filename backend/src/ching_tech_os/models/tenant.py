"""租戶（Tenant）相關資料模型"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class TenantSettings(BaseModel):
    """租戶設定"""

    # 功能開關
    enable_linebot: bool = True
    enable_ai_assistant: bool = True
    enable_knowledge_base: bool = True
    enable_project_management: bool = True
    enable_inventory: bool = True
    enable_vendor_management: bool = True  # 廠商管理

    # 配額設定
    max_users: int | None = None  # None 表示無限制
    max_projects: int | None = None
    max_ai_calls_per_day: int | None = None

    # Line Bot 設定（多租戶支援）
    line_channel_id: str | None = None  # Line Channel ID
    line_channel_secret: str | None = None  # 加密儲存
    line_channel_access_token: str | None = None  # 加密儲存

    # 自訂設定
    custom: dict = Field(default_factory=dict)


class TenantBase(BaseModel):
    """租戶基本資訊"""

    code: str = Field(..., min_length=2, max_length=50, description="租戶代碼（用於登入識別）")
    name: str = Field(..., min_length=1, max_length=200, description="租戶名稱")


class TenantCreate(TenantBase):
    """建立租戶請求"""

    plan: str = "trial"
    storage_quota_mb: int = 5120  # 預設 5GB
    trial_days: int | None = 30  # 試用天數，None 表示不是試用


class TenantUpdate(BaseModel):
    """更新租戶請求"""

    name: str | None = None
    status: str | None = None  # active, suspended, trial
    plan: str | None = None  # trial, basic, pro, enterprise
    storage_quota_mb: int | None = None
    settings: TenantSettings | None = None


class TenantInfo(TenantBase):
    """租戶資訊（API 回應）"""

    id: UUID
    status: str
    plan: str
    storage_quota_mb: int
    storage_used_mb: int
    settings: TenantSettings
    trial_ends_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TenantBrief(BaseModel):
    """租戶簡要資訊（用於列表、登入回應等）"""

    id: UUID
    code: str
    name: str
    status: str
    plan: str


class TenantUsage(BaseModel):
    """租戶使用量統計"""

    tenant_id: UUID
    storage_used_mb: int
    storage_quota_mb: int
    storage_percentage: float
    user_count: int
    project_count: int
    knowledge_count: int
    ai_calls_today: int
    ai_calls_this_month: int


class TenantAdminBase(BaseModel):
    """租戶管理員基本資訊"""

    user_id: int | None = None  # 選擇現有使用者時使用
    role: str = "admin"  # admin, owner


class TenantAdminCreate(BaseModel):
    """新增租戶管理員請求 - 支援建立新帳號"""

    # 方式一：選擇現有使用者
    user_id: int | None = None

    # 方式二：建立新帳號
    username: str | None = None
    display_name: str | None = None
    password: str | None = None  # 空值時自動產生臨時密碼
    must_change_password: bool = True

    role: str = "admin"  # admin, owner


class TenantAdminCreateResponse(BaseModel):
    """新增租戶管理員回應"""

    success: bool
    admin: "TenantAdminInfo | None" = None
    temporary_password: str | None = None  # 自動產生的臨時密碼
    error: str | None = None


class TenantAdminInfo(BaseModel):
    """租戶管理員資訊"""

    id: UUID
    tenant_id: UUID
    user_id: int
    username: str  # 從 user 關聯取得
    display_name: str | None
    role: str = "admin"
    created_at: datetime


# === API 請求/回應模型 ===


class TenantListResponse(BaseModel):
    """租戶列表回應"""

    tenants: list[TenantInfo]
    total: int


class TenantExportRequest(BaseModel):
    """匯出租戶資料請求"""

    include_files: bool = True  # 是否包含檔案
    include_ai_logs: bool = False  # AI 日誌通常很大，預設不包含


class TenantExportResponse(BaseModel):
    """匯出租戶資料回應"""

    download_url: str
    expires_at: datetime
    file_size_mb: float


class TenantImportRequest(BaseModel):
    """匯入租戶資料請求"""

    source_file_path: str  # 上傳的 ZIP 檔案路徑
    merge_mode: str = "replace"  # replace: 取代現有資料, merge: 合併


# === Line Bot 設定模型 ===


class LineBotSettingsUpdate(BaseModel):
    """更新 Line Bot 設定請求"""

    channel_id: str | None = Field(None, description="Line Channel ID")
    channel_secret: str | None = Field(None, description="Line Channel Secret（明文）")
    access_token: str | None = Field(None, description="Line Channel Access Token（明文）")


class LineBotSettingsResponse(BaseModel):
    """Line Bot 設定回應（不包含敏感資訊）"""

    configured: bool = Field(..., description="是否已設定 Line Bot")
    channel_id: str | None = Field(None, description="Line Channel ID")
    # 不回傳 channel_secret 和 access_token


class LineBotTestResponse(BaseModel):
    """Line Bot 測試回應"""

    success: bool
    bot_info: dict | None = None  # 包含 bot 名稱等資訊
    error: str | None = None


# === 租戶使用者列表模型 ===


class TenantUserBrief(BaseModel):
    """租戶使用者簡要資訊（供平台管理員選擇管理員用）"""

    id: int
    username: str
    display_name: str | None
    role: str  # user, tenant_admin
    is_admin: bool  # 是否已是此租戶的管理員


class TenantUserListResponse(BaseModel):
    """租戶使用者列表回應"""

    users: list[TenantUserBrief]
