"""廠商管理 API"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ching_tech_os.models.auth import SessionData
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
from .auth import get_current_session
from ..services.permissions import require_app_permission

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
    session: SessionData = Depends(require_app_permission("vendor-management")),
) -> VendorListResponse:
    """列出廠商"""
    try:
        return await list_vendors(
            query=q,
            active_only=active,
            limit=limit,
            tenant_id=session.tenant_id,
        )
    except VendorError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/{vendor_id}",
    response_model=VendorResponse,
    summary="取得廠商詳情",
)
async def api_get_vendor(
    vendor_id: UUID,
    session: SessionData = Depends(require_app_permission("vendor-management")),
) -> VendorResponse:
    """取得廠商詳情"""
    try:
        return await get_vendor(vendor_id, tenant_id=session.tenant_id)
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
async def api_create_vendor(
    data: VendorCreate,
    session: SessionData = Depends(require_app_permission("vendor-management")),
) -> VendorResponse:
    """新增廠商"""
    try:
        return await create_vendor(
            data,
            created_by=session.username,
            tenant_id=session.tenant_id,
        )
    except VendorDuplicateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except VendorError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put(
    "/{vendor_id}",
    response_model=VendorResponse,
    summary="更新廠商",
)
async def api_update_vendor(
    vendor_id: UUID,
    data: VendorUpdate,
    session: SessionData = Depends(require_app_permission("vendor-management")),
) -> VendorResponse:
    """更新廠商"""
    try:
        return await update_vendor(vendor_id, data, tenant_id=session.tenant_id)
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
async def api_deactivate_vendor(
    vendor_id: UUID,
    session: SessionData = Depends(require_app_permission("vendor-management")),
) -> VendorResponse:
    """停用廠商（軟刪除）"""
    try:
        return await deactivate_vendor(vendor_id, tenant_id=session.tenant_id)
    except VendorNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except VendorError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/{vendor_id}/activate",
    response_model=VendorResponse,
    summary="啟用廠商",
)
async def api_activate_vendor(
    vendor_id: UUID,
    session: SessionData = Depends(require_app_permission("vendor-management")),
) -> VendorResponse:
    """啟用廠商"""
    try:
        return await activate_vendor(vendor_id, tenant_id=session.tenant_id)
    except VendorNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except VendorError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
