"""廠商管理 API"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ching_tech_os.models.vendor import (
    VendorCreate,
    VendorUpdate,
    VendorResponse,
    VendorListResponse,
)
from ching_tech_os.services.vendor import (
    list_vendors,
    get_vendor,
    create_vendor,
    update_vendor,
    deactivate_vendor,
    activate_vendor,
    VendorError,
    VendorNotFoundError,
    VendorDuplicateError,
)

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


@router.get(
    "",
    response_model=VendorListResponse,
    summary="列出廠商",
)
async def api_list_vendors(
    q: str | None = Query(None, description="關鍵字搜尋（名稱、簡稱、ERP 編號）"),
    active: bool = Query(True, description="只顯示啟用的廠商"),
    limit: int = Query(100, description="最大回傳數量", ge=1, le=500),
) -> VendorListResponse:
    """列出廠商"""
    try:
        return await list_vendors(query=q, active_only=active, limit=limit)
    except VendorError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/{vendor_id}",
    response_model=VendorResponse,
    summary="取得廠商詳情",
)
async def api_get_vendor(vendor_id: UUID) -> VendorResponse:
    """取得廠商詳情"""
    try:
        return await get_vendor(vendor_id)
    except VendorNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except VendorError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "",
    response_model=VendorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增廠商",
)
async def api_create_vendor(data: VendorCreate) -> VendorResponse:
    """新增廠商"""
    try:
        return await create_vendor(data)
    except VendorDuplicateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except VendorError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put(
    "/{vendor_id}",
    response_model=VendorResponse,
    summary="更新廠商",
)
async def api_update_vendor(vendor_id: UUID, data: VendorUpdate) -> VendorResponse:
    """更新廠商"""
    try:
        return await update_vendor(vendor_id, data)
    except VendorNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except VendorDuplicateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except VendorError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete(
    "/{vendor_id}",
    response_model=VendorResponse,
    summary="停用廠商",
)
async def api_deactivate_vendor(vendor_id: UUID) -> VendorResponse:
    """停用廠商（軟刪除）"""
    try:
        return await deactivate_vendor(vendor_id)
    except VendorNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except VendorError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/{vendor_id}/activate",
    response_model=VendorResponse,
    summary="啟用廠商",
)
async def api_activate_vendor(vendor_id: UUID) -> VendorResponse:
    """啟用廠商"""
    try:
        return await activate_vendor(vendor_id)
    except VendorNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except VendorError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
