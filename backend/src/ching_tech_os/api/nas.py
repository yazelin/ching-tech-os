"""NAS 操作 API"""

import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from ..models.auth import ErrorResponse, SessionData
from ..services.message import log_message
from ..models.nas import (
    SharesResponse,
    BrowseResponse,
    ShareInfo,
    FileItem,
    FileContentResponse,
    DeleteRequest,
    RenameRequest,
    MkdirRequest,
    OperationResponse,
    SearchResponse,
    SearchItem,
)
from ..services.smb import create_smb_service, SMBError, SMBConnectionError
from .auth import get_current_session, get_session_from_token_or_query

router = APIRouter(prefix="/api/nas", tags=["nas"])


@router.get(
    "/shares",
    response_model=SharesResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未授權"},
        503: {"model": ErrorResponse, "description": "無法連線至檔案伺服器"},
    },
)
async def list_shares(
    session: SessionData = Depends(get_current_session),
) -> SharesResponse:
    """列出 NAS 上的共享資料夾"""
    smb = create_smb_service(
        username=session.username,
        password=session.password,
        host=session.nas_host,
    )

    try:
        with smb:
            shares = smb.list_shares()
            return SharesResponse(
                shares=[ShareInfo(name=s["name"], type=s["type"]) for s in shares]
            )
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )
    except SMBError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/browse",
    response_model=BrowseResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未授權"},
        403: {"model": ErrorResponse, "description": "無權限存取"},
        503: {"model": ErrorResponse, "description": "無法連線至檔案伺服器"},
    },
)
async def browse_directory(
    path: str = "/",
    session: SessionData = Depends(get_current_session),
) -> BrowseResponse:
    """瀏覽指定資料夾內容

    Args:
        path: 資料夾路徑，格式為 /share_name 或 /share_name/folder/subfolder
    """
    # 解析路徑
    path = path.strip("/")
    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定共享資料夾名稱",
        )

    parts = path.split("/", 1)
    share_name = parts[0]
    sub_path = parts[1] if len(parts) > 1 else ""

    smb = create_smb_service(
        username=session.username,
        password=session.password,
        host=session.nas_host,
    )

    try:
        with smb:
            items = smb.browse_directory(share_name, sub_path)
            return BrowseResponse(
                path=f"/{path}",
                items=[
                    FileItem(
                        name=item["name"],
                        type=item["type"],
                        size=item.get("size"),
                        modified=item.get("modified"),
                    )
                    for item in items
                ],
            )
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )
    except SMBError as e:
        error_msg = str(e)
        if "權限" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權限存取此資料夾",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


def _parse_path(path: str) -> tuple[str, str]:
    """解析路徑為 (share_name, sub_path)"""
    path = path.strip("/")
    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定檔案路徑",
        )
    parts = path.split("/", 1)
    share_name = parts[0]
    sub_path = parts[1] if len(parts) > 1 else ""
    return share_name, sub_path


def _get_mime_type(filename: str) -> str:
    """根據檔名取得 MIME 類型"""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


