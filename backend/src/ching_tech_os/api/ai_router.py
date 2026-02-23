"""AI 對話 REST API 路由"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from ..models.ai import (
    ChatCreate,
    ChatDetailResponse,
    ChatResponse,
    ChatUpdate,
)
from ..services import ai_chat
from ..services.session import session_manager

router = APIRouter(prefix="/api/ai", tags=["AI"])


async def get_current_user_id(request: Request) -> int:
    """從 session 取得當前使用者 ID

    需從 session 中的資料庫 user_id 取得，若驗證失敗則回傳 401。
    """
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="未登入或 session 已過期")

    session = await session_manager.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="未登入或 session 已過期")

    if session.user_id is None:
        raise HTTPException(status_code=401, detail="未登入或 session 已過期")

    return session.user_id


@router.get("/chats", response_model=list[ChatResponse])
async def list_chats(user_id: int = Depends(get_current_user_id)):
    """取得使用者的對話列表"""
    chats = await ai_chat.get_user_chats(user_id)
    return chats


@router.post("/chats", response_model=ChatDetailResponse)
async def create_chat(
    data: ChatCreate, user_id: int = Depends(get_current_user_id)
):
    """建立新對話"""
    chat = await ai_chat.create_chat(
        user_id=user_id,
        title=data.title,
        model=data.model,
        prompt_name=data.prompt_name,
    )
    return chat


@router.get("/chats/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(chat_id: UUID, user_id: int = Depends(get_current_user_id)):
    """取得對話詳情"""
    chat = await ai_chat.get_chat(chat_id, user_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="對話不存在")
    return chat


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: UUID, user_id: int = Depends(get_current_user_id)):
    """刪除對話"""
    success = await ai_chat.delete_chat(chat_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="對話不存在")
    return {"success": True}


@router.patch("/chats/{chat_id}", response_model=ChatDetailResponse)
async def update_chat(
    chat_id: UUID, data: ChatUpdate, user_id: int = Depends(get_current_user_id)
):
    """更新對話（標題、模型等）"""
    chat = await ai_chat.update_chat(
        chat_id=chat_id,
        user_id=user_id,
        title=data.title,
        model=data.model,
        prompt_name=data.prompt_name,
    )
    if chat is None:
        raise HTTPException(status_code=404, detail="對話不存在")
    return chat


# 注意：/prompts endpoint 已移至 ai_management.py，使用資料庫管理
