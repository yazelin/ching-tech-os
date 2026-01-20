"""租戶自助服務 API

供租戶管理員管理自己的租戶設定。
"""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import settings
from ..models.auth import SessionData
from ..models.tenant import (
    TenantInfo,
    TenantUpdate,
    TenantUsage,
    TenantAdminCreate,
    TenantAdminInfo,
    TenantSettings,
    TenantExportRequest,
    TenantExportResponse,
    TenantImportRequest,
)
from ..services.tenant import (
    get_tenant_by_id,
    update_tenant,
    get_tenant_usage,
    add_tenant_admin,
    remove_tenant_admin,
    list_tenant_admins,
    is_tenant_admin,
    TenantNotFoundError,
)
from ..services.tenant_data import (
    export_tenant_data,
    import_tenant_data,
    validate_tenant_data,
)
from .auth import get_current_session

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


# === 輔助函數 ===


async def require_tenant_admin(session: SessionData) -> SessionData:
    """要求租戶管理員權限

    Raises:
        HTTPException: 若不是租戶管理員
    """
    if session.role not in ("tenant_admin", "platform_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要租戶管理員權限",
        )
    return session


# === 租戶資訊 API ===


@router.get("/info", response_model=TenantInfo)
async def get_tenant_info(
    session: SessionData = Depends(get_current_session),
) -> TenantInfo:
    """取得目前租戶資訊

    任何登入使用者都可以查看自己租戶的基本資訊。
    """
    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    tenant = await get_tenant_by_id(session.tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )

    # 將資料轉換為 TenantInfo
    import json
    settings_data = tenant["settings"]
    if isinstance(settings_data, str):
        settings_data = json.loads(settings_data)
    elif settings_data is None:
        settings_data = {}

    return TenantInfo(
        id=tenant["id"],
        code=tenant["code"],
        name=tenant["name"],
        status=tenant["status"],
        plan=tenant["plan"],
        storage_quota_mb=tenant["storage_quota_mb"],
        storage_used_mb=tenant["storage_used_mb"] or 0,
        settings=TenantSettings(**settings_data),
        trial_ends_at=tenant["trial_ends_at"],
        created_at=tenant["created_at"],
        updated_at=tenant["updated_at"],
    )


@router.get("/usage", response_model=TenantUsage)
async def get_usage(
    session: SessionData = Depends(get_current_session),
) -> TenantUsage:
    """取得租戶使用量統計

    任何登入使用者都可以查看。
    """
    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    try:
        return await get_tenant_usage(session.tenant_id)
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )


# === 租戶設定 API（需要管理員權限）===


class UpdateTenantSettingsRequest(BaseModel):
    """更新租戶設定請求"""
    name: str | None = None
    settings: TenantSettings | None = None


@router.put("/settings", response_model=TenantInfo)
async def update_tenant_settings(
    request: UpdateTenantSettingsRequest,
    session: SessionData = Depends(get_current_session),
) -> TenantInfo:
    """更新租戶設定

    僅租戶管理員可操作。只能修改名稱和設定，不能修改 plan、status 等。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    try:
        # 只允許修改名稱和設定
        update_data = TenantUpdate(
            name=request.name,
            settings=request.settings,
        )
        return await update_tenant(session.tenant_id, update_data)
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租戶不存在",
        )


# === 租戶管理員 API ===


@router.get("/admins", response_model=list[TenantAdminInfo])
async def get_admins(
    session: SessionData = Depends(get_current_session),
) -> list[TenantAdminInfo]:
    """列出租戶管理員

    僅租戶管理員可查看。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    return await list_tenant_admins(session.tenant_id)


