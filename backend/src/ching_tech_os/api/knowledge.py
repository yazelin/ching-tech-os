"""知識庫 API"""

import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from ching_tech_os.config import settings
from ching_tech_os.services.message import log_message
from ching_tech_os.models.knowledge import (
    AttachmentUpdate,
    HistoryResponse,
    KnowledgeAttachment,
    KnowledgeCreate,
    KnowledgeListResponse,
    KnowledgeResponse,
    KnowledgeUpdate,
    TagsResponse,
    VersionResponse,
)
from ching_tech_os.services.knowledge import (
    create_knowledge,
    delete_attachment,
    delete_knowledge,
    update_attachment,
    get_all_tags,
    get_history,
    get_knowledge,
    get_nas_attachment,
    get_version,
    rebuild_index,
    search_knowledge,
    update_knowledge,
    upload_attachment,
    KnowledgeError,
    KnowledgeNotFoundError,
)
from ching_tech_os.services.permissions import check_knowledge_permission_async
from ching_tech_os.services.user import get_user_preferences, _parse_preferences
from ching_tech_os.api.auth import get_current_session
from ching_tech_os.models.auth import SessionData

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get(
    "",
    response_model=KnowledgeListResponse,
    summary="搜尋/列出知識",
)
async def list_knowledge(
    q: str | None = Query(None, description="關鍵字搜尋"),
    project: str | None = Query(None, description="專案過濾"),
    type: str | None = Query(None, description="類型過濾"),
    category: str | None = Query(None, description="分類過濾"),
    role: str | None = Query(None, description="角色過濾"),
    level: str | None = Query(None, description="層級過濾"),
    topics: list[str] | None = Query(None, description="主題過濾"),
    scope: str | None = Query(None, description="範圍過濾（global、personal）"),
    session: SessionData = Depends(get_current_session),
) -> KnowledgeListResponse:
    """搜尋或列出知識

    支援關鍵字全文搜尋（使用 ripgrep）與多維度標籤過濾。
    預設顯示全域知識 + 自己的個人知識。
    """
    try:
        return search_knowledge(
            query=q,
            project=project,
            kb_type=type,
            category=category,
            role=role,
            level=level,
            topics=topics,
            scope=scope,
            current_username=session.username,
            tenant_id=session.tenant_id,
        )
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/tags",
    response_model=TagsResponse,
    summary="取得標籤列表",
)
async def get_tags(
    session: SessionData = Depends(get_current_session),
) -> TagsResponse:
    """取得所有可用標籤（按類型分組，專案從資料庫動態載入）"""
    try:
        return await get_all_tags(tenant_id=session.tenant_id)
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/rebuild-index",
    summary="重建索引",
)
async def rebuild_knowledge_index(
    session: SessionData = Depends(get_current_session),
) -> dict:
    """重建知識庫索引

    掃描所有知識檔案並重新建立 index.json。
    """
    try:
        return rebuild_index(tenant_id=session.tenant_id)
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/attachments/{path:path}",
    summary="取得 NAS 附件",
)
async def get_attachment(path: str) -> Response:
    """代理取得 NAS 上的附件

    Args:
        path: 附件路徑（不含 nas://knowledge/ 前綴）
    """
    try:
        content = get_nas_attachment(path)
        filename = path.split("/")[-1]
        mime_type, _ = mimetypes.guess_type(filename)
        return Response(
            content=content,
            media_type=mime_type or "application/octet-stream",
        )
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/assets/{path:path}",
    summary="取得本機附件",
)
async def get_local_asset(
    path: str,
    session: SessionData = Depends(get_current_session),
) -> Response:
    """取得本機知識庫附件

    Args:
        path: 附件路徑（如 images/kb-001-file.png）
    """
    from pathlib import Path

    # 安全檢查：防止路徑穿越攻擊
    if ".." in path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無效的路徑",
        )

    # 使用租戶專屬路徑
    tenant_id = session.tenant_id if session.tenant_id else None
    assets_base = Path(settings.get_tenant_knowledge_path(tenant_id)) / "assets"
    file_path = assets_base / path

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"檔案不存在：{path}",
        )

    try:
        content = file_path.read_bytes()
        filename = file_path.name
        mime_type, _ = mimetypes.guess_type(filename)
        return Response(
            content=content,
            media_type=mime_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{kb_id}",
    response_model=KnowledgeResponse,
    summary="取得單一知識",
)
async def get_single_knowledge(
    kb_id: str,
    session: SessionData = Depends(get_current_session),
) -> KnowledgeResponse:
    """取得單一知識的完整內容與元資料

    Args:
        kb_id: 知識 ID（如 kb-001）
    """
    try:
        return get_knowledge(kb_id, tenant_id=session.tenant_id)
    except KnowledgeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知識 {kb_id} 不存在",
        )
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "",
    response_model=KnowledgeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增知識",
)
async def create_new_knowledge(
    data: KnowledgeCreate,
    session: SessionData = Depends(get_current_session),
) -> KnowledgeResponse:
    """建立新知識

    系統會自動分配 ID，並根據標題產生 slug（若未提供）。
    個人知識會自動設定 owner 為目前使用者。
    建立全域知識需要 global_write 權限。
    """
    # 權限檢查：建立全域知識需要權限
    if data.scope == "global":
        preferences = await get_user_preferences(session.user_id) if session.user_id else None
        if not await check_knowledge_permission_async(
            session.username, preferences, None, "global", "write",
            user_id=session.user_id, project_id=data.project_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您沒有建立全域知識的權限",
            )

    try:
        # 傳入 owner（建立個人知識時使用）和 tenant_id
        result = create_knowledge(data, owner=session.username, tenant_id=session.tenant_id)

        # 記錄到訊息中心
        try:
            await log_message(
                severity="info",
                source="knowledge-base",
                title="知識庫新增",
                content=f"新增知識: {result.title}",
                category="app",
                metadata={"kb_id": result.id, "title": result.title, "scope": result.scope}
            )
        except Exception as e:
            print(f"[knowledge] log_message error: {e}")

        return result
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put(
    "/{kb_id}",
    response_model=KnowledgeResponse,
    summary="更新知識",
)
async def update_existing_knowledge(
    kb_id: str,
    data: KnowledgeUpdate,
    session: SessionData = Depends(get_current_session),
) -> KnowledgeResponse:
    """更新知識內容或元資料

    只需提供要更新的欄位。
    需要對該知識有寫入權限。
    """
    # 取得知識以檢查權限
    try:
        knowledge = get_knowledge(kb_id, tenant_id=session.tenant_id)
    except KnowledgeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知識 {kb_id} 不存在",
        )

    # 權限檢查
    preferences = await get_user_preferences(session.user_id) if session.user_id else None
    if not await check_knowledge_permission_async(
        session.username, preferences, knowledge.owner, knowledge.scope, "write",
        user_id=session.user_id, project_id=knowledge.project_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您沒有編輯此知識的權限",
        )

    try:
        result = update_knowledge(kb_id, data, tenant_id=session.tenant_id)

        # 記錄到訊息中心
        try:
            await log_message(
                severity="info",
                source="knowledge-base",
                title="知識庫更新",
                content=f"更新知識: {result.title}",
                category="app",
                metadata={"kb_id": kb_id, "title": result.title}
            )
        except Exception as e:
            print(f"[knowledge] log_message error: {e}")

        return result
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{kb_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除知識",
)
async def delete_existing_knowledge(
    kb_id: str,
    session: SessionData = Depends(get_current_session),
) -> None:
    """刪除知識

    會同時刪除檔案和索引記錄。
    需要對該知識有刪除權限。
    """
    # 取得知識以檢查權限
    try:
        knowledge = get_knowledge(kb_id, tenant_id=session.tenant_id)
    except KnowledgeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知識 {kb_id} 不存在",
        )

    # 權限檢查
    preferences = await get_user_preferences(session.user_id) if session.user_id else None
    if not await check_knowledge_permission_async(
        session.username, preferences, knowledge.owner, knowledge.scope, "delete",
        user_id=session.user_id, project_id=knowledge.project_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您沒有刪除此知識的權限",
        )

    try:
        delete_knowledge(kb_id, tenant_id=session.tenant_id)

        # 記錄到訊息中心
        try:
            await log_message(
                severity="info",
                source="knowledge-base",
                title="知識庫刪除",
                content=f"刪除知識: {kb_id}",
                category="app",
                metadata={"kb_id": kb_id}
            )
        except Exception as e:
            print(f"[knowledge] log_message error: {e}")

    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{kb_id}/history",
    response_model=HistoryResponse,
    summary="取得版本歷史",
)
async def get_knowledge_history(
    kb_id: str,
    session: SessionData = Depends(get_current_session),
) -> HistoryResponse:
    """取得知識的 Git 版本歷史

    使用 git log --follow 追蹤檔案歷史（含重命名）。
    """
    try:
        return get_history(kb_id, tenant_id=session.tenant_id)
    except KnowledgeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知識 {kb_id} 不存在",
        )
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{kb_id}/version/{commit}",
    response_model=VersionResponse,
    summary="取得特定版本",
)
async def get_knowledge_version(
    kb_id: str,
    commit: str,
    session: SessionData = Depends(get_current_session),
) -> VersionResponse:
    """取得知識的特定版本內容

    使用 git show 取得該版本的檔案內容。
    """
    try:
        return get_version(kb_id, commit, tenant_id=session.tenant_id)
    except KnowledgeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知識 {kb_id} 不存在",
        )
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{kb_id}/attachments",
    summary="上傳附件",
)
async def upload_knowledge_attachment(
    kb_id: str,
    file: UploadFile = File(...),
    description: Annotated[str | None, Form()] = None,
    session: SessionData = Depends(get_current_session),
) -> dict:
    """上傳附件

    小於 1MB 的檔案存本機（Git 追蹤），大於等於 1MB 存 NAS。
    """
    # 確認知識存在
    try:
        get_knowledge(kb_id, tenant_id=session.tenant_id)
    except KnowledgeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知識 {kb_id} 不存在",
        )

    try:
        content = await file.read()
        filename = file.filename or "unnamed"
        attachment = upload_attachment(kb_id, filename, content, description, tenant_id=session.tenant_id)
        return {
            "success": True,
            "attachment": attachment.model_dump(),
        }
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{kb_id}/attachments/{attachment_idx}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除附件",
)
async def delete_knowledge_attachment(
    kb_id: str,
    attachment_idx: int,
    session: SessionData = Depends(get_current_session),
) -> None:
    """刪除附件

    Args:
        kb_id: 知識 ID
        attachment_idx: 附件索引（從 0 開始）
    """
    # 確認知識存在
    try:
        get_knowledge(kb_id, tenant_id=session.tenant_id)
    except KnowledgeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知識 {kb_id} 不存在",
        )

    try:
        delete_attachment(kb_id, attachment_idx, tenant_id=session.tenant_id)
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/{kb_id}/attachments/{attachment_idx}",
    response_model=KnowledgeAttachment,
    summary="更新附件資訊",
)
async def update_knowledge_attachment(
    kb_id: str,
    attachment_idx: int,
    data: AttachmentUpdate,
    session: SessionData = Depends(get_current_session),
) -> KnowledgeAttachment:
    """更新附件資訊（說明、類型）

    Args:
        kb_id: 知識 ID
        attachment_idx: 附件索引（從 0 開始）
        data: 更新資料
    """
    # 確認知識存在
    try:
        get_knowledge(kb_id, tenant_id=session.tenant_id)
    except KnowledgeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知識 {kb_id} 不存在",
        )

    try:
        return update_attachment(
            kb_id,
            attachment_idx,
            description=data.description,
            attachment_type=data.type,
            tenant_id=session.tenant_id,
        )
    except KnowledgeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
