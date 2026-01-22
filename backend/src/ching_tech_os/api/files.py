"""統一檔案存取 API

提供統一的檔案存取介面，支援五種儲存區域：
- ctos://    → CTOS 系統檔案 (/mnt/nas/ctos/)
- shared://  → 公司專案共用區 (/mnt/nas/projects/)
- temp://    → 暫存檔案 (/tmp/ctos/)
- local://   → 本機小檔案 (應用程式 data 目錄)
- nas://     → NAS 共享（透過 SMB 存取，用於檔案管理器）

API 格式：
- GET  /api/files/{zone}/{path:path}          - 讀取/預覽檔案
- GET  /api/files/{zone}/{path:path}/download - 下載檔案
"""

import mimetypes
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import Response

from ..models.auth import ErrorResponse, SessionData
from ..services.path_manager import path_manager, StorageZone
from ..services.smb import (
    create_smb_service,
    SMBError,
    SMBConnectionError,
    SMBFileNotFoundError,
    SMBPermissionError,
    SMBService,
)
from ..services.nas_connection import nas_connection_manager
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
            detail=f"無效的儲存區域: {zone}，支援的區域: ctos, shared, temp, local, nas",
        )


def _check_path_traversal(path: str) -> None:
    """防止路徑穿越攻擊"""
    if ".." in path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無效的路徑",
        )


def _get_file_path(
    zone: StorageZone, path: str, tenant_id: str | None = None
) -> Path:
    """根據 zone 和 path 取得實際檔案路徑（不支援 NAS zone）

    Args:
        zone: 儲存區域
        path: 相對路徑
        tenant_id: 租戶 ID（用於 CTOS zone 的租戶隔離）

    Returns:
        實際檔案路徑
    """
    if zone == StorageZone.NAS:
        raise ValueError("NAS zone 不支援本地檔案路徑，請使用 _read_nas_file()")
    uri = f"{zone.value}://{path}"
    fs_path = path_manager.to_filesystem(uri, tenant_id)
    return Path(fs_path)


def _get_nas_smb_service(
    nas_token: str | None,
    session: SessionData,
) -> tuple[SMBService, str]:
    """取得 NAS SMB 連線服務

    優先使用 NAS Token，若無則 fallback 使用 session 中的認證資訊。

    Args:
        nas_token: NAS 連線 token（可選）
        session: 使用者 session

    Returns:
        (SMBService, host) tuple

    Raises:
        HTTPException: 無有效連線
    """
    # 優先使用 NAS Token
    if nas_token:
        conn = nas_connection_manager.get_connection(nas_token)
        if conn is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="NAS 連線已過期，請重新連線",
                headers={"X-NAS-Token-Expired": "true"},
            )
        return conn.get_smb_service(), conn.host

    # Fallback: 使用 Session 密碼
    if session.password:
        return create_smb_service(
            username=session.username,
            password=session.password,
            host=session.nas_host,
        ), session.nas_host

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="需要 NAS 連線，請先連線至 NAS",
    )


def _read_nas_file(
    path: str,
    session: SessionData,
    nas_token: str | None = None,
) -> bytes:
    """透過 SMB 讀取 NAS 檔案

    Args:
        path: NAS 相對路徑，格式為 share_name/folder/file.txt
        session: 使用者 session（包含 NAS 認證資訊）
        nas_token: NAS 連線 token（優先使用）

    Returns:
        檔案內容

    Raises:
        HTTPException: 檔案不存在、無權限、連線失敗等
    """
    # 解析路徑：share_name/folder/file.txt
    path = path.strip("/")
    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定檔案路徑",
        )

    parts = path.split("/", 1)
    share_name = parts[0]
    sub_path = parts[1] if len(parts) > 1 else ""

    if not sub_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定檔案路徑（不可只指定共享名稱）",
        )

    smb, _ = _get_nas_smb_service(nas_token, session)

    try:
        with smb:
            return smb.read_file(share_name, sub_path)
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )
    except SMBFileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="檔案不存在",
        )
    except SMBPermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限讀取此檔案",
        )
    except SMBError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


def _read_local_file(file_path: Path) -> bytes:
    """讀取本地檔案系統的檔案

    Args:
        file_path: 檔案路徑

    Returns:
        檔案內容

    Raises:
        HTTPException: 檔案不存在、無權限等
    """
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
        return file_path.read_bytes()
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


def _read_file_content(
    zone: str,
    path: str,
    session: SessionData,
    nas_token: str | None = None,
) -> tuple[bytes, str, str]:
    """讀取檔案內容（統一入口）

    Args:
        zone: 儲存區域字串
        path: 檔案相對路徑
        session: 使用者 session
        nas_token: NAS 連線 token（用於 NAS zone）

    Returns:
        (content, filename, mime_type) 元組

    Raises:
        HTTPException: 各種錯誤情況
    """
    # 驗證參數
    storage_zone = _validate_zone(zone)
    _check_path_traversal(path)

    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定檔案路徑",
        )

    # NAS zone：透過 SMB 讀取（不受租戶隔離影響）
    if storage_zone == StorageZone.NAS:
        content = _read_nas_file(path, session, nas_token)
        filename = path.split("/")[-1]
        mime_type = _get_mime_type(filename)
        return content, filename, mime_type

    # 取得租戶 ID（用於 CTOS zone 的租戶隔離）
    tenant_id = getattr(session, "tenant_id", None)

    # 其他 zone：透過本地檔案系統讀取
    file_path = _get_file_path(storage_zone, path, tenant_id)
    content = _read_local_file(file_path)
    filename = file_path.name
    mime_type = _get_mime_type(filename)
    return content, filename, mime_type


# 注意：/download 路由必須放在 /{path:path} 之前，
# 否則 path:path 會貪婪匹配到 /download
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
    x_nas_token: str | None = Header(None, alias="X-NAS-Token"),
    nas_token: str | None = None,  # Query parameter（用於無法設定 header 的情況）
    session: SessionData = Depends(get_session_from_token_or_query),
) -> Response:
    """下載檔案

    支援 X-NAS-Token header 或 nas_token query parameter 來指定 NAS 連線。

    Args:
        zone: 儲存區域 (ctos, shared, temp, local, nas)
        path: 檔案相對路徑

    Returns:
        檔案內容，附帶 Content-Disposition header
    """
    actual_nas_token = x_nas_token or nas_token
    content, filename, mime_type = _read_file_content(zone, path, session, actual_nas_token)
    encoded_filename = quote(filename)

    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


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
    x_nas_token: str | None = Header(None, alias="X-NAS-Token"),
    nas_token: str | None = None,  # Query parameter（用於 <img src> 等無法設定 header 的情況）
    session: SessionData = Depends(get_session_from_token_or_query),
) -> Response:
    """讀取檔案內容（inline 顯示）

    支援 Authorization header 或 query parameter token 認證。
    支援 X-NAS-Token header 或 nas_token query parameter 來指定 NAS 連線。

    Args:
        zone: 儲存區域 (ctos, shared, temp, local, nas)
        path: 檔案相對路徑

    Returns:
        檔案內容，使用適當的 MIME type
    """
    actual_nas_token = x_nas_token or nas_token
    content, _, mime_type = _read_file_content(zone, path, session, actual_nas_token)
    return Response(content=content, media_type=mime_type)
