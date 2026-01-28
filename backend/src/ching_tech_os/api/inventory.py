"""物料管理 API"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ching_tech_os.models.auth import SessionData
from ching_tech_os.models.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryItemListResponse,
    InventoryTransactionCreate,
    InventoryTransactionResponse,
    InventoryTransactionListResponse,
    InventoryOrderCreate,
    InventoryOrderUpdate,
    InventoryOrderResponse,
    InventoryOrderListResponse,
)
from ching_tech_os.services.inventory import (
    # 物料
    list_inventory_items,
    get_inventory_item,
    create_inventory_item,
    update_inventory_item,
    delete_inventory_item,
    # 進出貨
    list_inventory_transactions,
    get_inventory_transaction,
    create_inventory_transaction,
    delete_inventory_transaction,
    # 訂購記錄
    list_inventory_orders,
    get_inventory_order,
    create_inventory_order,
    update_inventory_order,
    delete_inventory_order,
    # 統計
    get_categories,
    get_low_stock_count,
    # 例外
    InventoryError,
    InventoryItemNotFoundError,
    InventoryTransactionNotFoundError,
    InventoryOrderNotFoundError,
)
from .auth import get_current_session
from ..services.permissions import require_app_permission

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


# ============================================
# 物料主檔 CRUD
# ============================================


@router.get(
    "/items",
    response_model=InventoryItemListResponse,
    summary="列出物料",
)
async def api_list_inventory_items(
    q: str | None = Query(None, description="關鍵字搜尋（名稱、規格）"),
    category: str | None = Query(None, description="類別過濾"),
    low_stock: bool = Query(False, description="只顯示庫存不足的物料"),
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> InventoryItemListResponse:
    """列出物料"""
    try:
        return await list_inventory_items(
            query=q,
            category=category,
            low_stock=low_stock,
            tenant_id=session.tenant_id,
        )
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/items/{item_id}",
    response_model=InventoryItemResponse,
    summary="取得物料詳情",
)
async def api_get_inventory_item(
    item_id: UUID,
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> InventoryItemResponse:
    """取得物料詳情"""
    try:
        return await get_inventory_item(item_id, tenant_id=session.tenant_id)
    except InventoryItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/items",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立物料",
)
async def api_create_inventory_item(
    data: InventoryItemCreate,
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> InventoryItemResponse:
    """建立物料"""
    try:
        return await create_inventory_item(
            data,
            created_by=session.username,
            tenant_id=session.tenant_id,
        )
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/items/{item_id}",
    response_model=InventoryItemResponse,
    summary="更新物料",
)
async def api_update_inventory_item(
    item_id: UUID,
    data: InventoryItemUpdate,
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> InventoryItemResponse:
    """更新物料"""
    try:
        return await update_inventory_item(item_id, data, tenant_id=session.tenant_id)
    except InventoryItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除物料",
)
async def api_delete_inventory_item(
    item_id: UUID,
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> None:
    """刪除物料"""
    try:
        await delete_inventory_item(item_id, tenant_id=session.tenant_id)
    except InventoryItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================
# 進出貨記錄 CRUD
# ============================================


@router.get(
    "/items/{item_id}/transactions",
    response_model=InventoryTransactionListResponse,
    summary="列出進出貨記錄",
)
async def api_list_inventory_transactions(
    item_id: UUID,
    limit: int = Query(50, ge=1, le=200, description="最大筆數"),
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> InventoryTransactionListResponse:
    """列出物料的進出貨記錄"""
    try:
        return await list_inventory_transactions(
            item_id,
            limit=limit,
            tenant_id=session.tenant_id,
        )
    except InventoryItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/items/{item_id}/transactions",
    response_model=InventoryTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立進出貨記錄",
)
async def api_create_inventory_transaction(
    item_id: UUID,
    data: InventoryTransactionCreate,
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> InventoryTransactionResponse:
    """建立進出貨記錄"""
    try:
        return await create_inventory_transaction(
            item_id,
            data,
            created_by=session.username,
            tenant_id=session.tenant_id,
        )
    except InventoryItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/transactions/{transaction_id}",
    response_model=InventoryTransactionResponse,
    summary="取得進出貨記錄詳情",
)
async def api_get_inventory_transaction(
    transaction_id: UUID,
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> InventoryTransactionResponse:
    """取得進出貨記錄詳情"""
    try:
        return await get_inventory_transaction(
            transaction_id,
            tenant_id=session.tenant_id,
        )
    except InventoryTransactionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除進出貨記錄",
)
async def api_delete_inventory_transaction(
    transaction_id: UUID,
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> None:
    """刪除進出貨記錄"""
    try:
        await delete_inventory_transaction(
            transaction_id,
            tenant_id=session.tenant_id,
        )
    except InventoryTransactionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================
# 訂購記錄 CRUD
# ============================================


@router.get(
    "/items/{item_id}/orders",
    response_model=InventoryOrderListResponse,
    summary="列出物料訂購記錄",
)
async def api_list_inventory_orders(
    item_id: UUID,
    status: str | None = Query(None, description="狀態過濾（pending/ordered/delivered/cancelled）"),
    limit: int = Query(50, ge=1, le=200, description="最大筆數"),
) -> InventoryOrderListResponse:
    """列出物料的訂購記錄"""
    try:
        return await list_inventory_orders(item_id=item_id, status=status, limit=limit)
    except InventoryItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/items/{item_id}/orders",
    response_model=InventoryOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立訂購記錄",
)
async def api_create_inventory_order(
    item_id: UUID,
    data: InventoryOrderCreate,
) -> InventoryOrderResponse:
    """建立訂購記錄"""
    try:
        return await create_inventory_order(item_id, data)
    except InventoryItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/orders/{order_id}",
    response_model=InventoryOrderResponse,
    summary="取得訂購記錄詳情",
)
async def api_get_inventory_order(order_id: UUID) -> InventoryOrderResponse:
    """取得訂購記錄詳情"""
    try:
        return await get_inventory_order(order_id)
    except InventoryOrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/orders/{order_id}",
    response_model=InventoryOrderResponse,
    summary="更新訂購記錄",
)
async def api_update_inventory_order(
    order_id: UUID,
    data: InventoryOrderUpdate,
) -> InventoryOrderResponse:
    """更新訂購記錄"""
    try:
        return await update_inventory_order(order_id, data)
    except InventoryOrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/orders/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除訂購記錄",
)
async def api_delete_inventory_order(order_id: UUID) -> None:
    """刪除訂購記錄"""
    try:
        await delete_inventory_order(order_id)
    except InventoryOrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================
# 統計
# ============================================


@router.get(
    "/categories",
    response_model=list[str],
    summary="取得所有類別",
)
async def api_get_categories(
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> list[str]:
    """取得所有類別"""
    return await get_categories(tenant_id=session.tenant_id)


@router.get(
    "/stats/low-stock-count",
    response_model=int,
    summary="取得庫存不足數量",
)
async def api_get_low_stock_count(
    session: SessionData = Depends(require_app_permission("inventory-management")),
) -> int:
    """取得庫存不足的物料數量"""
    return await get_low_stock_count(tenant_id=session.tenant_id)
