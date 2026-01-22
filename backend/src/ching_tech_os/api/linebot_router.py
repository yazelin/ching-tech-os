"""Line Bot API 路由

包含：
- Webhook 端點（接收 Line 訊息）
- 群組/用戶/訊息管理 API
"""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks, Depends
from fastapi.responses import Response
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    VideoMessageContent,
    AudioMessageContent,
    FileMessageContent,
    JoinEvent,
    LeaveEvent,
    FollowEvent,
    UnfollowEvent,
)

from ..models.linebot import (
    LineGroupResponse,
    LineGroupListResponse,
    LineGroupUpdate,
    LineUserResponse,
    LineUserListResponse,
    LineMessageResponse,
    LineMessageListResponse,
    LineFileResponse,
    LineFileListResponse,
    ProjectBindingRequest,
    BindingCodeResponse,
    BindingStatusResponse,
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
    MemoryListResponse,
)
from ..api.auth import get_current_session
from ..models.auth import SessionData
from ..services.linebot import (
    verify_signature,
    get_webhook_parser,
    save_message,
    save_file_record,
    download_and_save_file,
    handle_join_event,
    handle_leave_event,
    list_groups,
    list_messages,
    list_users,
    list_users_with_binding,
    list_files,
    get_group_by_id,
    get_user_by_id,
    get_file_by_id,
    read_file_from_nas,
    delete_file,
    bind_group_to_project,
    unbind_group_from_project,
    delete_group,
    get_or_create_group,
    get_or_create_user,
    update_user_friend_status,
    get_group_profile,
    get_user_profile,
    # 綁定與存取控制
    generate_binding_code,
    verify_binding_code,
    unbind_line_user,
    get_binding_status,
    is_binding_code_format,
    check_line_access,
    update_group_settings,
    reply_text,
)
from ..services.linebot_ai import handle_text_message

logger = logging.getLogger("linebot_router")

router = APIRouter(prefix="/api/linebot", tags=["Line Bot"])


# ============================================================
# Webhook 端點
# ============================================================


@router.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str = Header(...),
):
    """
    Line Webhook 端點

    接收並處理 Line 平台發送的事件
    """
    # 取得請求 body
    body = await request.body()

    # 驗證簽章
    if not verify_signature(body, x_line_signature):
        logger.warning("Webhook 簽章驗證失敗")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 解析事件
    try:
        parser = get_webhook_parser()
        events = parser.parse(body.decode("utf-8"), x_line_signature)
    except Exception as e:
        logger.error(f"解析 Webhook 事件失敗: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook body")

    # 處理每個事件
    for event in events:
        background_tasks.add_task(process_event, event)

    return {"status": "ok"}


async def process_event(event) -> None:
    """
    處理單個 Line 事件

    Args:
        event: Line Webhook 事件
    """
    try:
        if isinstance(event, MessageEvent):
            await process_message_event(event)
        elif isinstance(event, JoinEvent):
            await process_join_event(event)
        elif isinstance(event, LeaveEvent):
            await process_leave_event(event)
        elif isinstance(event, FollowEvent):
            await process_follow_event(event)
        elif isinstance(event, UnfollowEvent):
            await process_unfollow_event(event)
        else:
            logger.debug(f"未處理的事件類型: {type(event).__name__}")
    except Exception as e:
        logger.error(f"處理事件失敗: {e}")


