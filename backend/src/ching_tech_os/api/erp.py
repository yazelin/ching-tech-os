"""往來與物料模組 API（只服務新前端 ctos-web，與 MCP 工具共用 service）

權限（規格第四節）：讀寫都只看 app 權限，不做成員制，admin 一律過。
- `/api/parties` → `vendor-management`
- `/api/items`、`/api/warehouses`、`/api/stock`、`/api/purchase-orders`
  → `inventory-management`

主檔是軟刪除（`DELETE` 打 `deleted_at`），採購單是取消不是刪。
每個寫入端點的回應都帶 service 寫下的 `audit_id`（在 body 的 `audit_id` 欄位）。
"""

import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..models.auth import SessionData
from ..models.erp import (
    ItemCreate,
    ItemDetailResponse,
    ItemListResponse,
    ItemUpdate,
    PartyAddressCreate,
    PartyAddressUpdate,
    PartyAddressUpdateResponse,
    PartyContactCreate,
    PartyContactUpdate,
    PartyContactUpdateResponse,
    PartyCreate,
    PartyMergeRequest,
    PartyDetailResponse,
    PartyListResponse,
    PartyUpdate,
    PurchaseOrderCancelRequest,
    PurchaseOrderCreate,
    PurchaseOrderDetailResponse,
    PurchaseOrderListResponse,
    PurchaseOrderReceiveRequest,
    PurchaseOrderUpdate,
    StockAdjustRequest,
    StockListResponse,
    StockTransferRequest,
    WarehouseCreate,
    WarehouseListResponse,
    WarehouseResponse,
    WarehouseUpdate,
)
from ..services import erp as erp_core
from ..services import erp_inventory as inventory_service
from ..services import erp_parties as party_service
from ..services import erp_purchasing as purchasing_service
from ..services.permissions import require_app_permission

logger = logging.getLogger(__name__)

# 讀寫共用：有 app 權限就能寫（規格第四節，管理層要「AI 操控第一」）
require_vendor_access = require_app_permission("vendor-management")
require_inventory_access = require_app_permission("inventory-management")

router = APIRouter()
parties_router = APIRouter(prefix="/api/parties", tags=["erp-parties"])
items_router = APIRouter(prefix="/api/items", tags=["erp-items"])
warehouses_router = APIRouter(prefix="/api/warehouses", tags=["erp-warehouses"])
stock_router = APIRouter(prefix="/api/stock", tags=["erp-stock"])
po_router = APIRouter(prefix="/api/purchase-orders", tags=["erp-purchasing"])