@router.post("/admins", response_model=TenantAdminInfo, status_code=status.HTTP_201_CREATED)
async def add_admin(
    request: TenantAdminCreate,
    session: SessionData = Depends(get_current_session),
) -> TenantAdminInfo:
    """新增租戶管理員

    僅租戶管理員可操作。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    try:
        return await add_tenant_admin(session.tenant_id, request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


class RemoveAdminResponse(BaseModel):
    """移除管理員回應"""
    success: bool
    message: str


@router.delete("/admins/{user_id}", response_model=RemoveAdminResponse)
async def remove_admin(
    user_id: int,
    session: SessionData = Depends(get_current_session),
) -> RemoveAdminResponse:
    """移除租戶管理員

    僅租戶管理員可操作。不能移除自己。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 不能移除自己
    if session.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除自己的管理員身份",
        )

    success = await remove_tenant_admin(session.tenant_id, user_id)
    if success:
        return RemoveAdminResponse(success=True, message="已移除管理員")
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理員不存在",
        )


# === 資料匯出/匯入 API ===


@router.post("/export")
async def export_data(
    request: TenantExportRequest,
    session: SessionData = Depends(get_current_session),
) -> StreamingResponse:
    """匯出租戶資料

    匯出租戶的所有資料（資料庫 + 檔案）為 ZIP 檔案。
    僅租戶管理員可操作。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    try:
        zip_content, summary = await export_tenant_data(
            session.tenant_id,
            include_files=request.include_files,
            include_ai_logs=request.include_ai_logs,
        )

        # 取得租戶資訊作為檔名
        tenant = await get_tenant_by_id(session.tenant_id)
        tenant_code = tenant["code"] if tenant else "tenant"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{tenant_code}_export_{timestamp}.zip"

        return StreamingResponse(
            iter([zip_content]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(zip_content)),
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"匯出失敗: {str(e)}",
        )


class ImportResponse(BaseModel):
    """匯入回應"""
    success: bool
    message: str
    summary: dict


@router.post("/import", response_model=ImportResponse)
async def import_data(
    file: UploadFile = File(...),
    merge_mode: str = "replace",
    session: SessionData = Depends(get_current_session),
) -> ImportResponse:
    """匯入租戶資料

    從 ZIP 檔案匯入租戶資料。
    僅租戶管理員可操作。

    Args:
        file: ZIP 檔案
        merge_mode: 合併模式（replace: 取代現有資料, merge: 合併）
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    # 驗證檔案類型
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請上傳 ZIP 檔案",
        )

    # 驗證合併模式
    if merge_mode not in ("replace", "merge"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="合併模式必須是 replace 或 merge",
        )

    try:
        # 讀取上傳的檔案內容
        zip_content = await file.read()

        # 執行匯入
        summary = await import_tenant_data(
            session.tenant_id,
            zip_content,
            merge_mode=merge_mode,
        )

        # 檢查是否有錯誤
        errors = summary.get("errors", [])
        if errors:
            return ImportResponse(
                success=True,
                message=f"匯入完成，但有 {len(errors)} 個錯誤",
                summary=summary,
            )

        return ImportResponse(
            success=True,
            message="匯入完成",
            summary=summary,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"匯入失敗: {str(e)}",
        )


class ValidateResponse(BaseModel):
    """驗證回應"""
    success: bool
    message: str
    result: dict


@router.get("/validate", response_model=ValidateResponse)
async def validate_data(
    session: SessionData = Depends(get_current_session),
) -> ValidateResponse:
    """驗證租戶資料完整性

    檢查租戶資料的完整性，包括資料庫記錄和檔案系統。
    僅租戶管理員可操作。
    """
    await require_tenant_admin(session)

    if session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未關聯租戶",
        )

    try:
        result = await validate_tenant_data(session.tenant_id)

        errors = result.get("errors", [])
        warnings = result.get("warnings", [])

        if errors:
            return ValidateResponse(
                success=False,
                message=f"驗證失敗: {len(errors)} 個錯誤",
                result=result,
            )
        elif warnings:
            return ValidateResponse(
                success=True,
                message=f"驗證通過，但有 {len(warnings)} 個警告",
                result=result,
            )
        else:
            return ValidateResponse(
                success=True,
                message="驗證通過",
                result=result,
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"驗證失敗: {str(e)}",
        )
