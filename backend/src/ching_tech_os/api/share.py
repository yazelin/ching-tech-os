"""公開分享連結 API"""

import mimetypes
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from ching_tech_os.models.share import (
    ShareLinkCreate,
    ShareLinkResponse,
    ShareLinkListResponse,
    PublicResourceResponse,
)
from ching_tech_os.services.share import (
    create_share_link,
    list_my_links,
    list_all_links,
    revoke_link,
    get_public_resource,
    get_link_info,
    validate_nas_file_path,
    ShareError,
    ShareLinkNotFoundError,
    ShareLinkExpiredError,
    ResourceNotFoundError,
    NasFileNotFoundError,
    NasFileAccessDenied,
)
from ching_tech_os.config import settings
from ching_tech_os.services.knowledge import get_nas_attachment, KnowledgeError
from ching_tech_os.services.permissions import check_knowledge_permission
from ching_tech_os.services.user import get_user_preferences
from ching_tech_os.services.knowledge import get_knowledge, KnowledgeNotFoundError
from ching_tech_os.api.auth import get_current_session
from ching_tech_os.models.auth import SessionData

# 需登入的 API
router = APIRouter(prefix="/api/share", tags=["share"])

# 無需登入的公開 API
public_router = APIRouter(prefix="/api/public", tags=["public"])


def is_admin(username: str) -> bool:
    """檢查是否為管理員"""
    return username == settings.admin_username


@router.post(
    "",
    response_model=ShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立分享連結",
)
async def create_link(
    data: ShareLinkCreate,
    session: SessionData = Depends(get_current_session),
) -> ShareLinkResponse:
    """建立公開分享連結

    只有資源擁有者或有編輯權限的人可以建立連結。
    """
    # 權限檢查
    if data.resource_type == "knowledge":
        try:
            knowledge = get_knowledge(data.resource_id)
            preferences = await get_user_preferences(session.user_id) if session.user_id else None
            if not check_knowledge_permission(
                session.username, preferences, knowledge.owner, knowledge.scope, "write"
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="您沒有分享此知識的權限",
                )
        except KnowledgeNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"知識 {data.resource_id} 不存在",
            )

    elif data.resource_type == "nas_file":
        # 驗證 NAS 檔案存在且在允許範圍內
        try:
            validate_nas_file_path(data.resource_id)
        except NasFileNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        except NasFileAccessDenied as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e),
            )

    # 專案目前不做權限檢查，任何登入使用者都可以分享
    # 後續可以加入專案權限檢查

    try:
        return await create_share_link(data, session.username)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ShareError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "",
    response_model=ShareLinkListResponse,
    summary="列出分享連結",
)
async def list_links(
    view: str = "mine",
    session: SessionData = Depends(get_current_session),
) -> ShareLinkListResponse:
    """列出分享連結

    Args:
        view: "mine" 只顯示自己的，"all" 顯示全部（僅管理員）
    """
    try:
        user_is_admin = is_admin(session.username)

        # 管理員可以選擇查看全部
        if view == "all" and user_is_admin:
            result = await list_all_links()
        else:
            # 非管理員或選擇「我的」
            result = await list_my_links(session.username)

        # 設定管理員標誌（讓前端知道可以切換視圖）
        result.is_admin = user_is_admin
        return result
    except ShareError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="撤銷分享連結",
)
async def delete_link(
    token: str,
    session: SessionData = Depends(get_current_session),
) -> None:
    """撤銷分享連結

    連結建立者或管理員可以撤銷。
    """
    try:
        await revoke_link(token, session.username, is_admin(session.username))
    except ShareLinkNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="連結不存在",
        )
    except ShareError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# ============================================
# 公開 API（無需登入）
# ============================================


