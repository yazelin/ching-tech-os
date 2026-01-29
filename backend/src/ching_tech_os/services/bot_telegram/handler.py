"""Telegram Bot 事件處理

Phase 3：接收文字訊息，透過 AI 回覆，並儲存用戶與訊息記錄。
"""

import logging
import time
from uuid import UUID

from telegram import Update

from .adapter import TelegramBotAdapter
from ..bot.ai import parse_ai_response
from ..claude_agent import call_claude
from ...database import get_connection
from ...config import settings
from ..linebot_agents import get_linebot_agent
from ..linebot_ai import (
    auto_prepare_generated_images,
    build_system_prompt,
    get_conversation_context,
    log_linebot_ai_call,
)
from ..linebot import (
    check_line_access,
    is_binding_code_format,
    verify_binding_code,
)
from ..mcp_server import get_mcp_tool_names
from ..permissions import get_mcp_tools_for_user, get_user_app_permissions_sync
from ..user import get_user_role_and_permissions

logger = logging.getLogger("bot_telegram.handler")

# 重置對話指令
RESET_COMMANDS = {"/新對話", "/reset"}

PLATFORM_TYPE = "telegram"


def _get_tenant_id() -> UUID:
    """取得預設 tenant_id"""
    return UUID(settings.default_tenant_id)