@router.get(
    "/file",
    responses={
        200: {"description": "檔案內容"},
        401: {"model": ErrorResponse, "description": "未授權"},
        403: {"model": ErrorResponse, "description": "無權限存取"},
        404: {"model": ErrorResponse, "description": "檔案不存在"},
    },
)
async def read_file(
    path: str,
    session: SessionData = Depends(get_session_from_token_or_query),
) -> Response:
    """讀取檔案內容

    支援 Authorization header 或 query parameter token 認證。
    Query parameter 用於 <img src> 等無法設定 header 的情況。

    Args:
        path: 檔案路徑，格式為 /share_name/folder/file.txt
        token: (可選) 認證 token，若未提供 Authorization header 則必須
    """
    share_name, sub_path = _parse_path(path)
    if not sub_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定檔案路徑",
        )

    smb = create_smb_service(
        username=session.username,
        password=session.password,
        host=session.nas_host,
    )

    try:
        with smb:
            content = smb.read_file(share_name, sub_path)
            mime_type = _get_mime_type(sub_path)
            return Response(content=content, media_type=mime_type)
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )
    except SMBError as e:
        error_msg = str(e)
        if "不存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="檔案不存在",
            )
        if "權限" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權限讀取此檔案",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/download",
    responses={
        200: {"description": "檔案下載"},
        401: {"model": ErrorResponse, "description": "未授權"},
        403: {"model": ErrorResponse, "description": "無權限存取"},
        404: {"model": ErrorResponse, "description": "檔案不存在"},
    },
)
async def download_file(
    path: str,
    session: SessionData = Depends(get_current_session),
) -> Response:
    """下載檔案

    Args:
        path: 檔案路徑，格式為 /share_name/folder/file.txt
    """
    share_name, sub_path = _parse_path(path)
    if not sub_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定檔案路徑",
        )

    # 取得檔名
    filename = sub_path.split("/")[-1]

    smb = create_smb_service(
        username=session.username,
        password=session.password,
        host=session.nas_host,
    )

    try:
        with smb:
            content = smb.read_file(share_name, sub_path)
            mime_type = _get_mime_type(filename)

            # 處理檔名編碼（支援中文）
            from urllib.parse import quote
            encoded_filename = quote(filename)

            return Response(
                content=content,
                media_type=mime_type,
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                },
            )
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )
    except SMBError as e:
        error_msg = str(e)
        if "不存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="檔案不存在",
            )
        if "權限" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權限下載此檔案",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/upload",
    response_model=OperationResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未授權"},
        403: {"model": ErrorResponse, "description": "無權限存取"},
    },
)
async def upload_file(
    path: Annotated[str, Form(description="目標資料夾路徑")],
    file: UploadFile = File(...),
    session: SessionData = Depends(get_current_session),
) -> OperationResponse:
    """上傳檔案

    Args:
        path: 目標資料夾路徑，格式為 /share_name/folder
        file: 上傳的檔案
    """
    share_name, sub_path = _parse_path(path)

    # 組合完整檔案路徑
    filename = file.filename or "unnamed"
    file_path = f"{sub_path}/{filename}" if sub_path else filename

    smb = create_smb_service(
        username=session.username,
        password=session.password,
        host=session.nas_host,
    )

    try:
        content = await file.read()
        with smb:
            smb.write_file(share_name, file_path, content)

            # 記錄上傳操作到訊息中心
            try:
                await log_message(
                    severity="info",
                    source="file-manager",
                    title="檔案上傳",
                    content=f"上傳檔案: {file_path}\n大小: {len(content)} bytes",
                    category="app",
                    user_id=session.user_id,
                    metadata={"path": f"/{share_name}/{file_path}", "size": len(content)}
                )
            except Exception as e:
                print(f"[nas] log_message error: {e}")

            return OperationResponse(success=True, message="上傳成功")
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )
    except SMBError as e:
        error_msg = str(e)
        if "權限" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權限上傳檔案",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/file",
    response_model=OperationResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未授權"},
        403: {"model": ErrorResponse, "description": "無權限存取"},
        404: {"model": ErrorResponse, "description": "檔案不存在"},
    },
)
async def delete_file(
    request: DeleteRequest,
    session: SessionData = Depends(get_current_session),
) -> OperationResponse:
    """刪除檔案或資料夾

    Args:
        request: 刪除請求，包含路徑和是否遞迴刪除
    """
    share_name, sub_path = _parse_path(request.path)
    if not sub_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無法刪除共享根目錄",
        )

    smb = create_smb_service(
        username=session.username,
        password=session.password,
        host=session.nas_host,
    )

    try:
        with smb:
            smb.delete_item(share_name, sub_path, recursive=request.recursive)

            # 記錄刪除操作到訊息中心
            try:
                await log_message(
                    severity="info",
                    source="file-manager",
                    title="檔案刪除",
                    content=f"刪除: {request.path}",
                    category="app",
                    user_id=session.user_id,
                    metadata={"path": request.path, "recursive": request.recursive}
                )
            except Exception as e:
                print(f"[nas] log_message error: {e}")

            return OperationResponse(success=True, message="刪除成功")
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )
    except SMBError as e:
        error_msg = str(e)
        if "不存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="檔案或資料夾不存在",
            )
        if "權限" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權限刪除此項目",
            )
        if "不是空的" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="資料夾不是空的，請使用遞迴刪除",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.patch(
    "/rename",
    response_model=OperationResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未授權"},
        403: {"model": ErrorResponse, "description": "無權限存取"},
        404: {"model": ErrorResponse, "description": "檔案不存在"},
        409: {"model": ErrorResponse, "description": "目標名稱已存在"},
    },
)
async def rename_item(
    request: RenameRequest,
    session: SessionData = Depends(get_current_session),
) -> OperationResponse:
    """重命名檔案或資料夾

    Args:
        request: 重命名請求，包含原始路徑和新名稱
    """
    share_name, sub_path = _parse_path(request.path)
    if not sub_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無法重命名共享根目錄",
        )

    smb = create_smb_service(
        username=session.username,
        password=session.password,
        host=session.nas_host,
    )

    try:
        with smb:
            smb.rename_item(share_name, sub_path, request.new_name)
            return OperationResponse(success=True, message="重命名成功")
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )
    except SMBError as e:
        error_msg = str(e)
        if "已存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="目標名稱已存在",
            )
        if "權限" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權限重命名此項目",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/mkdir",
    response_model=OperationResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未授權"},
        403: {"model": ErrorResponse, "description": "無權限存取"},
        409: {"model": ErrorResponse, "description": "資料夾已存在"},
    },
)
async def create_directory(
    request: MkdirRequest,
    session: SessionData = Depends(get_current_session),
) -> OperationResponse:
    """建立資料夾

    Args:
        request: 建立資料夾請求，包含路徑
    """
    share_name, sub_path = _parse_path(request.path)
    if not sub_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定資料夾名稱",
        )

    smb = create_smb_service(
        username=session.username,
        password=session.password,
        host=session.nas_host,
    )

    try:
        with smb:
            smb.create_directory(share_name, sub_path)
            return OperationResponse(success=True, message="建立成功")
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )
    except SMBError as e:
        error_msg = str(e)
        if "已存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="資料夾已存在",
            )
        if "權限" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權限建立資料夾",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/search",
    response_model=SearchResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未授權"},
        400: {"model": ErrorResponse, "description": "參數錯誤"},
        404: {"model": ErrorResponse, "description": "路徑不存在"},
    },
)
async def search_files(
    path: str,
    query: str,
    max_depth: int = 3,
    max_results: int = 100,
    session: SessionData = Depends(get_current_session),
) -> SearchResponse:
    """搜尋檔案和資料夾

    Args:
        path: 搜尋起始路徑（如 /home/documents）
        query: 搜尋關鍵字（支援萬用字元 * 和 ?）
        max_depth: 最大搜尋深度（預設 3 層，最大 10 層）
        max_results: 最大結果數量（預設 100，最大 500）
    """
    if not query or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請輸入搜尋關鍵字",
        )

    # 限制參數範圍
    max_depth = min(max(1, max_depth), 10)
    max_results = min(max(1, max_results), 500)

    share_name, sub_path = _parse_path(path)

    smb = create_smb_service(
        username=session.username,
        password=session.password,
        host=session.nas_host,
    )

    try:
        with smb:
            results = smb.search_files(
                share_name=share_name,
                path=sub_path or "",
                query=query.strip(),
                max_depth=max_depth,
                max_results=max_results,
            )
            return SearchResponse(
                query=query.strip(),
                path=path,
                results=[SearchItem(**r) for r in results],
                total=len(results),
            )
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )
    except SMBError as e:
        error_msg = str(e)
        if "不存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="搜尋路徑不存在",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
