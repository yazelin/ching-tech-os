"""訊息中心 API"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

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
    user_id: int | None = Query(None, description="使用者 ID 過濾"),
    start_date: datetime | None = Query(None, description="開始日期"),
    end_date: datetime | None = Query(None, description="結束日期"),
    search: str | None = Query(None, description="關鍵字搜尋"),
    is_read: bool | None = Query(None, description="已讀狀態過濾"),
    page: int = Query(1, ge=1, description="頁碼"),
    limit: int = Query(20, ge=1, le=100, description="每頁筆數"),
) -> MessageListResponse:
    """搜尋訊息

    支援多維度過濾與分頁。
    """
    filter = MessageFilter(
        severity=severity,
        source=source,
        category=category,
        user_id=user_id,
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
    user_id: int | None = Query(None, description="使用者 ID"),
) -> UnreadCountResponse:
    """取得未讀訊息數量

    若指定 user_id，只計算該使用者相關的訊息。
    """
    count = await get_unread_count(user_id)
    return UnreadCountResponse(count=count)


@router.post(
    "/mark-read",
    response_model=MarkReadResponse,
    summary="標記已讀",
)
async def mark_messages_read(
    request: MarkReadRequest,
    user_id: int | None = Query(None, description="使用者 ID（用於 all=true）"),
) -> MarkReadResponse:
    """標記訊息為已讀

    可指定 ID 列表或 all=true 標記全部。
    """
    if not request.ids and not request.all:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必須提供 ids 或設定 all=true",
        )

    count = await mark_as_read(
        ids=request.ids,
        mark_all=request.all,
        user_id=user_id,
    )
    return MarkReadResponse(marked_count=count)


@router.get(
    "/{message_id}",
    response_model=MessageResponse,
    summary="取得單一訊息",
)
async def get_single_message(message_id: int) -> MessageResponse:
    """取得單一訊息的完整內容

    Args:
        message_id: 訊息 ID
    """
    message = await get_message(message_id)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"訊息 {message_id} 不存在",
        )
    return message