def _http_error(exc: Exception) -> HTTPException:
    """把 service 的例外翻成 HTTP 錯誤，不要變成 500"""
    if isinstance(exc, erp_core.NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, erp_core.AmbiguousError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


_ERP_ERRORS = (erp_core.ErpError,)


# ============================================================
# 往來對象
# ============================================================


@parties_router.get("", response_model=PartyListResponse, summary="往來對象清單")
async def list_parties(
    q: str | None = Query(None, description="名稱／簡稱／別名／統編模糊搜尋"),
    role: str | None = Query(None, description="supplier 或 customer"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: SessionData = Depends(require_vendor_access),
) -> PartyListResponse:
    """往來對象清單（軟刪除的不列）"""
    result = await party_service.list_parties(
        q=q, role=role, page=page, page_size=page_size
    )
    return PartyListResponse(**result)


@parties_router.post(
    "",
    response_model=PartyDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立往來對象",
)
async def create_party(
    body: PartyCreate,
    session: SessionData = Depends(require_vendor_access),
) -> PartyDetailResponse:
    """建立往來對象（可一次帶聯絡人與地址）"""
    try:
        row = await party_service.create_party(
            body.model_dump(), actor_user_id=session.user_id, via="rest"
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    return await _party_detail(row["id"], audit_id=row["audit_id"])


@parties_router.post(
    "/merge", response_model=PartyDetailResponse, summary="合併重複的往來對象"
)
async def merge_parties(
    body: PartyMergeRequest,
    session: SessionData = Depends(require_vendor_access),
) -> PartyDetailResponse:
    """把 drop 的聯絡人、地址、採購單掛到 keep，drop 軟刪除"""
    try:
        row = await party_service.merge_parties(
            body.keep_id, body.drop_id, actor_user_id=session.user_id, via="rest"
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    return await _party_detail(row["id"], audit_id=row["audit_id"])


@parties_router.get(
    "/{party_id}", response_model=PartyDetailResponse, summary="往來對象明細"
)
async def get_party(
    party_id: UUID,
    session: SessionData = Depends(require_vendor_access),
) -> PartyDetailResponse:
    """明細：聯絡人、地址、近期採購單、相關專案、知識庫條目數"""
    return await _party_detail(party_id)


@parties_router.put(
    "/{party_id}", response_model=PartyDetailResponse, summary="更新往來對象"
)
async def update_party(
    party_id: UUID,
    body: PartyUpdate,
    session: SessionData = Depends(require_vendor_access),
) -> PartyDetailResponse:
    """只更新有給的欄位；NOT NULL 欄位送 null 會被擋在 422"""
    try:
        row = await party_service.update_party(
            party_id,
            body.model_dump(exclude_unset=True),
            actor_user_id=session.user_id,
            via="rest",
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="往來對象不存在"
        )
    return await _party_detail(party_id, audit_id=row["audit_id"])


@parties_router.delete("/{party_id}", summary="軟刪除往來對象")
async def delete_party(
    party_id: UUID,
    session: SessionData = Depends(require_vendor_access),
) -> dict:
    """軟刪除（`deleted_at`）；之後不進清單也不進模糊解析"""
    audit_id = await party_service.delete_party(
        party_id, actor_user_id=session.user_id, via="rest"
    )
    if audit_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="往來對象不存在"
        )
    return {"success": True, "audit_id": str(audit_id)}


@parties_router.post(
    "/{party_id}/contacts",
    status_code=status.HTTP_201_CREATED,
    summary="新增聯絡人",
)
async def add_party_contact(
    party_id: UUID,
    body: PartyContactCreate,
    session: SessionData = Depends(require_vendor_access),
) -> dict:
    """新增聯絡人；設 is_primary 會把同一家原本的主要聯絡人取消"""
    row = await party_service.add_contact(
        party_id, body.model_dump(), actor_user_id=session.user_id, via="rest"
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="往來對象不存在"
        )
    return {
        "success": True,
        "contact_id": str(row["id"]),
        "audit_id": str(row["audit_id"]),
    }


@parties_router.post(
    "/{party_id}/addresses",
    status_code=status.HTTP_201_CREATED,
    summary="新增地址",
)
async def add_party_address(
    party_id: UUID,
    body: PartyAddressCreate,
    session: SessionData = Depends(require_vendor_access),
) -> dict:
    """新增地址；設 is_primary 會把同一家原本的主要地址取消"""
    row = await party_service.add_address(
        party_id, body.model_dump(), actor_user_id=session.user_id, via="rest"
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="往來對象不存在"
        )
    return {
        "success": True,
        "address_id": str(row["id"]),
        "audit_id": str(row["audit_id"]),
    }


@parties_router.put(
    "/{party_id}/contacts/{contact_id}",
    response_model=PartyContactUpdateResponse,
    summary="更新聯絡人",
)
async def update_party_contact(
    party_id: UUID,
    contact_id: UUID,
    body: PartyContactUpdate,
    session: SessionData = Depends(require_vendor_access),
) -> PartyContactUpdateResponse:
    """只更新有給的欄位；`is_primary=true` 會把同一家其他聯絡人降級"""
    row = await party_service.update_contact(
        party_id,
        contact_id,
        body.model_dump(exclude_unset=True),
        actor_user_id=session.user_id,
        via="rest",
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="聯絡人不存在"
        )
    return PartyContactUpdateResponse(**row)


@parties_router.delete("/{party_id}/contacts/{contact_id}", summary="刪除聯絡人")
async def delete_party_contact(
    party_id: UUID,
    contact_id: UUID,
    session: SessionData = Depends(require_vendor_access),
) -> dict:
    """刪除聯絡人；刪掉主要那筆不自動指派新主要"""
    audit_id = await party_service.delete_contact(
        party_id, contact_id, actor_user_id=session.user_id, via="rest"
    )
    if audit_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="聯絡人不存在"
        )
    return {"success": True, "audit_id": str(audit_id)}


@parties_router.put(
    "/{party_id}/addresses/{address_id}",
    response_model=PartyAddressUpdateResponse,
    summary="更新地址",
)
async def update_party_address(
    party_id: UUID,
    address_id: UUID,
    body: PartyAddressUpdate,
    session: SessionData = Depends(require_vendor_access),
) -> PartyAddressUpdateResponse:
    """只更新有給的欄位；`is_primary=true` 會把同一家其他地址降級"""
    row = await party_service.update_address(
        party_id,
        address_id,
        body.model_dump(exclude_unset=True),
        actor_user_id=session.user_id,
        via="rest",
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在"
        )
    return PartyAddressUpdateResponse(**row)


@parties_router.delete("/{party_id}/addresses/{address_id}", summary="刪除地址")
async def delete_party_address(
    party_id: UUID,
    address_id: UUID,
    session: SessionData = Depends(require_vendor_access),
) -> dict:
    """刪除地址；刪掉主要那筆不自動指派新主要"""
    audit_id = await party_service.delete_address(
        party_id, address_id, actor_user_id=session.user_id, via="rest"
    )
    if audit_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在"
        )
    return {"success": True, "audit_id": str(audit_id)}


async def _party_detail(
    party_id: UUID, audit_id: UUID | None = None
) -> PartyDetailResponse:
    """明細；寫入端點會把剛寫下的 audit_id 一起帶回去（規格第三節）"""
    detail = await party_service.get_party_detail(party_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="往來對象不存在"
        )
    return PartyDetailResponse(**detail, audit_id=audit_id)


# ============================================================
# 物料
# ============================================================


@items_router.get("", response_model=ItemListResponse, summary="物料清單")
async def list_items(
    q: str | None = Query(None, description="料號／品名／規格／別名模糊搜尋"),
    item_group: str | None = Query(None, description="分類過濾"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: SessionData = Depends(require_inventory_access),
) -> ItemListResponse:
    """物料清單（含各倉合計數量）"""
    result = await inventory_service.list_items(
        q=q, item_group=item_group, page=page, page_size=page_size
    )
    return ItemListResponse(**result)


@items_router.post(
    "",
    response_model=ItemDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立物料",
)
async def create_item(
    body: ItemCreate,
    session: SessionData = Depends(require_inventory_access),
) -> ItemDetailResponse:
    """建立物料；料號重複回 400"""
    try:
        row = await inventory_service.create_item(
            body.model_dump(), actor_user_id=session.user_id, via="rest"
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    return await _item_detail(row["id"], audit_id=row["audit_id"])


@items_router.get("/{item_id}", response_model=ItemDetailResponse, summary="物料明細")
async def get_item(
    item_id: UUID,
    session: SessionData = Depends(require_inventory_access),
) -> ItemDetailResponse:
    """主檔＋各倉餘額＋最近異動＋預設供應商"""
    return await _item_detail(item_id)


@items_router.put("/{item_id}", response_model=ItemDetailResponse, summary="更新物料")
async def update_item(
    item_id: UUID,
    body: ItemUpdate,
    session: SessionData = Depends(require_inventory_access),
) -> ItemDetailResponse:
    """只更新有給的欄位"""
    try:
        row = await inventory_service.update_item(
            item_id,
            body.model_dump(exclude_unset=True),
            actor_user_id=session.user_id,
            via="rest",
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物料不存在")
    return await _item_detail(item_id, audit_id=row["audit_id"])


@items_router.delete("/{item_id}", summary="軟刪除物料")
async def delete_item(
    item_id: UUID,
    session: SessionData = Depends(require_inventory_access),
) -> dict:
    """軟刪除；庫存異動紀錄保留"""
    audit_id = await inventory_service.delete_item(
        item_id, actor_user_id=session.user_id, via="rest"
    )
    if audit_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物料不存在")
    return {"success": True, "audit_id": str(audit_id)}


async def _item_detail(
    item_id: UUID, audit_id: UUID | None = None
) -> ItemDetailResponse:
    """明細；寫入端點會把剛寫下的 audit_id 一起帶回去"""
    detail = await inventory_service.get_item_detail(item_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物料不存在")
    return ItemDetailResponse(**detail, audit_id=audit_id)


# ============================================================
# 倉庫
# ============================================================


@warehouses_router.get("", response_model=WarehouseListResponse, summary="倉庫清單")
async def list_warehouses(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: SessionData = Depends(require_inventory_access),
) -> WarehouseListResponse:
    """倉庫清單"""
    result = await inventory_service.list_warehouses(page=page, page_size=page_size)
    return WarehouseListResponse(**result)


@warehouses_router.post(
    "",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立倉庫",
)
async def create_warehouse(
    body: WarehouseCreate,
    session: SessionData = Depends(require_inventory_access),
) -> WarehouseResponse:
    """建立倉庫；代碼重複回 400"""
    try:
        row = await inventory_service.create_warehouse(
            body.model_dump(), actor_user_id=session.user_id, via="rest"
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    return WarehouseResponse(**_warehouse_payload(row))


@warehouses_router.put(
    "/{warehouse_id}", response_model=WarehouseResponse, summary="更新倉庫"
)
async def update_warehouse(
    warehouse_id: UUID,
    body: WarehouseUpdate,
    session: SessionData = Depends(require_inventory_access),
) -> WarehouseResponse:
    """只更新有給的欄位"""
    try:
        row = await inventory_service.update_warehouse(
            warehouse_id,
            body.model_dump(exclude_unset=True),
            actor_user_id=session.user_id,
            via="rest",
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="倉庫不存在")
    return WarehouseResponse(**_warehouse_payload(row))


def _warehouse_payload(row: dict) -> dict:
    """service 回的 dict 只挑 WarehouseResponse 要的欄位（含 audit_id）"""
    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "created_by": row.get("created_by"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "audit_id": row.get("audit_id"),
    }


@warehouses_router.delete("/{warehouse_id}", summary="軟刪除倉庫")
async def delete_warehouse(
    warehouse_id: UUID,
    session: SessionData = Depends(require_inventory_access),
) -> dict:
    """軟刪除；還有餘額的倉庫回 400"""
    try:
        audit_id = await inventory_service.delete_warehouse(
            warehouse_id, actor_user_id=session.user_id, via="rest"
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    if audit_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="倉庫不存在")
    return {"success": True, "audit_id": str(audit_id)}


# ============================================================
# 庫存
# ============================================================


@stock_router.get("", response_model=StockListResponse, summary="庫存查詢")
async def get_stock(
    item_id: UUID | None = Query(None),
    warehouse_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: SessionData = Depends(require_inventory_access),
) -> StockListResponse:
    """庫存餘額（item × warehouse 一列）"""
    result = await inventory_service.get_stock(
        item_id=item_id, warehouse_id=warehouse_id, page=page, page_size=page_size
    )
    return StockListResponse(**result)


@stock_router.post("/adjust", summary="調整庫存")
async def adjust_stock(
    body: StockAdjustRequest,
    session: SessionData = Depends(require_inventory_access),
) -> dict:
    """調整庫存（qty_delta 可正可負）；異動後餘額為負回 400"""
    try:
        result = await inventory_service.adjust_stock(
            body.item_id,
            body.warehouse_id,
            body.qty_delta,
            reason=body.reason,
            note=body.note,
            actor_user_id=session.user_id,
            via="rest",
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    return {
        "success": True,
        "audit_id": str(result["audit_id"]),
        "qty_after": str(result["balances"][0]["qty"]),
    }


@stock_router.post("/transfer", summary="倉別調撥")
async def transfer_stock(
    body: StockTransferRequest,
    session: SessionData = Depends(require_inventory_access),
) -> dict:
    """同一交易寫 transfer_out 與 transfer_in"""
    try:
        result = await inventory_service.transfer_stock(
            body.item_id,
            body.from_warehouse_id,
            body.to_warehouse_id,
            body.qty,
            note=body.note,
            actor_user_id=session.user_id,
            via="rest",
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    return {
        "success": True,
        "audit_id": str(result["audit_id"]),
        "balances": [
            {"warehouse_id": str(b["warehouse_id"]), "qty": str(b["qty"])}
            for b in result["balances"]
        ],
    }


# ============================================================
# 採購單
# ============================================================


@po_router.get("", response_model=PurchaseOrderListResponse, summary="採購單清單")
async def list_purchase_orders(
    supplier_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    project_id: UUID | None = Query(None),
    since: date | None = Query(None, description="訂購日起始（YYYY-MM-DD）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: SessionData = Depends(require_inventory_access),
) -> PurchaseOrderListResponse:
    """採購單清單（可依供應商、狀態、專案、起始日期篩選）"""
    result = await purchasing_service.list_purchase_orders(
        supplier_id=supplier_id,
        status=status_filter,
        project_id=project_id,
        since=since,
        page=page,
        page_size=page_size,
    )
    return PurchaseOrderListResponse(**result)


@po_router.post(
    "",
    response_model=PurchaseOrderDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立採購單",
)
async def create_purchase_order(
    body: PurchaseOrderCreate,
    session: SessionData = Depends(require_inventory_access),
) -> PurchaseOrderDetailResponse:
    """建立採購單（單號同交易產生）"""
    try:
        row = await purchasing_service.create_purchase_order(
            body.model_dump(), actor_user_id=session.user_id, via="rest"
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    return await _po_detail(row["id"], audit_id=row["audit_id"])


@po_router.get(
    "/{po_id}", response_model=PurchaseOrderDetailResponse, summary="採購單明細"
)
async def get_purchase_order(
    po_id: UUID,
    session: SessionData = Depends(require_inventory_access),
) -> PurchaseOrderDetailResponse:
    """採購單明細（含行項與金額）"""
    return await _po_detail(po_id)


@po_router.put(
    "/{po_id}", response_model=PurchaseOrderDetailResponse, summary="更新採購單"
)
async def update_purchase_order(
    po_id: UUID,
    body: PurchaseOrderUpdate,
    session: SessionData = Depends(require_inventory_access),
) -> PurchaseOrderDetailResponse:
    """更新單頭；已收貨或已取消的單回 400"""
    try:
        row = await purchasing_service.update_purchase_order(
            po_id,
            body.model_dump(exclude_unset=True),
            actor_user_id=session.user_id,
            via="rest",
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="採購單不存在"
        )
    return await _po_detail(po_id, audit_id=row["audit_id"])


@po_router.post("/{po_id}/receive", summary="採購收貨")
async def receive_purchase_order(
    po_id: UUID,
    body: PurchaseOrderReceiveRequest,
    session: SessionData = Depends(require_inventory_access),
) -> dict:
    """收貨入庫：更新已收量、寫庫存異動、更新單頭狀態"""
    try:
        result = await purchasing_service.receive_purchase_order(
            po_id,
            lines=[line.model_dump() for line in body.lines],
            receive_all=body.all,
            warehouse_id=body.warehouse_id,
            note=body.note,
            actor_user_id=session.user_id,
            via="rest",
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="採購單不存在"
        )
    return {
        "success": True,
        "status": result["status"],
        "audit_id": str(result["audit_id"]),
    }


@po_router.post("/{po_id}/cancel", summary="取消採購單")
async def cancel_purchase_order(
    po_id: UUID,
    body: PurchaseOrderCancelRequest,
    session: SessionData = Depends(require_inventory_access),
) -> dict:
    """取消（不是刪除）；已收過貨的回 400"""
    try:
        row = await purchasing_service.cancel_purchase_order(
            po_id, reason=body.reason, actor_user_id=session.user_id, via="rest"
        )
    except _ERP_ERRORS as e:
        raise _http_error(e)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="採購單不存在"
        )
    return {
        "success": True,
        "status": row["status"],
        "audit_id": str(row["audit_id"]),
    }


async def _po_detail(
    po_id: UUID, audit_id: UUID | None = None
) -> PurchaseOrderDetailResponse:
    """明細；寫入端點會把剛寫下的 audit_id 一起帶回去"""
    detail = await purchasing_service.get_purchase_order(po_id=po_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="採購單不存在"
        )
    return PurchaseOrderDetailResponse(**detail, audit_id=audit_id)


# 五個子 router 合成模組唯一的 router（modules.py 只註冊一個）
router.include_router(parties_router)
router.include_router(items_router)
router.include_router(warehouses_router)
router.include_router(stock_router)
router.include_router(po_router)