async def process_message_event(event: MessageEvent) -> None:
    """處理訊息事件"""
    message = event.message
    source = event.source

    # 取得用戶和群組 ID
    line_user_id = source.user_id if hasattr(source, "user_id") else None
    line_group_id = source.group_id if hasattr(source, "group_id") else None

    if not line_user_id:
        logger.warning("無法取得用戶 ID")
        return

    # 判斷訊息類型和檔案資訊
    file_name = None
    file_size = None
    duration = None

    # 用於處理回覆舊訊息
    quoted_message_id = None

    if isinstance(message, TextMessageContent):
        message_type = "text"
        content = message.text
        # 取得被回覆的訊息 ID（如果用戶回覆了某則訊息）
        quoted_message_id = message.quoted_message_id
        logger.info(f"TextMessage: quoted_message_id={quoted_message_id}")
    elif isinstance(message, ImageMessageContent):
        message_type = "image"
        content = None
    elif isinstance(message, VideoMessageContent):
        message_type = "video"
        content = None
        duration = getattr(message, "duration", None)
    elif isinstance(message, AudioMessageContent):
        message_type = "audio"
        content = None
        duration = getattr(message, "duration", None)
    elif isinstance(message, FileMessageContent):
        message_type = "file"
        file_name = message.file_name
        file_size = message.file_size
        content = file_name
    else:
        message_type = "unknown"
        content = None

    # 取得或建立用戶
    user_profile = await get_user_profile(line_user_id)
    user_uuid = await get_or_create_user(line_user_id, user_profile)

    # 取得群組 UUID（如果是群組訊息）
    group_uuid = None
    if line_group_id:
        group_profile = await get_group_profile(line_group_id)
        group_uuid = await get_or_create_group(line_group_id, group_profile)

    # 檢查是否為綁定驗證碼（僅個人對話、文字訊息、6 位數字）
    is_group = line_group_id is not None
    if not is_group and message_type == "text" and content and await is_binding_code_format(content):
        # 嘗試驗證綁定碼
        success, reply_msg = await verify_binding_code(user_uuid, content)
        if event.reply_token:
            try:
                await reply_text(event.reply_token, reply_msg)
            except Exception as e:
                logger.warning(f"回覆綁定訊息失敗: {e}")
        return  # 不再繼續處理

    # 儲存訊息
    message_uuid = await save_message(
        message_id=message.id,
        line_user_id=line_user_id,
        line_group_id=line_group_id,
        message_type=message_type,
        content=content,
        reply_token=event.reply_token,
    )

    logger.info(f"已儲存訊息: {message.id} (type={message_type})")

    # 處理媒體檔案（圖片、影片、音訊、檔案）
    if message_type in ("image", "video", "audio", "file"):
        await process_media_message(
            message_id=message.id,
            message_uuid=message_uuid,
            message_type=message_type,
            line_group_id=line_group_id,
            line_user_id=line_user_id,
            file_name=file_name,
            file_size=file_size,
            duration=duration,
        )

    # 如果是文字訊息，進行存取控制檢查並觸發 AI 處理
    if message_type == "text" and content:
        # 存取控制檢查
        has_access, deny_reason = await check_line_access(user_uuid, group_uuid)

        if not has_access:
            if deny_reason == "user_not_bound":
                # 個人對話：回覆提示訊息
                if not is_group and event.reply_token:
                    try:
                        await reply_text(
                            event.reply_token,
                            "請先在 CTOS 系統綁定您的 Line 帳號才能使用此服務。\n\n"
                            "步驟：\n"
                            "1. 登入 CTOS 系統\n"
                            "2. 進入 Line Bot 管理頁面\n"
                            "3. 點擊「綁定 Line 帳號」產生驗證碼\n"
                            "4. 將驗證碼發送給我完成綁定",
                        )
                    except Exception as e:
                        logger.warning(f"回覆未綁定訊息失敗: {e}")
                # 群組對話：靜默不回應
            elif deny_reason == "group_not_allowed":
                # 群組未開啟 AI 回應，靜默不回應
                pass
            return

        # 通過存取控制，觸發 AI 處理
        await handle_text_message(
            message_id=message.id,
            message_uuid=message_uuid,
            content=content,
            line_user_id=line_user_id,
            line_group_id=group_uuid,
            reply_token=event.reply_token,
            quoted_message_id=quoted_message_id,
        )


async def process_media_message(
    message_id: str,
    message_uuid,
    message_type: str,
    line_group_id: str | None,
    line_user_id: str | None,
    file_name: str | None = None,
    file_size: int | None = None,
    duration: int | None = None,
) -> None:
    """處理媒體訊息（圖片、影片、音訊、檔案）

    Args:
        message_id: Line 訊息 ID
        message_uuid: 訊息的 UUID
        message_type: 訊息類型
        line_group_id: Line 群組 ID
        line_user_id: Line 用戶 ID
        file_name: 原始檔案名稱
        file_size: 檔案大小
        duration: 音訊/影片長度（毫秒）
    """
    try:
        # 根據副檔名自動重新分類檔案類型
        actual_file_type = message_type
        if message_type == "file" and file_name and "." in file_name:
            ext = file_name.rsplit(".", 1)[-1].lower()
            # 影片格式
            if ext in ("mp4", "mov", "avi", "mkv", "webm", "m4v"):
                actual_file_type = "video"
                logger.info(f"檔案 {file_name} 重新分類為 video")
            # 音訊格式
            elif ext in ("mp3", "m4a", "wav", "ogg", "flac", "aac"):
                actual_file_type = "audio"
                logger.info(f"檔案 {file_name} 重新分類為 audio")
            # 圖片格式
            elif ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp", "heic"):
                actual_file_type = "image"
                logger.info(f"檔案 {file_name} 重新分類為 image")

        # 下載並儲存檔案到 NAS
        nas_path = await download_and_save_file(
            message_id=message_id,
            message_uuid=message_uuid,
            file_type=actual_file_type,
            line_group_id=line_group_id,
            line_user_id=line_user_id,
            file_name=file_name,
        )

        # 儲存檔案記錄到資料庫
        await save_file_record(
            message_uuid=message_uuid,
            file_type=actual_file_type,
            file_name=file_name,
            file_size=file_size,
            mime_type=None,  # 稍後可從內容判斷
            nas_path=nas_path,
            duration=duration,
        )

        logger.info(f"媒體訊息處理完成: {message_id} -> {nas_path}")

    except Exception as e:
        logger.error(f"處理媒體訊息失敗 {message_id}: {e}")


