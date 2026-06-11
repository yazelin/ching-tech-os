"""訊息中心 API"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ching_tech_os.models.auth import SessionData
from ching_tech_os.api.auth import get_current_session
from ching_tech_os.models.message import (
    MarkReadRequest,
    MarkReadResponse,
    MessageFilter,
    MessageListResponse,
    MessageResponse,
    MessageSeverity,
    MessageSource,
    UnreadCountResponse,
)
from ching_tech_os.services.message import (
    get_message,
    get_unread_count,
    mark_as_read,
    search_messages,
)

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.get(
    "",
    response_model=MessageListResponse,
    summary="搜尋訊息",
)
async def list_messages(
    severity: list[MessageSeverity] | None = Query(None, description="嚴重程度過濾"),
    source: list[MessageSource] | None = Query(None, description="來源過濾"),
    category: str | None = Query(None, description="細分類過濾"),
    user_id: int | None = Query(None, description="使用者 ID 過濾（僅管理員）"),
    start_date: datetime | None = Query(None, description="開始日期"),
    end_date: datetime | None = Query(None, description="結束日期"),
    search: str | None = Query(None, description="關鍵字搜尋"),
    is_read: bool | None = Query(None, description="已讀狀態過濾"),
    page: int = Query(1, ge=1, description="頁碼"),
    limit: int = Query(20, ge=1, le=100, description="每頁筆數"),
    session: SessionData = Depends(get_current_session),
) -> MessageListResponse:
    """搜尋訊息

    一般使用者只看發給自己的 + 全系統訊息；管理員可看全部、可用 user_id 查特定人。
    """
    is_admin = session.role == "admin"
    filter = MessageFilter(
        severity=severity,
        source=source,
        category=category,
        user_id=user_id if is_admin else None,
        restrict_to_user=None if is_admin else session.user_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
        is_read=is_read,
        page=page,
        limit=limit,
    )
    return await search_messages(filter)


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="取得未讀數量",
)
async def get_messages_unread_count(
    user_id: int | None = Query(None, description="使用者 ID（僅管理員）"),
    session: SessionData = Depends(get_current_session),
) -> UnreadCountResponse:
    """取得未讀訊息數量

    一般使用者只計算自己的 + 全系統；管理員可指定 user_id（None=全部）。
    """
    effective_user_id = user_id if session.role == "admin" else session.user_id
    count = await get_unread_count(effective_user_id)
    return UnreadCountResponse(count=count)


@router.post(
    "/mark-read",
    response_model=MarkReadResponse,
    summary="標記已讀",
)
async def mark_messages_read(
    request: MarkReadRequest,
    user_id: int | None = Query(None, description="使用者 ID（僅管理員，用於 all=true）"),
    session: SessionData = Depends(get_current_session),
) -> MarkReadResponse:
    """標記訊息為已讀

    可指定 ID 列表或 all=true 標記全部。
    一般使用者 all=true 只標記自己的 + 全系統訊息。
    """
    if not request.ids and not request.all:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必須提供 ids 或設定 all=true",
        )

    effective_user_id = user_id if session.role == "admin" else session.user_id
    count = await mark_as_read(
        ids=request.ids,
        mark_all=request.all,
        user_id=effective_user_id,
    )
    return MarkReadResponse(marked_count=count)


@router.get(
    "/{message_id}",
    response_model=MessageResponse,
    summary="取得單一訊息",
)
async def get_single_message(
    message_id: int,
    session: SessionData = Depends(get_current_session),
) -> MessageResponse:
    """取得單一訊息的完整內容

    一般使用者只能取發給自己的或全系統訊息，否則回 404（不洩漏存在）。

    Args:
        message_id: 訊息 ID
    """
    message = await get_message(message_id)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"訊息 {message_id} 不存在",
        )
    if session.role != "admin":
        msg_user_id = getattr(message, "user_id", None)
        # 只放行：發給自己的，或全系統訊息（user_id 為 None）
        if msg_user_id is not None and msg_user_id != session.user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"訊息 {message_id} 不存在",
            )
    return message
