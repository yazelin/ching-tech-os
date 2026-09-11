"""往來與物料模組資料模型

對應 migration 030 的十張表。狀態與異動原因用 Literal 鎖住，避免前端或 agent
送進沒定義的值。Update 模型對資料表 NOT NULL 的欄位明確送 null 時回 422
（同 models/project.py 的 `_not_null` 慣例）。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

# 規格第二節定義的集合
PurchaseOrderStatus = Literal["draft", "ordered", "partial", "received", "cancelled"]
# 單頭可以直接改成的狀態：partial／received 由收貨算出來、cancelled 只能走 cancel
EditablePurchaseOrderStatus = Literal["draft", "ordered"]
StockReason = Literal[
    "receipt", "issue", "adjust", "transfer_in", "transfer_out", "import"
]
PartyRole = Literal["supplier", "customer", "both"]
AuditVia = Literal["mcp", "rest"]


def _not_null(value):
    """更新請求裡明確送 null 到 NOT NULL 欄位：擋在 422，不要進到資料庫才爆"""
    if value is None:
        raise ValueError("此欄位不可為 null")
    return value


# ============================================================
# 往來對象
# ============================================================


class PartyContactBase(BaseModel):
    """聯絡人基礎欄位"""

    name: str
    title: str | None = None
    phone: str | None = None
    mobile: str | None = None
    email: str | None = None
    is_primary: bool = False
    notes: str | None = None


class PartyContactCreate(PartyContactBase):
    """新增聯絡人請求"""


class PartyContactUpdate(BaseModel):
    """更新聯絡人請求（只更新有給的欄位）"""

    name: str | None = None
    title: str | None = None
    phone: str | None = None
    mobile: str | None = None
    email: str | None = None
    is_primary: bool | None = None
    notes: str | None = None

    # 資料表 NOT NULL 的欄位不接受明確送 null
    _reject_null = field_validator("name", "is_primary", mode="before")(_not_null)


class PartyContactResponse(PartyContactBase):
    """聯絡人回應"""

    id: UUID
    party_id: UUID
    created_at: datetime
    updated_at: datetime


class PartyContactUpdateResponse(PartyContactResponse):
    """更新聯絡人回應（多帶 `audit_id`）"""

    audit_id: UUID | None = None


class PartyAddressBase(BaseModel):
    """地址基礎欄位"""

    address: str
    label: str | None = None
    city: str | None = None
    is_primary: bool = False


class PartyAddressCreate(PartyAddressBase):
    """新增地址請求"""


class PartyAddressUpdate(BaseModel):
    """更新地址請求（只更新有給的欄位）"""

    address: str | None = None
    label: str | None = None
    city: str | None = None
    is_primary: bool | None = None

    _reject_null = field_validator("address", "is_primary", mode="before")(_not_null)


class PartyAddressResponse(PartyAddressBase):
    """地址回應"""

    id: UUID
    party_id: UUID
    created_at: datetime
    updated_at: datetime


class PartyAddressUpdateResponse(PartyAddressResponse):
    """更新地址回應（多帶 `audit_id`）"""

    audit_id: UUID | None = None


class PartyBase(BaseModel):
    """往來對象基礎欄位"""

    name: str
    short_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    is_supplier: bool = False
    is_customer: bool = False
    tax_id: str | None = None
    industry: str | None = None
    payment_terms: str | None = None
    notes: str | None = None
    source_ref: str | None = None


class PartyCreate(PartyBase):
    """建立往來對象請求（可一次帶聯絡人與地址）"""

    contacts: list[PartyContactCreate] = Field(default_factory=list)
    addresses: list[PartyAddressCreate] = Field(default_factory=list)


class PartyUpdate(BaseModel):
    """更新往來對象請求（只更新有給的欄位）"""

    name: str | None = None
    short_name: str | None = None
    aliases: list[str] | None = None
    is_supplier: bool | None = None
    is_customer: bool | None = None
    tax_id: str | None = None
    industry: str | None = None
    payment_terms: str | None = None
    notes: str | None = None
    source_ref: str | None = None

    # 資料表 NOT NULL 的欄位不接受明確送 null（沒送就是不動）
    _reject_null = field_validator(
        "name", "aliases", "is_supplier", "is_customer", mode="before"
    )(_not_null)


class PartyMergeRequest(BaseModel):
    """合併請求：把 drop 併進 keep"""

    keep_id: UUID
    drop_id: UUID


class PartyListItem(BaseModel):
    """往來對象列表項目"""

    id: UUID
    name: str
    short_name: str | None = None
    is_supplier: bool = False
    is_customer: bool = False
    tax_id: str | None = None
    industry: str | None = None
    primary_contact: str | None = None
    primary_phone: str | None = None
    created_at: datetime
    updated_at: datetime


class PartyListResponse(BaseModel):
    """往來對象列表回應"""

    items: list[PartyListItem]
    total: int


class PartyPurchaseOrderItem(BaseModel):
    """往來對象明細裡的近期採購單"""

    id: UUID
    po_no: str
    status: str
    order_date: date | None = None
    expected_date: date | None = None
    total_amount: Decimal | None = None


class PartyProjectItem(BaseModel):
    """往來對象相關專案（採購單掛的專案）"""

    id: UUID
    name: str
    status: str


class PartyDetailResponse(PartyBase):
    """往來對象明細（聚合聯絡人、地址、近期採購單、相關專案、知識庫條目數）

    `audit_id` 只有建立／更新的回應才有值（GET 明細是 None）。
    """

    id: UUID
    audit_id: UUID | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    contacts: list[PartyContactResponse] = Field(default_factory=list)
    addresses: list[PartyAddressResponse] = Field(default_factory=list)
    purchase_orders: list[PartyPurchaseOrderItem] = Field(default_factory=list)
    projects: list[PartyProjectItem] = Field(default_factory=list)
    knowledge_count: int = 0


# ============================================================
# 物料
# ============================================================


class ItemBase(BaseModel):
    """物料基礎欄位"""

    code: str
    name: str
    spec: str | None = None
    unit: str | None = None
    item_group: str | None = None
    default_supplier_id: UUID | None = None
    purchase_price: Decimal | None = None
    lead_days: int | None = None
    aliases: list[str] = Field(default_factory=list)
    notes: str | None = None
    source_ref: str | None = None


class ItemCreate(ItemBase):
    """建立物料請求"""


class ItemUpdate(BaseModel):
    """更新物料請求"""

    code: str | None = None
    name: str | None = None
    spec: str | None = None
    unit: str | None = None
    item_group: str | None = None
    default_supplier_id: UUID | None = None
    purchase_price: Decimal | None = None
    lead_days: int | None = None
    aliases: list[str] | None = None
    notes: str | None = None
    source_ref: str | None = None

    _reject_null = field_validator("code", "name", "aliases", mode="before")(_not_null)


class ItemListItem(BaseModel):
    """物料列表項目"""

    id: UUID
    code: str
    name: str
    spec: str | None = None
    unit: str | None = None
    item_group: str | None = None
    default_supplier_id: UUID | None = None
    default_supplier_name: str | None = None
    purchase_price: Decimal | None = None
    total_qty: Decimal = Decimal(0)
    created_at: datetime
    updated_at: datetime


class ItemListResponse(BaseModel):
    """物料列表回應"""

    items: list[ItemListItem]
    total: int


class StockBalanceItem(BaseModel):
    """單一倉別的餘額"""

    warehouse_id: UUID
    warehouse_code: str | None = None
    warehouse_name: str | None = None
    qty: Decimal = Decimal(0)


class StockMovementItem(BaseModel):
    """庫存異動紀錄"""

    id: UUID
    item_id: UUID
    warehouse_id: UUID
    warehouse_name: str | None = None
    qty_delta: Decimal
    reason: str
    ref_type: str | None = None
    ref_id: UUID | None = None
    note: str | None = None
    actor_user_id: int | None = None
    created_at: datetime


class ItemDetailResponse(ItemBase):
    """物料明細（主檔＋各倉餘額＋最近異動＋預設供應商）

    `audit_id` 只有建立／更新的回應才有值。
    """

    id: UUID
    audit_id: UUID | None = None
    default_supplier_name: str | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    balances: list[StockBalanceItem] = Field(default_factory=list)
    total_qty: Decimal = Decimal(0)
    movements: list[StockMovementItem] = Field(default_factory=list)


# ============================================================
# 倉庫
# ============================================================


class WarehouseBase(BaseModel):
    """倉庫基礎欄位"""

    code: str
    name: str


class WarehouseCreate(WarehouseBase):
    """建立倉庫請求"""


class WarehouseUpdate(BaseModel):
    """更新倉庫請求"""

    code: str | None = None
    name: str | None = None

    _reject_null = field_validator("code", "name", mode="before")(_not_null)


class WarehouseResponse(WarehouseBase):
    """倉庫回應（`audit_id` 只有建立／更新才有值）"""

    id: UUID
    audit_id: UUID | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class WarehouseListResponse(BaseModel):
    """倉庫列表回應"""

    items: list[WarehouseResponse]
    total: int


# ============================================================
# 庫存
# ============================================================


class StockRow(BaseModel):
    """庫存查詢的一列（item × warehouse）"""

    item_id: UUID
    item_code: str
    item_name: str
    warehouse_id: UUID
    warehouse_code: str | None = None
    warehouse_name: str | None = None
    qty: Decimal = Decimal(0)


class StockListResponse(BaseModel):
    """庫存查詢回應"""

    items: list[StockRow]
    total: int


class StockAdjustRequest(BaseModel):
    """調整庫存請求（qty_delta 可正可負）"""

    item_id: UUID
    warehouse_id: UUID
    qty_delta: Decimal
    reason: StockReason = "adjust"
    note: str | None = None


class StockTransferRequest(BaseModel):
    """倉別調撥請求（qty 必須為正）"""

    item_id: UUID
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    qty: Decimal
    note: str | None = None


class StockMutationResponse(BaseModel):
    """庫存異動結果"""

    audit_id: UUID | None = None
    movements: list[StockMovementItem] = Field(default_factory=list)
    balances: list[StockBalanceItem] = Field(default_factory=list)


# ============================================================
# 採購
# ============================================================


class PurchaseOrderLineCreate(BaseModel):
    """採購單行項（建立用）"""

    item_id: UUID
    qty: Decimal
    unit_price: Decimal | None = None
    description: str | None = None


class PurchaseOrderLineResponse(BaseModel):
    """採購單行項回應"""

    id: UUID
    po_id: UUID
    item_id: UUID
    item_code: str | None = None
    item_name: str | None = None
    description: str | None = None
    qty: Decimal
    unit_price: Decimal | None = None
    received_qty: Decimal = Decimal(0)
    sort_order: int = 0


class PurchaseOrderCreate(BaseModel):
    """建立採購單請求"""

    supplier_id: UUID
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)
    project_id: UUID | None = None
    status: PurchaseOrderStatus = "ordered"
    order_date: date | None = None
    expected_date: date | None = None
    notes: str | None = None


class PurchaseOrderUpdate(BaseModel):
    """更新採購單請求（行項不在這裡改）

    `status` 只收 `draft`／`ordered`：`partial`／`received` 是收貨算出來的，
    `cancelled` 只能走 `POST /{id}/cancel`，從這裡送會被擋在 422。
    """

    supplier_id: UUID | None = None
    project_id: UUID | None = None
    status: EditablePurchaseOrderStatus | None = None
    order_date: date | None = None
    expected_date: date | None = None
    notes: str | None = None

    _reject_null = field_validator("supplier_id", "status", mode="before")(_not_null)


class PurchaseOrderListItem(BaseModel):
    """採購單列表項目"""

    id: UUID
    po_no: str
    supplier_id: UUID
    supplier_name: str | None = None
    project_id: UUID | None = None
    project_name: str | None = None
    status: str
    order_date: date | None = None
    expected_date: date | None = None
    line_count: int = 0
    total_amount: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class PurchaseOrderListResponse(BaseModel):
    """採購單列表回應"""

    items: list[PurchaseOrderListItem]
    total: int


class PurchaseOrderDetailResponse(BaseModel):
    """採購單明細（`audit_id` 只有建立／更新才有值）"""

    id: UUID
    audit_id: UUID | None = None
    po_no: str
    supplier_id: UUID
    supplier_name: str | None = None
    project_id: UUID | None = None
    project_name: str | None = None
    status: str
    order_date: date | None = None
    expected_date: date | None = None
    notes: str | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[PurchaseOrderLineResponse] = Field(default_factory=list)
    total_amount: Decimal | None = None


class ReceiveLine(BaseModel):
    """收貨行：`line_id` 指定行項，或用 `item_id`（該物料只有一行時才行）

    同一張採購單可以有兩行同一個物料，所以行項的 key 是 `line_id`。
    只給 `item_id` 而該物料有多行時，service 會回候選要呼叫端挑。
    """

    line_id: UUID | None = None
    item_id: UUID | None = None
    qty: Decimal

    @model_validator(mode="after")
    def _require_line_or_item(self) -> "ReceiveLine":
        if self.line_id is None and self.item_id is None:
            raise ValueError("收貨行項要給 line_id 或 item_id")
        return self


class PurchaseOrderReceiveRequest(BaseModel):
    """收貨請求：給 lines 收指定行，或 all=True 收全部未收數量"""

    lines: list[ReceiveLine] = Field(default_factory=list)
    all: bool = False
    warehouse_id: UUID | None = None
    note: str | None = None


class PurchaseOrderCancelRequest(BaseModel):
    """取消採購單請求"""

    reason: str | None = None


# ============================================================
# 稽核
# ============================================================


class AuditResponse(BaseModel):
    """稽核紀錄"""

    id: UUID
    entity_type: str
    entity_id: UUID | None = None
    action: str
    diff: dict[str, Any] | None = None
    actor_user_id: int | None = None
    via: str = "mcp"
    agent_name: str | None = None
    created_at: datetime
