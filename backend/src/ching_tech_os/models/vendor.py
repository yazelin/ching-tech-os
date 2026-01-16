"""廠商主檔相關資料模型"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class VendorBase(BaseModel):
    """廠商基礎欄位"""

    erp_code: str | None = None  # ERP 系統廠商編號
    name: str  # 廠商名稱
    short_name: str | None = None  # 簡稱
    contact_person: str | None = None  # 聯絡人
    phone: str | None = None  # 電話
    fax: str | None = None  # 傳真
    email: str | None = None  # Email
    address: str | None = None  # 地址
    tax_id: str | None = None  # 統一編號
    payment_terms: str | None = None  # 付款條件
    notes: str | None = None  # 備註


class VendorCreate(VendorBase):
    """建立廠商請求"""

    pass


class VendorUpdate(BaseModel):
    """更新廠商請求"""

    erp_code: str | None = None
    name: str | None = None
    short_name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None
    address: str | None = None
    tax_id: str | None = None
    payment_terms: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class VendorResponse(VendorBase):
    """廠商回應"""

    id: UUID
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None


class VendorListItem(BaseModel):
    """廠商列表項目"""

    id: UUID
    erp_code: str | None = None
    name: str
    short_name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    is_active: bool = True


class VendorListResponse(BaseModel):
    """廠商列表回應"""

    items: list[VendorListItem]
    total: int