@public_router.get(
    "/{token}",
    response_model=PublicResourceResponse,
    summary="取得公開資源",
)
async def get_resource(token: str) -> PublicResourceResponse:
    """取得公開分享的資源內容

    無需登入即可存取。
    """
    try:
        return await get_public_resource(token)
    except ShareLinkNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="連結不存在或已被撤銷",
        )
    except ShareLinkExpiredError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="此連結已過期",
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原始內容已被刪除",
        )
    except ShareError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@public_router.get(
    "/{token}/attachments/{path:path}",
    summary="取得公開資源的附件",
)
async def get_public_attachment(token: str, path: str) -> Response:
    """取得公開資源的附件

    僅限知識庫附件，無需登入。
    path 格式可能是：
    - nas://knowledge/attachments/{kb_id}/{filename} (NAS 附件)
    - attachments/{kb_id}/{filename} (NAS 附件)
    - local/images/{kb_id}-{filename} (本機附件，正規化後的格式)
    """
    from pathlib import Path as FilePath

    try:
        # 驗證 token 有效
        link_info = await get_link_info(token)

        # 只支援知識庫附件
        if link_info["resource_type"] != "knowledge":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="此資源類型不支援附件",
            )

        kb_id = link_info["resource_id"]
        filename = path.split("/")[-1]

        # 判斷是本機附件還是 NAS 附件
        # local/ 開頭是正規化後的本機附件路徑
        is_local_asset = path.startswith("local/")

        if is_local_asset:
            # 本機附件：驗證檔名包含 kb_id
            if not filename.startswith(f"{kb_id}-"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="無權存取此附件",
                )

            # 安全檢查：防止路徑穿越
            if ".." in path:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="無效的路徑",
                )

            # 將 local/ 轉換為 assets/
            assets_path = "assets/" + path[len("local/"):]

            # 讀取本機檔案
            assets_base = FilePath("/home/ct/SDD/ching-tech-os/data/knowledge")
            file_path = assets_base / assets_path

            if not file_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="附件不存在",
                )

            content = file_path.read_bytes()
        else:
            # NAS 附件
            # 移除 nas://knowledge/ 前綴（如果有的話）
            nas_prefix = "nas://knowledge/"
            if path.startswith(nas_prefix):
                path = path[len(nas_prefix):]

            # 驗證附件路徑是否屬於該知識庫
            if not path.startswith(f"attachments/{kb_id}/"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="無權存取此附件",
                )

            # get_nas_attachment 期望的 path 不含 attachments/ 前綴
            nas_path = path[len("attachments/"):]
            content = get_nas_attachment(nas_path)

        mime_type, _ = mimetypes.guess_type(filename)
        return Response(
            content=content,
            media_type=mime_type or "application/octet-stream",
        )

    except ShareLinkNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="連結不存在",
        )
    except ShareLinkExpiredError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="此連結已過期",
        )
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@public_router.get(
    "/{token}/download",
    summary="下載 NAS 檔案",
)
async def download_nas_file(token: str) -> Response:
    """透過分享連結下載 NAS 檔案

    僅限 nas_file 類型的分享連結，無需登入。
    """
    from urllib.parse import quote

    try:
        # 驗證 token 有效
        link_info = await get_link_info(token)

        # 只支援 NAS 檔案
        if link_info["resource_type"] != "nas_file":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="此連結不是檔案下載連結",
            )

        file_path = link_info["resource_id"]

        # 驗證並取得檔案路徑
        full_path = validate_nas_file_path(file_path)

        # 讀取檔案內容
        content = full_path.read_bytes()
        filename = full_path.name

        # 取得 MIME 類型
        mime_type, _ = mimetypes.guess_type(filename)

        # 處理檔名編碼（支援中文）
        encoded_filename = quote(filename)

        # 圖片用 inline（讓 Line PC 能顯示），其他用 attachment
        is_image = mime_type and mime_type.startswith("image/")
        disposition = "inline" if is_image else "attachment"

        return Response(
            content=content,
            media_type=mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{encoded_filename}",
            },
        )

    except ShareLinkNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="連結不存在",
        )
    except ShareLinkExpiredError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="此連結已過期",
        )
    except NasFileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except NasFileAccessDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下載失敗：{e}",
        )
