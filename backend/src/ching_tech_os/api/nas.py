"""NAS 操作 API"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.auth import ErrorResponse, SessionData
from ..models.nas import SharesResponse, BrowseResponse, ShareInfo, FileItem
from ..services.smb import create_smb_service, SMBError, SMBConnectionError
from .auth import get_current_session

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
