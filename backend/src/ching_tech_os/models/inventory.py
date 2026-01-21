"""物料管理相關資料模型"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    """交易類型"""
    IN = "in"    # 進貨
    OUT = "out"  # 出貨


def calculate_is_low_stock(current_stock: Decimal | None, min_stock: Decimal | None) -> bool:
    """計算是否庫存不足"""
    if current_stock is None or min_stock is None:
        return False
    return current_stock < min_stock


# ============================================
# 物料主檔
# ============================================


class InventoryItemBase(BaseModel):
    """物料基礎欄位"""

    name: str = Field(..., description="物料名稱")
    model: str | None = Field(None, description="型號")
    specification: str | None = Field(None, description="規格")
    unit: str | None = Field(None, description="單位（如：個、台、公斤）")
    category: str | None = Field(None, description="類別")
    default_vendor: str | None = Field(None, description="預設廠商")
    storage_location: str | None = Field(None, description="存放庫位")
    min_stock: Decimal | None = Field(Decimal("0"), description="最低庫存量")
    notes: str | None = Field(None, description="備註")


class InventoryItemCreate(InventoryItemBase):
    """建立物料請求"""

    pass


class InventoryItemUpdate(BaseModel):
    """更新物料請求"""

    name: str | None = None
    model: str | None = None
    specification: str | None = None
    unit: str | None = None
    category: str | None = None
    default_vendor: str | None = None
    storage_location: str | None = None
    min_stock: Decimal | None = None
    notes: str | None = None


class InventoryItemResponse(InventoryItemBase):
    """物料回應"""

    id: UUID
    current_stock: Decimal = Field(Decimal("0"), description="目前庫存")
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    is_low_stock: bool = Field(False, description="是否庫存不足")


class InventoryItemListItem(BaseModel):
    """物料列表項目"""

    id: UUID
    name: str
    model: str | None = None
    specification: str | None = None
    unit: str | None = None
    category: str | None = None
    storage_location: str | None = None
    default_vendor: str | None = None
    current_stock: Decimal = Decimal("0")
    min_stock: Decimal | None = None
    is_low_stock: bool = False
    updated_at: datetime


class InventoryItemListResponse(BaseModel):
    """物料列表回應"""

    items: list[InventoryItemListItem]
    total: int


# ============================================
# 進出貨記錄
# ============================================


class InventoryTransactionBase(BaseModel):
    """進出貨記錄基礎欄位"""

    type: TransactionType = Field(..., description="類型：in（進貨）/ out（出貨）")
    quantity: Decimal = Field(..., description="數量")
    transaction_date: date = Field(default_factory=date.today, description="進出貨日期")
    vendor: str | None = Field(None, description="廠商")
    project_id: UUID | None = Field(None, description="關聯專案")
    notes: str | None = Field(None, description="備註")


class InventoryTransactionCreate(InventoryTransactionBase):
    """建立進出貨記錄請求"""

    pass


class InventoryTransactionUpdate(BaseModel):
    """更新進出貨記錄請求"""

    type: TransactionType | None = None
    quantity: Decimal | None = None
    transaction_date: date | None = None
    vendor: str | None = None
    project_id: UUID | None = None
    notes: str | None = None


class InventoryTransactionResponse(InventoryTransactionBase):
    """進出貨記錄回應"""

    id: UUID
    item_id: UUID
    created_at: datetime
    created_by: str | None = None
    # 關聯專案資訊
    project_name: str | None = None


class InventoryTransactionListItem(BaseModel):
    """進出貨記錄列表項目"""

    id: UUID
    item_id: UUID
    type: TransactionType
    quantity: Decimal
    transaction_date: date
    vendor: str | None = None
    project_id: UUID | None = None
    project_name: str | None = None
    notes: str | None = None
    created_at: datetime
    created_by: str | None = None


class InventoryTransactionListResponse(BaseModel):
    """進出貨記錄列表回應"""

    items: list[InventoryTransactionListItem]
    total: int


# ============================================
# 訂購記錄
# ============================================


class OrderStatus(str, Enum):
    """訂購狀態"""
    PENDING = "pending"       # 待下單
    ORDERED = "ordered"       # 已下單
    DELIVERED = "delivered"   # 已交貨
    CANCELLED = "cancelled"   # 已取消


class InventoryOrderBase(BaseModel):
    """訂購記錄基礎欄位"""

    order_quantity: Decimal = Field(..., description="訂購數量")
    order_date: date | None = Field(None, description="下單日期")
    expected_delivery_date: date | None = Field(None, description="預計交貨日期")
    vendor: str | None = Field(None, description="訂購廠商")
    project_id: UUID | None = Field(None, description="關聯專案")
    notes: str | None = Field(None, description="備註")


class InventoryOrderCreate(InventoryOrderBase):
    """建立訂購記錄請求"""
    pass


class InventoryOrderUpdate(BaseModel):
    """更新訂購記錄請求"""

    order_quantity: Decimal | None = None
    order_date: date | None = None
    expected_delivery_date: date | None = None
    actual_delivery_date: date | None = None
    status: OrderStatus | None = None
    vendor: str | None = None
    project_id: UUID | None = None
    notes: str | None = None


class InventoryOrderResponse(InventoryOrderBase):
    """訂購記錄回應"""

    id: UUID
    item_id: UUID
    actual_delivery_date: date | None = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    # 關聯資訊
    item_name: str | None = None
    project_name: str | None = None


class InventoryOrderListItem(BaseModel):
    """訂購記錄列表項目"""

    id: UUID
    item_id: UUID
    item_name: str | None = None
    order_quantity: Decimal
    order_date: date | None = None
    expected_delivery_date: date | None = None
    actual_delivery_date: date | None = None
    status: OrderStatus
    vendor: str | None = None
    project_id: UUID | None = None
    project_name: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None


class InventoryOrderListResponse(BaseModel):
    """訂購記錄列表回應"""

    items: list[InventoryOrderListItem]
    total: int


# ============================================
# 庫存摘要
# ============================================


class InventoryStockSummary(BaseModel):
    """庫存摘要"""

    item_id: UUID
    item_name: str
    current_stock: Decimal
    min_stock: Decimal | None
    is_low_stock: bool
    recent_in: Decimal = Decimal("0")  # 近期進貨總量
    recent_out: Decimal = Decimal("0")  # 近期出貨總量