async def process_join_event(event: JoinEvent) -> None:
    """處理加入群組事件"""
    source = event.source
    line_group_id = source.group_id if hasattr(source, "group_id") else None

    if line_group_id:
        await handle_join_event(line_group_id)


async def process_leave_event(event: LeaveEvent) -> None:
    """處理離開群組事件"""
    source = event.source
    line_group_id = source.group_id if hasattr(source, "group_id") else None

    if line_group_id:
        await handle_leave_event(line_group_id)


async def process_follow_event(event: FollowEvent) -> None:
    """處理用戶加好友事件"""
    source = event.source
    line_user_id = source.user_id if hasattr(source, "user_id") else None

    if line_user_id:
        profile = await get_user_profile(line_user_id)
        await get_or_create_user(line_user_id, profile, is_friend=True)
        # 更新現有用戶的好友狀態
        await update_user_friend_status(line_user_id, is_friend=True)
        logger.info(f"用戶加好友: {line_user_id}")


async def process_unfollow_event(event: UnfollowEvent) -> None:
    """處理用戶封鎖/取消好友事件"""
    source = event.source
    line_user_id = source.user_id if hasattr(source, "user_id") else None

    if line_user_id:
        await update_user_friend_status(line_user_id, is_friend=False)
        logger.info(f"用戶封鎖/取消好友: {line_user_id}")


# ============================================================
# 群組管理 API
# ============================================================


@router.get("/groups", response_model=LineGroupListResponse)
async def api_list_groups(
    is_active: bool | None = None,
    project_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """列出 Line 群組"""
    items, total = await list_groups(
        is_active=is_active,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )
    return LineGroupListResponse(
        items=[LineGroupResponse(**item) for item in items],
        total=total,
    )


@router.get("/groups/{group_id}", response_model=LineGroupResponse)
async def api_get_group(group_id: UUID):
    """取得群組詳情"""
    group = await get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return LineGroupResponse(**group)


@router.post("/groups/{group_id}/bind-project")
async def api_bind_project(group_id: UUID, request: ProjectBindingRequest):
    """綁定群組到專案"""
    success = await bind_group_to_project(group_id, request.project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"status": "ok", "message": "專案綁定成功"}


@router.delete("/groups/{group_id}/bind-project")
async def api_unbind_project(group_id: UUID):
    """解除群組與專案的綁定"""
    success = await unbind_group_from_project(group_id)
    if not success:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"status": "ok", "message": "已解除專案綁定"}


@router.delete("/groups/{group_id}")
async def api_delete_group(group_id: UUID):
    """刪除群組及其相關資料

    刪除群組記錄，同時級聯刪除相關的訊息和檔案記錄。
    注意：NAS 上的實體檔案不會被刪除。
    """
    result = await delete_group(group_id)
    if not result:
        raise HTTPException(status_code=404, detail="Group not found")
    return {
        "status": "ok",
        "message": f"已刪除群組「{result['group_name']}」及 {result['deleted_messages']} 則訊息",
        "deleted_messages": result["deleted_messages"],
    }


# ============================================================
# 用戶管理 API
# ============================================================


@router.get("/users", response_model=LineUserListResponse)
async def api_list_users(limit: int = 50, offset: int = 0):
    """列出 Line 用戶"""
    items, total = await list_users(limit=limit, offset=offset)
    return LineUserListResponse(
        items=[LineUserResponse(**item) for item in items],
        total=total,
    )


@router.get("/users/{user_id}", response_model=LineUserResponse)
async def api_get_user(user_id: UUID):
    """取得用戶詳情"""
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return LineUserResponse(**user)


