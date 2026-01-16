"""物料管理 API"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ching_tech_os.models.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryItemListResponse,
    InventoryTransactionCreate,
    InventoryTransactionResponse,
    InventoryTransactionListResponse,
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
    # 統計
    get_categories,
    get_low_stock_count,
    # 例外
    InventoryError,
    InventoryItemNotFoundError,
    InventoryTransactionNotFoundError,
)

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
) -> InventoryItemListResponse:
    """列出物料"""
    try:
        return await list_inventory_items(query=q, category=category, low_stock=low_stock)
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/items/{item_id}",
    response_model=InventoryItemResponse,
    summary="取得物料詳情",
)
async def api_get_inventory_item(item_id: UUID) -> InventoryItemResponse:
    """取得物料詳情"""
    try:
        return await get_inventory_item(item_id)
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
async def api_create_inventory_item(data: InventoryItemCreate) -> InventoryItemResponse:
    """建立物料"""
    try:
        return await create_inventory_item(data)
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
) -> InventoryItemResponse:
    """更新物料"""
    try:
        return await update_inventory_item(item_id, data)
    except InventoryItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除物料",
)
async def api_delete_inventory_item(item_id: UUID) -> None:
    """刪除物料"""
    try:
        await delete_inventory_item(item_id)
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
) -> InventoryTransactionListResponse:
    """列出物料的進出貨記錄"""
    try:
        return await list_inventory_transactions(item_id, limit=limit)
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
) -> InventoryTransactionResponse:
    """建立進出貨記錄"""
    try:
        return await create_inventory_transaction(item_id, data)
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
) -> InventoryTransactionResponse:
    """取得進出貨記錄詳情"""
    try:
        return await get_inventory_transaction(transaction_id)
    except InventoryTransactionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除進出貨記錄",
)
async def api_delete_inventory_transaction(transaction_id: UUID) -> None:
    """刪除進出貨記錄"""
    try:
        await delete_inventory_transaction(transaction_id)
    except InventoryTransactionNotFoundError as e:
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
async def api_get_categories() -> list[str]:
    """取得所有類別"""
    return await get_categories()


@router.get(
    "/stats/low-stock-count",
    response_model=int,
    summary="取得庫存不足數量",
)
async def api_get_low_stock_count() -> int:
    """取得庫存不足的物料數量"""
    return await get_low_stock_count()