async def _ensure_bot_user(user, conn) -> UUID:
    """確保 Telegram 用戶存在於 bot_users，回傳 UUID"""
    tenant_id = _get_tenant_id()
    platform_user_id = str(user.id)
    display_name = user.full_name

    row = await conn.fetchrow(
        """
        SELECT id, display_name FROM bot_users
        WHERE platform_type = $1 AND platform_user_id = $2 AND tenant_id = $3
        """,
        PLATFORM_TYPE,
        platform_user_id,
        tenant_id,
    )

    if row:
        # 如果 display_name 有變化，更新
        if display_name and display_name != row["display_name"]:
            await conn.execute(
                "UPDATE bot_users SET display_name = $1, updated_at = NOW() WHERE id = $2",
                display_name,
                row["id"],
            )
        return row["id"]

    # 新建用戶
    row = await conn.fetchrow(
        """
        INSERT INTO bot_users (platform_type, platform_user_id, display_name, tenant_id)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        PLATFORM_TYPE,
        platform_user_id,
        display_name,
        tenant_id,
    )
    logger.info(f"建立 Telegram 用戶: {display_name} ({platform_user_id})")
    return row["id"]


async def _save_message(
    conn,
    message_id: str,
    bot_user_id: UUID,
    bot_group_id: UUID | None,
    message_type: str,
    content: str | None,
    is_from_bot: bool,
) -> UUID:
    """儲存訊息到 bot_messages"""
    tenant_id = _get_tenant_id()
    row = await conn.fetchrow(
        """
        INSERT INTO bot_messages (
            message_id, bot_user_id, bot_group_id,
            message_type, content, is_from_bot, tenant_id, platform_type
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        message_id,
        bot_user_id,
        bot_group_id,
        message_type,
        content,
        is_from_bot,
        tenant_id,
        PLATFORM_TYPE,
    )
    return row["id"]


async def handle_update(update: Update, adapter: TelegramBotAdapter) -> None:
    """處理 Telegram Update 事件"""
    if not update.message:
        logger.debug(f"跳過非訊息 Update: {update.update_id}")
        return

    message = update.message
    chat_id = str(message.chat_id)

    # 記錄訊息資訊
    user = message.from_user
    user_name = user.full_name if user else "未知"
    logger.info(
        f"收到 Telegram 訊息: chat_id={chat_id}, "
        f"user={user_name}, type={'text' if message.text else 'other'}"
    )

    if message.text:
        await _handle_text(message, chat_id, user, adapter)
    else:
        logger.debug(f"跳過非文字訊息 (chat_id={chat_id})")


async def _handle_text(
    message, chat_id: str, user, adapter: TelegramBotAdapter
) -> None:
    """處理文字訊息"""
    text = message.text
    tenant_id = _get_tenant_id()

    # 確保用戶存在
    bot_user_id: UUID | None = None
    try:
        async with get_connection() as conn:
            bot_user_id = await _ensure_bot_user(user, conn)
    except Exception as e:
        logger.error(f"確保用戶失敗: {e}", exc_info=True)

    # 檢查重置指令
    if text.strip() in RESET_COMMANDS:
        if bot_user_id:
            try:
                async with get_connection() as conn:
                    await conn.execute(
                        "UPDATE bot_users SET conversation_reset_at = NOW() WHERE id = $1",
                        bot_user_id,
                    )
            except Exception as e:
                logger.error(f"重置對話失敗: {e}", exc_info=True)
        await adapter.send_text(chat_id, "對話已重置 ✨")
        return

    # 檢查是否為綁定驗證碼（6 位數字）
    if bot_user_id and await is_binding_code_format(text.strip()):
        success, msg = await verify_binding_code(
            bot_user_id, text.strip(), tenant_id=tenant_id
        )
        await adapter.send_text(chat_id, msg)
        return

    # 存取控制檢查
    if bot_user_id:
        has_access, deny_reason = await check_line_access(
            bot_user_id, line_group_uuid=None, tenant_id=tenant_id
        )
        if not has_access and deny_reason == "user_not_bound":
            await adapter.send_text(
                chat_id,
                "請先在 CTOS 系統綁定您的 Telegram 帳號才能使用此服務。\n\n"
                "步驟：\n"
                "1. 登入 CTOS 系統\n"
                "2. 進入 Bot 管理頁面\n"
                "3. 點擊「綁定帳號」產生驗證碼\n"
                "4. 將 6 位數驗證碼發送給我完成綁定",
            )
            return

    # AI 對話
    try:
        await _handle_text_with_ai(text, chat_id, user, message.message_id, bot_user_id, adapter)
    except Exception as e:
        logger.error(f"AI 處理失敗: {e}", exc_info=True)
        await adapter.send_text(chat_id, "抱歉，處理訊息時發生錯誤，請稍後再試。")


async def _handle_text_with_ai(
    text: str,
    chat_id: str,
    user,
    message_id: int,
    bot_user_id: UUID | None,
    adapter: TelegramBotAdapter,
) -> None:
    """透過 AI 處理文字訊息並回覆"""
    # 0. 儲存用戶訊息
    message_uuid: UUID | None = None
    platform_user_id = str(user.id)
    tenant_id = _get_tenant_id()
    if bot_user_id:
        try:
            async with get_connection() as conn:
                message_uuid = await _save_message(
                    conn,
                    message_id=f"tg_{message_id}",
                    bot_user_id=bot_user_id,
                    bot_group_id=None,
                    message_type="text",
                    content=text,
                    is_from_bot=False,
                )
        except Exception as e:
            logger.error(f"儲存用戶訊息失敗: {e}", exc_info=True)

    # 0.5 取得對話歷史
    history: list[dict] = []
    try:
        history, _images, _files = await get_conversation_context(
            line_group_id=None,
            line_user_id=platform_user_id,
            limit=20,
            exclude_message_id=message_uuid,
        )
    except Exception as e:
        logger.error(f"取得對話歷史失敗: {e}", exc_info=True)

    # 1. 取得 Agent 設定（使用個人對話 Agent）
    agent = await get_linebot_agent(is_group=False)
    if not agent:
        logger.error("找不到 Agent 設定")
        await adapter.send_text(chat_id, "系統尚未設定 AI Agent，請聯繫管理員。")
        return

    model = agent.get("model", "sonnet")
    base_prompt = agent.get("system_prompt", {}).get("content", "")
    builtin_tools = agent.get("tools") or []

    # 2. 取得用戶權限（用於工具過濾和 system_prompt）
    user_role = "user"
    user_permissions = None
    app_permissions: dict[str, bool] = {}
    if bot_user_id:
        try:
            async with get_connection() as conn:
                row = await conn.fetchrow(
                    "SELECT user_id FROM bot_users WHERE id = $1", bot_user_id
                )
                if row and row["user_id"]:
                    user_info = await get_user_role_and_permissions(
                        row["user_id"], tenant_id
                    )
                    user_role = user_info["role"]
                    user_permissions = user_info["permissions"]
                    app_permissions = get_user_app_permissions_sync(
                        user_role, user_info.get("user_data")
                    )
        except Exception as e:
            logger.error(f"取得用戶權限失敗: {e}", exc_info=True)

    if not app_permissions:
        app_permissions = get_user_app_permissions_sync("user", None)

    # 2.5 建立系統提示
    system_prompt = await build_system_prompt(
        line_group_id=None,
        line_user_id=None,
        base_prompt=base_prompt,
        builtin_tools=builtin_tools,
        app_permissions=app_permissions,
    )

    # 3. 組裝工具列表（根據用戶權限過濾）
    mcp_tools = await get_mcp_tool_names(exclude_group_only=True)
    mcp_tools = get_mcp_tools_for_user(user_role, user_permissions, mcp_tools)
    nanobanana_tools = [
        "mcp__nanobanana__generate_image",
        "mcp__nanobanana__edit_image",
    ]
    all_tools = builtin_tools + mcp_tools + nanobanana_tools + ["Read"]

    # 4. 呼叫 AI（含對話歷史）
    start_time = time.time()
    response = await call_claude(
        prompt=text,
        model=model,
        history=history,
        system_prompt=system_prompt,
        timeout=480,
        tools=all_tools,
    )
    duration_ms = int((time.time() - start_time) * 1000)

    # 4.5 記錄 AI Log
    if message_uuid:
        try:
            await log_linebot_ai_call(
                message_uuid=message_uuid,
                line_group_id=None,
                is_group=False,
                input_prompt=text,
                history=history,
                system_prompt=system_prompt,
                allowed_tools=all_tools,
                model=model,
                response=response,
                duration_ms=duration_ms,
                context_type_override="telegram-personal",
            )
        except Exception as e:
            logger.error(f"記錄 AI Log 失敗: {e}", exc_info=True)

    if not response.success:
        logger.error(f"AI 呼叫失敗: {response.error}")
        await adapter.send_text(chat_id, "AI 回應失敗，請稍後再試。")
        return

    # 5. 處理生成的圖片
    ai_message = await auto_prepare_generated_images(
        response.message, response.tool_calls
    )

    # 6. 解析回應（分離文字和檔案）
    reply_text, files = parse_ai_response(ai_message)

    # 7. 發送回覆
    if reply_text:
        await adapter.send_text(chat_id, reply_text)

    for file_info in files:
        file_type = file_info.get("type", "")
        url = file_info.get("url", "")
        if not url:
            continue
        try:
            if file_type == "image":
                await adapter.send_image(chat_id, url)
            else:
                await adapter.send_file(
                    chat_id, url, file_info.get("name", "file")
                )
        except Exception as e:
            logger.warning(f"發送檔案失敗: {e}")

    # 沒有任何回覆內容時的 fallback
    if not reply_text and not files:
        reply_text = "（AI 沒有產生回覆內容）"
        await adapter.send_text(chat_id, reply_text)

    # 儲存 Bot 回覆訊息
    if bot_user_id:
        try:
            async with get_connection() as conn:
                await _save_message(
                    conn,
                    message_id=f"tg_reply_{message_id}",
                    bot_user_id=bot_user_id,
                    bot_group_id=None,
                    message_type="text",
                    content=reply_text or "",
                    is_from_bot=True,
                )
        except Exception as e:
            logger.error(f"儲存 Bot 回覆失敗: {e}", exc_info=True)