# ============================================================
# 訊息管理 API
# ============================================================


@router.get("/messages", response_model=LineMessageListResponse)
async def api_list_messages(
    group_id: UUID | None = None,
    user_id: UUID | None = None,
    page: int = 1,
    page_size: int = 50,
):
    """列出訊息"""
    offset = (page - 1) * page_size
    items, total = await list_messages(
        line_group_id=group_id,
        line_user_id=user_id,
        limit=page_size,
        offset=offset,
    )
    return LineMessageListResponse(
        items=[LineMessageResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================
# 檔案管理 API
# ============================================================


@router.get("/groups/{group_id}/files", response_model=LineFileListResponse)
async def api_list_group_files(
    group_id: UUID,
    file_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    """列出群組檔案

    Args:
        group_id: 群組 UUID
        file_type: 檔案類型過濾（image, video, audio, file）
        page: 頁碼
        page_size: 每頁數量
    """
    offset = (page - 1) * page_size
    items, total = await list_files(
        line_group_id=group_id,
        file_type=file_type,
        limit=page_size,
        offset=offset,
    )
    return LineFileListResponse(
        items=[LineFileResponse(**item) for item in items],
        total=total,
    )


@router.get("/files", response_model=LineFileListResponse)
async def api_list_files(
    group_id: UUID | None = None,
    user_id: UUID | None = None,
    file_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    """列出所有檔案（可過濾群組/用戶）

    Args:
        group_id: 群組 UUID 過濾
        user_id: 用戶 UUID 過濾
        file_type: 檔案類型過濾（image, video, audio, file）
        page: 頁碼
        page_size: 每頁數量
    """
    offset = (page - 1) * page_size
    items, total = await list_files(
        line_group_id=group_id,
        line_user_id=user_id,
        file_type=file_type,
        limit=page_size,
        offset=offset,
    )
    return LineFileListResponse(
        items=[LineFileResponse(**item) for item in items],
        total=total,
    )


@router.get("/files/{file_id}")
async def api_get_file(file_id: UUID):
    """取得檔案詳情"""
    file_info = await get_file_by_id(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")
    return LineFileResponse(**file_info)


@router.get("/files/{file_id}/download")
async def api_download_file(file_id: UUID):
    """下載檔案

    從 NAS 讀取檔案並回傳
    """
    # 取得檔案資訊
    file_info = await get_file_by_id(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    nas_path = file_info.get("nas_path")
    if not nas_path:
        raise HTTPException(status_code=404, detail="File not stored on NAS")

    # 從 NAS 讀取檔案
    content = await read_file_from_nas(nas_path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found on NAS")

    # 決定 Content-Type
    file_type = file_info.get("file_type", "file")
    mime_type = file_info.get("mime_type")

    if not mime_type:
        # 根據檔案類型猜測 MIME
        type_to_mime = {
            "image": "image/jpeg",
            "video": "video/mp4",
            "audio": "audio/m4a",
            "file": "application/octet-stream",
        }
        mime_type = type_to_mime.get(file_type, "application/octet-stream")

    # 決定檔案名稱
    file_name = file_info.get("file_name")
    if not file_name:
        # 從 nas_path 取得檔名
        file_name = nas_path.split("/")[-1]

    # 處理檔名中的非 ASCII 字元（使用 RFC 5987 編碼）
    from urllib.parse import quote
    safe_filename = quote(file_name, safe="")

    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}",
        },
    )


@router.delete("/files/{file_id}")
async def api_delete_file(file_id: UUID):
    """刪除檔案

    從 NAS 和資料庫中刪除檔案
    """
    success = await delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "ok", "message": "檔案已刪除"}


# ============================================================
# Line 綁定 API
# ============================================================


@router.post("/binding/generate-code", response_model=BindingCodeResponse)
async def api_generate_binding_code(session: SessionData = Depends(get_current_session)):
    """產生 Line 綁定驗證碼

    產生 6 位數字驗證碼，有效期 5 分鐘。
    用戶需在 Line 私訊 Bot 發送此驗證碼來完成綁定。
    """
    code, expires_at = await generate_binding_code(session.user_id)
    return BindingCodeResponse(code=code, expires_at=expires_at)


@router.get("/binding/status", response_model=BindingStatusResponse)
async def api_get_binding_status(session: SessionData = Depends(get_current_session)):
    """查詢當前用戶的 Line 綁定狀態"""
    status = await get_binding_status(session.user_id)
    return BindingStatusResponse(**status)


@router.delete("/binding")
async def api_unbind_line(session: SessionData = Depends(get_current_session)):
    """解除當前用戶的 Line 綁定"""
    success = await unbind_line_user(session.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="未找到綁定記錄")
    return {"status": "ok", "message": "已解除 Line 綁定"}


# ============================================================
# 群組設定 API（更新 allow_ai_response）
# ============================================================


@router.patch("/groups/{group_id}")
async def api_update_group(
    group_id: UUID,
    update: LineGroupUpdate,
    session: SessionData = Depends(get_current_session),
):
    """更新群組設定

    可更新：
    - allow_ai_response: 是否允許 AI 回應
    - project_id: 綁定專案（使用 bind-project API）
    """
    # 檢查群組是否存在
    group = await get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # 更新 allow_ai_response
    if update.allow_ai_response is not None:
        success = await update_group_settings(group_id, update.allow_ai_response)
        if not success:
            raise HTTPException(status_code=500, detail="更新失敗")

    # 重新取得群組資訊
    updated_group = await get_group_by_id(group_id)
    return LineGroupResponse(**updated_group)


# ============================================================
# 用戶列表（含綁定狀態）
# ============================================================


@router.get("/users-with-binding", response_model=LineUserListResponse)
async def api_list_users_with_binding(
    limit: int = 50,
    offset: int = 0,
    session: SessionData = Depends(get_current_session),
):
    """列出 Line 用戶（包含 CTOS 帳號綁定狀態）"""
    items, total = await list_users_with_binding(limit=limit, offset=offset)
    return LineUserListResponse(
        items=[LineUserResponse(**item) for item in items],
        total=total,
    )


# ============================================================
# 記憶管理 API
# ============================================================


@router.get("/groups/{group_id}/memories", response_model=MemoryListResponse)
async def api_list_group_memories(
    group_id: UUID,
    session: SessionData = Depends(get_current_session),
):
    """取得群組記憶列表"""
    from ..services.linebot import list_group_memories

    # 檢查群組是否存在
    group = await get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    items, total = await list_group_memories(group_id)
    return MemoryListResponse(
        items=[MemoryResponse(**item) for item in items],
        total=total,
    )


@router.post("/groups/{group_id}/memories", response_model=MemoryResponse)
async def api_create_group_memory(
    group_id: UUID,
    memory: MemoryCreate,
    session: SessionData = Depends(get_current_session),
):
    """新增群組記憶"""
    from ..services.linebot import create_group_memory, get_line_user_by_ctos_user

    # 檢查群組是否存在
    group = await get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # 取得當前用戶對應的 Line 用戶（用於記錄建立者）
    line_user = await get_line_user_by_ctos_user(session.user_id)
    created_by = line_user["id"] if line_user else None

    result = await create_group_memory(
        line_group_id=group_id,
        title=memory.title,
        content=memory.content,
        created_by=created_by,
    )
    return MemoryResponse(**result)


@router.get("/users/{user_id}/memories", response_model=MemoryListResponse)
async def api_list_user_memories(
    user_id: UUID,
    session: SessionData = Depends(get_current_session),
):
    """取得個人記憶列表"""
    from ..services.linebot import list_user_memories

    # 檢查用戶是否存在
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    items, total = await list_user_memories(user_id)
    return MemoryListResponse(
        items=[MemoryResponse(**item) for item in items],
        total=total,
    )


@router.post("/users/{user_id}/memories", response_model=MemoryResponse)
async def api_create_user_memory(
    user_id: UUID,
    memory: MemoryCreate,
    session: SessionData = Depends(get_current_session),
):
    """新增個人記憶"""
    from ..services.linebot import create_user_memory

    # 檢查用戶是否存在
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await create_user_memory(
        line_user_id=user_id,
        title=memory.title,
        content=memory.content,
    )
    return MemoryResponse(**result)


@router.put("/memories/{memory_id}", response_model=MemoryResponse)
async def api_update_memory(
    memory_id: UUID,
    memory: MemoryUpdate,
    session: SessionData = Depends(get_current_session),
):
    """更新記憶（群組或個人）"""
    from ..services.linebot import update_memory

    result = await update_memory(
        memory_id=memory_id,
        title=memory.title,
        content=memory.content,
        is_active=memory.is_active,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryResponse(**result)


@router.delete("/memories/{memory_id}")
async def api_delete_memory(
    memory_id: UUID,
    session: SessionData = Depends(get_current_session),
):
    """刪除記憶"""
    from ..services.linebot import delete_memory

    success = await delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "ok", "message": "記憶已刪除"}
