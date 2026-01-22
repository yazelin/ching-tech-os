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
    - local://knowledge/assets/images/{kb_id}-{filename} (本機附件，新格式)
    - local://knowledge/images/{kb_id}-{filename} (本機附件，舊格式)
    - local/images/{kb_id}-{filename} (本機附件，正規化格式)
    - ctos://knowledge/attachments/{kb_id}/{filename} (NAS 附件，新格式)
    - nas://knowledge/attachments/{kb_id}/{filename} (NAS 附件，舊格式)
    - attachments/{kb_id}/{filename} (NAS 附件)
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

        # 安全檢查：防止路徑穿越
        if ".." in path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="無效的路徑",
            )

        # 判斷附件類型並正規化路徑
        # 注意：nginx 預設會把 // 合併成 /，所以需要同時支援 :// 和 :/ 格式
        # 1. 本機附件：local://knowledge/... 或 local:/knowledge/... 格式
        is_local_asset = False
        if path.startswith("local://knowledge/assets/images/"):
            # 新格式：local://knowledge/assets/images/...
            path = "local/images/" + path[len("local://knowledge/assets/images/"):]
            is_local_asset = True
        elif path.startswith("local:/knowledge/assets/images/"):
            # 新格式（nginx 合併後）：local:/knowledge/assets/images/...
            path = "local/images/" + path[len("local:/knowledge/assets/images/"):]
            is_local_asset = True
        elif path.startswith("local://knowledge/images/"):
            # 舊格式：local://knowledge/images/...
            path = "local/images/" + path[len("local://knowledge/images/"):]
            is_local_asset = True
        elif path.startswith("local:/knowledge/images/"):
            # 舊格式（nginx 合併後）：local:/knowledge/images/...
            path = "local/images/" + path[len("local:/knowledge/images/"):]
            is_local_asset = True
        elif path.startswith("local/"):
            # 正規化格式：local/images/...
            is_local_asset = True

        # 2. NAS 附件：ctos://knowledge/... 或 nas://knowledge/... 格式
        if path.startswith("ctos://knowledge/attachments/"):
            # 新格式：ctos://knowledge/attachments/...
            path = "attachments/" + path[len("ctos://knowledge/attachments/"):]
        elif path.startswith("ctos:/knowledge/attachments/"):
            # 新格式（nginx 合併後）：ctos:/knowledge/attachments/...
            path = "attachments/" + path[len("ctos:/knowledge/attachments/"):]
        elif path.startswith("nas://knowledge/"):
            # 舊格式：nas://knowledge/...
            path = path[len("nas://knowledge/"):]
        elif path.startswith("nas:/knowledge/"):
            # 舊格式（nginx 合併後）：nas:/knowledge/...
            path = path[len("nas:/knowledge/"):]

        if is_local_asset:
            # 本機附件：驗證檔名包含 kb_id
            if not filename.startswith(f"{kb_id}-"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="無權存取此附件",
                )

            # 將 local/ 轉換為 assets/
            assets_path = "assets/" + path[len("local/"):]

            # 讀取本機檔案
            assets_base = FilePath(settings.knowledge_data_path)
            file_path = assets_base / assets_path

            if not file_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="附件不存在",
                )

            content = file_path.read_bytes()
        else:
            # NAS 附件
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
    summary="下載檔案",
)
async def download_shared_file(token: str) -> Response:
    """透過分享連結下載檔案

    支援 nas_file 和 project_attachment 類型的分享連結，無需登入。
    """
    from urllib.parse import quote
    from ..services.share import get_project_attachment_info
    from ..services.project import get_attachment_content, ProjectError

    try:
        # 驗證 token 有效
        link_info = await get_link_info(token)
        resource_type = link_info["resource_type"]

        # 支援 NAS 檔案和專案附件
        if resource_type == "nas_file":
            file_path = link_info["resource_id"]
            # 驗證並取得檔案路徑
            full_path = validate_nas_file_path(file_path)
            # 讀取檔案內容
            content = full_path.read_bytes()
            filename = full_path.name
        elif resource_type == "project_attachment":
            attachment_id = link_info["resource_id"]
            # 取得附件資訊（已包含 project_id）
            attachment_info = await get_project_attachment_info(attachment_id)
            project_id = attachment_info["project_id"]
            # 使用專案服務讀取附件內容
            from uuid import UUID
            content, filename = await get_attachment_content(project_id, UUID(attachment_id))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="此連結不是檔案下載連結",
            )

        # 取得 MIME 類型
        mime_type, _ = mimetypes.guess_type(filename)

        # 處理檔名編碼（支援中文）
        encoded_filename = quote(filename)

        # 圖片和 HTML 用 inline（讓瀏覽器直接顯示），其他用 attachment
        is_image = mime_type and mime_type.startswith("image/")
        is_html = mime_type == "text/html"
        disposition = "inline" if (is_image or is_html) else "attachment"

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
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ProjectError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下載失敗：{e}",
        )
