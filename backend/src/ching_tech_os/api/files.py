"""統一檔案存取 API

提供統一的檔案存取介面，支援四種儲存區域：
- ctos://    → CTOS 系統檔案 (/mnt/nas/ctos/)
- shared://  → 公司專案共用區 (/mnt/nas/projects/)
- temp://    → 暫存檔案 (/tmp/ctos/)
- local://   → 本機小檔案 (應用程式 data 目錄)

API 格式：
- GET  /api/files/{zone}/{path:path}          - 讀取/預覽檔案
- GET  /api/files/{zone}/{path:path}/download - 下載檔案
"""

import mimetypes
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from ..models.auth import ErrorResponse, SessionData
from ..services.path_manager import path_manager, StorageZone
from .auth import get_session_from_token_or_query

router = APIRouter(prefix="/api/files", tags=["files"])


def _get_mime_type(filename: str) -> str:
    """根據檔名取得 MIME 類型"""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def _validate_zone(zone: str) -> StorageZone:
    """驗證並轉換 zone 字串為 StorageZone enum"""
    try:
        return StorageZone(zone)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"無效的儲存區域: {zone}，支援的區域: ctos, shared, temp, local",
        )


def _check_path_traversal(path: str) -> None:
    """防止路徑穿越攻擊"""
    if ".." in path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無效的路徑",
        )


def _get_file_path(zone: StorageZone, path: str) -> Path:
    """根據 zone 和 path 取得實際檔案路徑"""
    uri = f"{zone.value}://{path}"
    fs_path = path_manager.to_filesystem(uri)
    return Path(fs_path)


@router.get(
    "/{zone}/{path:path}",
    responses={
        200: {"description": "檔案內容"},
        400: {"model": ErrorResponse, "description": "無效的請求"},
        401: {"model": ErrorResponse, "description": "未授權"},
        403: {"model": ErrorResponse, "description": "無權限存取"},
        404: {"model": ErrorResponse, "description": "檔案不存在"},
    },
)
async def read_file(
    zone: str,
    path: str,
    session: SessionData = Depends(get_session_from_token_or_query),
) -> Response:
    """讀取檔案內容（inline 顯示）

    支援 Authorization header 或 query parameter token 認證。
    Query parameter 用於 <img src> 等無法設定 header 的情況。

    Args:
        zone: 儲存區域 (ctos, shared, temp, local)
        path: 檔案相對路徑

    Returns:
        檔案內容，使用適當的 MIME type
    """
    # 驗證參數
    storage_zone = _validate_zone(zone)
    _check_path_traversal(path)

    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定檔案路徑",
        )

    # 取得實際檔案路徑
    file_path = _get_file_path(storage_zone, path)

    # 檢查檔案是否存在
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="檔案不存在",
        )

    # 檢查是否為檔案（非目錄）
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="指定的路徑不是檔案",
        )

    # 讀取檔案
    try:
        content = file_path.read_bytes()
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限讀取此檔案",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"讀取檔案失敗: {e}",
        )

    # 取得 MIME type
    mime_type = _get_mime_type(file_path.name)

    return Response(content=content, media_type=mime_type)


@router.get(
    "/{zone}/{path:path}/download",
    responses={
        200: {"description": "檔案下載"},
        400: {"model": ErrorResponse, "description": "無效的請求"},
        401: {"model": ErrorResponse, "description": "未授權"},
        403: {"model": ErrorResponse, "description": "無權限存取"},
        404: {"model": ErrorResponse, "description": "檔案不存在"},
    },
)
async def download_file(
    zone: str,
    path: str,
    session: SessionData = Depends(get_session_from_token_or_query),
) -> Response:
    """下載檔案

    Args:
        zone: 儲存區域 (ctos, shared, temp, local)
        path: 檔案相對路徑

    Returns:
        檔案內容，附帶 Content-Disposition header
    """
    # 驗證參數
    storage_zone = _validate_zone(zone)
    _check_path_traversal(path)

    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定檔案路徑",
        )

    # 取得實際檔案路徑
    file_path = _get_file_path(storage_zone, path)

    # 檢查檔案是否存在
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="檔案不存在",
        )

    # 檢查是否為檔案（非目錄）
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="指定的路徑不是檔案",
        )

    # 讀取檔案
    try:
        content = file_path.read_bytes()
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限讀取此檔案",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"讀取檔案失敗: {e}",
        )

    # 取得 MIME type 和檔名
    filename = file_path.name
    mime_type = _get_mime_type(filename)

    # 處理檔名編碼（支援中文）
    encoded_filename = quote(filename)

    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )
