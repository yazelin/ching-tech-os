"""Telegram Bot 事件處理

Phase 3：接收文字訊息，透過 AI 回覆，並儲存用戶與訊息記錄。
支援私訊和群組對話。
"""

import logging
import os
import time
from telegram import Update

from .adapter import TelegramBotAdapter
from ..bot.ai import parse_ai_response
from ..claude_agent import call_claude
from ...database import get_connection
from ..linebot_agents import get_linebot_agent
from ..linebot_ai import (
    auto_prepare_generated_images,
    build_system_prompt,
    get_conversation_context,
    log_linebot_ai_call,
)
from ..bot_line import (
    check_line_access,
    is_binding_code_format,
    save_file_record,
    verify_binding_code,
)
from ..linebot_agents import (
    get_mcp_servers_for_user,
    get_tools_for_user,
    get_tool_routing_for_user,
)
from ..mcp import get_mcp_tool_names
from ..permissions import get_mcp_tools_for_user, get_user_app_permissions_sync
from ..user import get_user_role_and_permissions
from .media import download_telegram_document, download_telegram_photo

logger = logging.getLogger("bot_telegram.handler")

# /start 歡迎訊息
START_MESSAGE = (
    "👋 歡迎使用 CTOS Bot！\n\n"
    "我是 Ching Tech OS 的 AI 助手，可以幫你：\n"
    "• 回答問題和對話\n"
    "• 管理專案和筆記\n"
    "• 生成和編輯圖片\n\n"
    "📌 首次使用請先綁定帳號：\n"
    "1. 登入 CTOS 系統\n"
    "2. 進入 Bot 管理頁面\n"
    "3. 點擊「綁定帳號」產生驗證碼\n"
    "4. 將 6 位數驗證碼發送給我\n\n"
    "輸入 /help 查看更多功能"
)

# /help 說明訊息
HELP_MESSAGE = (
    "📖 CTOS Bot 使用說明\n\n"
    "💬 基本對話\n"
    "直接傳送文字即可與 AI 對話\n\n"
    "🔗 帳號綁定\n"
    "發送 6 位數驗證碼完成綁定\n\n"
    "📝 指令列表\n"
    "/start — 歡迎訊息\n"
    "/help — 查看此說明\n"
    "/reset 或 /新對話 — 重置對話記錄\n\n"
    "👥 群組使用\n"
    "在群組中 @Bot 或回覆 Bot 訊息即可觸發"
)

PLATFORM_TYPE = "telegram"

# 群組 chat type
GROUP_CHAT_TYPES = {"group", "supergroup"}


async def _ensure_bot_user(user, conn) -> str:
    """確保 Telegram 用戶存在於 bot_users，回傳 UUID"""
    platform_user_id = str(user.id)
    display_name = user.full_name

    row = await conn.fetchrow(
        """
        SELECT id, display_name FROM bot_users
        WHERE platform_type = $1 AND platform_user_id = $2
        """,
        PLATFORM_TYPE,
        platform_user_id,
    )

    if row:
        # 如果 display_name 有變化，更新
        if display_name and display_name != row["display_name"]:
            await conn.execute(
                "UPDATE bot_users SET display_name = $1, updated_at = NOW() WHERE id = $2",
                display_name,
                row["id"],
            )
        return str(row["id"])

    # 新建用戶
    row = await conn.fetchrow(
        """
        INSERT INTO bot_users (platform_type, platform_user_id, display_name)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        PLATFORM_TYPE,
        platform_user_id,
        display_name,
    )
    logger.info(f"建立 Telegram 用戶: {display_name} ({platform_user_id})")
    return str(row["id"])


async def _ensure_bot_group(chat, conn) -> str:
    """確保 Telegram 群組存在於 bot_groups，回傳 UUID"""
    platform_group_id = str(chat.id)
    group_name = chat.title or "未知群組"

    row = await conn.fetchrow(
        """
        SELECT id, name FROM bot_groups
        WHERE platform_type = $1 AND platform_group_id = $2
        """,
        PLATFORM_TYPE,
        platform_group_id,
    )

    if row:
        if group_name and group_name != row["name"]:
            await conn.execute(
                "UPDATE bot_groups SET name = $1, updated_at = NOW() WHERE id = $2",
                group_name,
                row["id"],
            )
        return str(row["id"])

    # 新建群組（預設 allow_ai_response = false）
    row = await conn.fetchrow(
        """
        INSERT INTO bot_groups (platform_type, platform_group_id, name)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        PLATFORM_TYPE,
        platform_group_id,
        group_name,
    )
    logger.info(f"建立 Telegram 群組: {group_name} ({platform_group_id})")
    return str(row["id"])


async def _save_message(
    conn,
    message_id: str,
    bot_user_id: str,
    bot_group_id: str | None,
    message_type: str,
    content: str | None,
    is_from_bot: bool,
) -> str:
    """儲存訊息到 bot_messages"""
    row = await conn.fetchrow(
        """
        INSERT INTO bot_messages (
            message_id, bot_user_id, bot_group_id,
            message_type, content, is_from_bot, platform_type
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        message_id,
        bot_user_id,
        bot_group_id,
        message_type,
        content,
        is_from_bot,
        PLATFORM_TYPE,
    )
    return row["id"]


def _should_respond_in_group(message, bot_username: str | None) -> bool:
    """判斷群組訊息是否應該觸發 AI 回覆

    條件：
    1. 訊息中 @Bot（mention）
    2. 回覆 Bot 的訊息
    """
    # 檢查是否回覆 Bot 的訊息
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.is_bot:
            return True

    # 檢查是否 @Bot
    if message.entities and bot_username:
        for entity in message.entities:
            if entity.type == "mention":
                # 取得 mention 的文字內容
                mention_text = message.text[entity.offset : entity.offset + entity.length]
                if mention_text.lower() == f"@{bot_username.lower()}":
                    return True

    return False


REPLY_IMAGE_DIR = "/tmp/bot-images"
os.makedirs(REPLY_IMAGE_DIR, exist_ok=True)


async def _extract_reply_from_message(reply, bot=None) -> str:
    """從 Telegram message 物件直接取得回覆內容（不查 DB）

    支援文字、圖片（含 caption）和檔案訊息。
    圖片會下載到暫存目錄讓 AI 讀取。
    """
    parts = []

    # 圖片：下載到暫存目錄
    if reply.photo and bot:
        try:
            photo = reply.photo[-1]  # 最大尺寸
            file = await bot.get_file(photo.file_id)
            file_path = os.path.join(REPLY_IMAGE_DIR, f"{photo.file_unique_id}.jpg")
            await file.download_to_drive(file_path)
            parts.append(f"[回覆圖片: {file_path}]")
            logger.debug(f"下載回覆圖片: {file_path}")
        except Exception as e:
            logger.warning(f"下載回覆圖片失敗: {e}")
            parts.append("[回覆圖片]")
    elif reply.photo:
        parts.append("[回覆圖片]")

    # 檔案：下載可讀檔案到暫存目錄
    elif reply.document:
        file_name = reply.document.file_name or "未知檔案"
        if bot:
            try:
                from ..bot.media import is_readable_file, TEMP_FILE_DIR
                if is_readable_file(file_name):
                    file = await bot.get_file(reply.document.file_id)
                    file_path = os.path.join(TEMP_FILE_DIR, f"reply_{reply.document.file_unique_id}_{file_name}")
                    os.makedirs(TEMP_FILE_DIR, exist_ok=True)
                    await file.download_to_drive(file_path)
                    parts.append(f"[回覆檔案: {file_path}]")
                    logger.debug(f"下載回覆檔案: {file_path}")
                else:
                    parts.append(f"[回覆檔案: {file_name}（不支援讀取的格式）]")
            except Exception as e:
                logger.warning(f"下載回覆檔案失敗: {e}")
                parts.append(f"[回覆檔案: {file_name}]")
        else:
            parts.append(f"[回覆檔案: {file_name}]")

    # caption（圖片或檔案的附文）
    if reply.caption and not reply.text:
        caption = reply.caption
        if len(caption) > 500:
            caption = caption[:500] + "..."
        parts.append(f"[附文: {caption}]")

    # 文字
    if reply.text:
        text = reply.text
        if len(text) > 500:
            text = text[:500] + "..."
        parts.append(f"[回覆訊息: {text}]")

    return "\n".join(parts) + "\n" if parts else ""


async def _get_reply_context(message, bot=None) -> str:
    """取得被回覆訊息的上下文

    如果用戶回覆了一則舊訊息，查詢該訊息內容並組裝成上下文。
    支援文字、圖片和檔案訊息。
    """
    reply = message.reply_to_message
    if not reply:
        return ""

    reply_msg_id = f"tg_{reply.message_id}"

    # 查 DB 取得被回覆訊息
    try:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT m.content, m.message_type, f.nas_path, f.file_name
                FROM bot_messages m
                LEFT JOIN bot_files f ON f.message_id = m.id
                WHERE m.message_id = $1
                """,
                reply_msg_id,
            )
    except Exception as e:
        logger.error(f"查詢被回覆訊息失敗: {e}", exc_info=True)
        return ""

    if not row:
        # DB 沒有記錄，直接從 Telegram reply message 物件取得內容
        # （Bot 回覆的 message_id 與 DB 儲存的 key 格式不同，常會查不到）
        return await _extract_reply_from_message(reply, bot)

    msg_type = row["message_type"]
    content = row["content"]
    nas_path = row["nas_path"]

    if msg_type == "image" and nas_path:
        from ..bot_line import ensure_temp_image
        temp_path = await ensure_temp_image(reply_msg_id, nas_path)
        if temp_path:
            return f"[回覆圖片: {temp_path}]\n"

    if msg_type == "file" and nas_path and row["file_name"]:
        from ..bot_line import ensure_temp_file
        from ..bot.media import is_readable_file
        if is_readable_file(row["file_name"]):
            temp_path = await ensure_temp_file(
                reply_msg_id, nas_path, row["file_name"],
            )
            if temp_path:
                return f"[回覆檔案: {temp_path}]\n"

    if content:
        return f"[回覆訊息: {content}]\n"

    # DB 有記錄但沒有可用內容，嘗試從 message 物件取得
    return await _extract_reply_from_message(reply, bot)


def _prefix_user(text: str, user) -> str:
    """為文字加上 user[使用者名稱]: 前綴"""
    if user:
        display_name = user.full_name or "未知用戶"
        return f"user[{display_name}]: {text}"
    return text


def _strip_bot_mention(text: str, bot_username: str | None) -> str:
    """移除訊息中的 @Bot mention，保留實際內容"""
    if bot_username:
        # 移除 @username（不分大小寫）
        import re
        text = re.sub(rf"@{re.escape(bot_username)}\b", "", text, flags=re.IGNORECASE).strip()
    return text


async def handle_update(update: Update, adapter: TelegramBotAdapter) -> None:
    """處理 Telegram Update 事件"""
    if not update.message:
        logger.debug(f"跳過非訊息 Update: {update.update_id}")
        return

    message = update.message
    chat = message.chat
    chat_id = str(chat.id)
    chat_type = chat.type  # "private", "group", "supergroup"
    is_group = chat_type in GROUP_CHAT_TYPES

    # 確保 bot_username 已初始化（用於群組 @Bot 判斷）
    await adapter.ensure_bot_info()

    # 記錄訊息資訊
    user = message.from_user
    user_name = user.full_name if user else "未知"
    logger.info(
        f"收到 Telegram 訊息: chat_id={chat_id}, type={chat_type}, "
        f"user={user_name}, msg_type={'text' if message.text else 'other'}"
    )

    # 判斷訊息類型
    if message.photo:
        msg_type = "image"
    elif message.document:
        msg_type = "file"
    elif message.text:
        msg_type = "text"
    else:
        logger.debug(f"跳過不支援的訊息類型 (chat_id={chat_id})")
        return

    # 群組訊息：檢查是否應該回覆（僅文字和圖片需檢查 @Bot）
    if is_group and msg_type == "text":
        bot_username = adapter.bot_username
        if not _should_respond_in_group(message, bot_username):
            return

    if msg_type == "text":
        # 群組文字訊息移除 @Bot mention
        if is_group:
            text = _strip_bot_mention(message.text, adapter.bot_username)
            if not text:
                # 只有 @Bot 沒有其他內容時，讓 AI 根據對話歷史回應
                text = "（用戶呼叫了你，請根據最近的對話歷史回應）"
        else:
            text = message.text
        await _handle_text(message, text, chat_id, chat, user, is_group, adapter)
    elif msg_type in ("image", "file"):
        # 圖片和檔案：群組中需要回覆 Bot 訊息才觸發
        if is_group:
            if not (message.reply_to_message and message.reply_to_message.from_user
                    and message.reply_to_message.from_user.is_bot):
                return
        await _handle_media(message, msg_type, chat_id, chat, user, is_group, adapter)


async def _handle_text(
    message, text: str, chat_id: str, chat, user,
    is_group: bool, adapter: TelegramBotAdapter,
) -> None:
    """處理文字訊息"""
    # 確保用戶和群組存在
    bot_user_id: str | None = None
    bot_group_id: str | None = None
    try:
        async with get_connection() as conn:
            bot_user_id = await _ensure_bot_user(user, conn)
            if is_group:
                bot_group_id = await _ensure_bot_group(chat, conn)
    except Exception as e:
        logger.error(f"確保用戶/群組失敗: {e}", exc_info=True)

    # === 斜線指令攔截（統一使用 CommandRouter） ===
    from ..bot.commands import CommandContext, get_command_user_context, router as command_router

    parsed = command_router.parse(text)
    if parsed is not None:
        command, args = parsed
        ctos_user_id, is_admin = await get_command_user_context(bot_user_id)

        ctx = CommandContext(
            platform_type="telegram",
            platform_user_id=str(user.id) if user else "",
            bot_user_id=bot_user_id,
            ctos_user_id=ctos_user_id,
            is_admin=is_admin,
            is_group=is_group,
            group_id=bot_group_id,
            reply_token=None,
            raw_args=args,
        )
        reply = await command_router.dispatch(command, args, ctx)
        if reply is not None:
            await adapter.send_text(chat_id, reply)
        return

    # Telegram 專屬指令（不在 CommandRouter 中的）
    if not is_group:
        cmd = text.strip().split("@")[0]
        if cmd == "/start":
            await adapter.send_text(chat_id, START_MESSAGE)
            return
        if cmd == "/help":
            await adapter.send_text(chat_id, HELP_MESSAGE)
            return

        # 檢查是否為綁定驗證碼（6 位數字）
        if bot_user_id and await is_binding_code_format(text.strip()):
            success, msg = await verify_binding_code(bot_user_id, text.strip())
            await adapter.send_text(chat_id, msg)
            return

    # 存取控制檢查
    if bot_user_id:
        has_access, deny_reason = await check_line_access(
            bot_user_id, line_group_uuid=bot_group_id
        )
        if not has_access:
            if deny_reason == "user_not_bound":
                # 身份分流：根據策略決定拒絕或進入受限模式
                from ..bot.identity_router import (
                    route_unbound,
                    handle_restricted_mode,
                )

                route_result = route_unbound(
                    platform_type="telegram", is_group=is_group
                )
                if route_result.action == "reject":
                    if not is_group and route_result.reply_text:
                        extra = (
                            f"\n\n📋 您的 Telegram ID：{chat_id}\n"
                            "（設定 Admin Chat ID 時可使用此 ID）"
                        )
                        await adapter.send_text(
                            chat_id, route_result.reply_text + extra
                        )
                elif route_result.action == "restricted":
                    # 斜線指令已在上方 L431 由 CommandRouter 統一處理並 return，
                    # 到此處的文字一定不是已註冊指令，直接進入 AI 流程。

                    # 受限模式 AI 處理
                    try:
                        display_name = None
                        if user:
                            display_name = user.full_name or user.username

                        # 儲存訊息以取得 message_uuid（用於 AI log）
                        restricted_msg_uuid = None
                        if bot_user_id:
                            try:
                                async with get_connection() as conn:
                                    restricted_msg_uuid = await _save_message(
                                        conn,
                                        message_id=f"tg_{message.message_id}",
                                        bot_user_id=bot_user_id,
                                        bot_group_id=bot_group_id,
                                        message_type="text",
                                        content=text,
                                        is_from_bot=False,
                                    )
                            except Exception as e:
                                logger.warning(f"受限模式儲存訊息失敗: {e}")

                        reply = await handle_restricted_mode(
                            content=text,
                            platform_user_id=str(user.id) if user else chat_id,
                            bot_user_id=bot_user_id,
                            is_group=is_group,
                            line_group_id=None,
                            message_uuid=restricted_msg_uuid,
                            user_display_name=display_name,
                        )
                        if reply:
                            await adapter.send_text(chat_id, reply)
                    except Exception as e:
                        logger.error(f"受限模式 AI 處理失敗: {e}", exc_info=True)
                        await adapter.send_text(
                            chat_id, "抱歉，處理訊息時發生錯誤，請稍後再試。"
                        )
                # silent: 群組靜默忽略
            # group_not_allowed：靜默忽略
            return

    # 加上使用者名稱前綴（與 Line Bot 格式對齊）
    text = _prefix_user(text, user)

    # 取得回覆上下文
    reply_context = await _get_reply_context(message, bot=adapter.bot)
    if reply_context:
        text = reply_context + text

    # AI 對話
    try:
        await _handle_text_with_ai(
            text, chat_id, user, message.message_id,
            bot_user_id, bot_group_id, is_group, adapter,
        )
    except Exception as e:
        logger.error(f"AI 處理失敗: {e}", exc_info=True)
        await adapter.send_text(chat_id, "抱歉，處理訊息時發生錯誤，請稍後再試。")


async def _handle_media(
    message, msg_type: str, chat_id: str, chat, user,
    is_group: bool, adapter: TelegramBotAdapter,
) -> None:
    """處理圖片和檔案訊息"""
    caption = message.caption or ""

    # 確保用戶和群組存在
    bot_user_id: str | None = None
    bot_group_id: str | None = None
    try:
        async with get_connection() as conn:
            bot_user_id = await _ensure_bot_user(user, conn)
            if is_group:
                bot_group_id = await _ensure_bot_group(chat, conn)
    except Exception as e:
        logger.error(f"確保用戶/群組失敗: {e}", exc_info=True)

    # 存取控制
    if bot_user_id:
        has_access, deny_reason = await check_line_access(
            bot_user_id, line_group_uuid=bot_group_id
        )
        if not has_access:
            if deny_reason == "user_not_bound" and not is_group:
                await adapter.send_text(
                    chat_id,
                    "請先綁定帳號才能使用此功能。發送 /start 查看綁定步驟。",
                )
            return

    # 儲存訊息記錄
    message_uuid: str | None = None
    if bot_user_id:
        try:
            async with get_connection() as conn:
                message_uuid = await _save_message(
                    conn,
                    message_id=f"tg_{message.message_id}",
                    bot_user_id=bot_user_id,
                    bot_group_id=bot_group_id,
                    message_type=msg_type,
                    content=caption,
                    is_from_bot=False,
                )
        except Exception as e:
            logger.error(f"儲存媒體訊息失敗: {e}", exc_info=True)

    if not message_uuid:
        return

    # 下載並儲存到 NAS
    nas_path: str | None = None
    if msg_type == "image":
        nas_path = await download_telegram_photo(
            adapter.bot, message, message_uuid, chat_id, is_group
        )
    elif msg_type == "file":
        nas_path = await download_telegram_document(
            adapter.bot, message, message_uuid, chat_id, is_group
        )

    if not nas_path:
        await adapter.send_text(chat_id, "檔案下載失敗，請稍後再試。")
        return

    # 組裝 AI 提示
    if msg_type == "image":
        from ..bot_line import ensure_temp_image
        temp_path = await ensure_temp_image(
            f"tg_{message.message_id}", nas_path
        )
        if temp_path:
            ai_prompt = f"[上傳圖片: {temp_path}]"
            if caption:
                ai_prompt += f"\nuser: {caption}"
            else:
                ai_prompt += "\nuser: 請描述這張圖片"
        else:
            await adapter.send_text(chat_id, "圖片處理失敗。")
            return
    else:
        from ..bot_line import ensure_temp_file
        from ..bot.media import is_readable_file
        file_name = message.document.file_name or "unknown"
        if is_readable_file(file_name):
            temp_path = await ensure_temp_file(
                f"tg_{message.message_id}", nas_path, file_name,
                message.document.file_size,
            )
            if temp_path:
                ai_prompt = f"[上傳檔案: {temp_path}]"
                if caption:
                    ai_prompt += f"\nuser: {caption}"
                else:
                    ai_prompt += f"\nuser: 請閱讀並摘要這個檔案"
            else:
                await adapter.send_text(chat_id, "檔案處理失敗。")
                return
        else:
            await adapter.send_text(
                chat_id, f"已儲存檔案 {file_name}，但此格式無法由 AI 讀取。"
            )
            return

    # 加上使用者名稱前綴（與 Line Bot 格式對齊）
    ai_prompt = _prefix_user(ai_prompt, user)

    # 呼叫 AI 處理（傳入已儲存的 message_uuid，避免重複儲存）
    await _handle_text_with_ai(
        ai_prompt, chat_id, user, message.message_id,
        bot_user_id, bot_group_id, is_group, adapter,
        existing_message_uuid=message_uuid,
    )


async def _handle_text_with_ai(
    text: str,
    chat_id: str,
    user,
    message_id: int,
    bot_user_id: str | None,
    bot_group_id: str | None,
    is_group: bool,
    adapter: TelegramBotAdapter,
    existing_message_uuid: str | None = None,
) -> None:
    """透過 AI 處理文字訊息並回覆"""
    # 發送「正在輸入」提示
    try:
        await adapter.bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception as e:
        logger.debug(f"發送 typing 提示失敗: {e}")

    # 0. 儲存用戶訊息（媒體訊息已在 _handle_media 儲存，跳過）
    message_uuid: str | None = existing_message_uuid
    platform_user_id = str(user.id)
    if bot_user_id and message_uuid is None:
        try:
            async with get_connection() as conn:
                message_uuid = await _save_message(
                    conn,
                    message_id=f"tg_{message_id}",
                    bot_user_id=bot_user_id,
                    bot_group_id=bot_group_id,
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
            line_group_id=bot_group_id if is_group else None,
            line_user_id=platform_user_id if not is_group else None,
            limit=20,
            exclude_message_id=message_uuid,
        )
    except Exception as e:
        logger.error(f"取得對話歷史失敗: {e}", exc_info=True)

    # 1. 取得 Agent 設定
    agent = await get_linebot_agent(is_group=is_group)
    if not agent:
        logger.error("找不到 Agent 設定")
        await adapter.send_text(chat_id, "系統尚未設定 AI Agent，請聯繫管理員。")
        return

    # 從 Agent 取得 model 和基礎 prompt（與 Line Bot 對齊）
    model = agent.get("model", "opus").replace("claude-", "")
    system_prompt_data = agent.get("system_prompt")
    if isinstance(system_prompt_data, dict):
        base_prompt = system_prompt_data.get("content", "")
    else:
        base_prompt = ""
        if system_prompt_data is not None:
            logger.warning(f"system_prompt 不是 dict: {type(system_prompt_data)}")
    builtin_tools = agent.get("tools") or []

    if not base_prompt:
        logger.error("Agent 沒有設定 system_prompt")
        await adapter.send_text(chat_id, "⚠️ AI 設定錯誤：Agent 沒有設定 system_prompt")
        return

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
                    user_info = await get_user_role_and_permissions(row["user_id"])
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
        line_group_id=bot_group_id if is_group else None,
        line_user_id=platform_user_id,
        base_prompt=base_prompt,
        builtin_tools=builtin_tools,
        app_permissions=app_permissions,
        platform_type="telegram",
    )

    # 3. 組裝工具列表（根據用戶權限過濾）
    # 內建 MCP 工具（ching-tech-os server）
    mcp_tools = await get_mcp_tool_names(exclude_group_only=not is_group)
    mcp_tools = get_mcp_tools_for_user(user_role, user_permissions, mcp_tools)
    tool_routing = await get_tool_routing_for_user(app_permissions)
    suppressed_tools = set(tool_routing.get("suppressed_mcp_tools") or [])
    if suppressed_tools:
        mcp_tools = [tool for tool in mcp_tools if tool not in suppressed_tools]
    # 外部 MCP 工具（由 SkillManager 動態產生，含 fallback）
    skill_tools = await get_tools_for_user(app_permissions)
    all_tools = list(dict.fromkeys(builtin_tools + mcp_tools + skill_tools))

    # 取得需要的 MCP server 集合（按需載入）
    required_mcp_servers = await get_mcp_servers_for_user(app_permissions)

    # 4. 建立進度通知 callback（含節流避免 Telegram API 限流）
    progress_message_id: str | None = None
    tool_status_lines: list[dict] = []
    last_update_ts: float = 0.0
    THROTTLE_INTERVAL = 1.0  # 至少間隔 1 秒才更新訊息

    async def _send_or_update_progress() -> None:
        """送出或更新進度訊息（含節流）"""
        nonlocal progress_message_id, last_update_ts
        now = time.time()
        full_text = "🤖 AI 處理中\n\n" + "\n\n".join(t["line"] for t in tool_status_lines)

        if progress_message_id is None:
            sent = await adapter.send_progress(chat_id, full_text)
            progress_message_id = sent.message_id
            last_update_ts = now
        elif now - last_update_ts >= THROTTLE_INTERVAL:
            await adapter.update_progress(chat_id, progress_message_id, full_text)
            last_update_ts = now

    async def _on_tool_start(tool_name: str, tool_input: dict) -> None:
        """Tool 開始執行時的回調：送出或更新進度通知"""
        try:
            # 格式化輸入參數（簡短顯示）
            input_str = ""
            if tool_input:
                items = list(tool_input.items())[:2]
                input_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in items)
                if len(tool_input) > 2:
                    input_str += ", ..."

            status_line = f"🔧 {tool_name}"
            if input_str:
                status_line += f"\n   └ {input_str}"
            status_line += "\n   ⏳ 執行中..."

            tool_status_lines.append({"name": tool_name, "status": "running", "line": status_line})
            await _send_or_update_progress()
        except Exception as e:
            logger.debug(f"進度通知（tool_start）失敗: {e}")

    async def _on_tool_end(tool_name: str, result: dict) -> None:
        """Tool 執行完成時的回調：更新進度通知"""
        try:
            duration_ms_val = result.get("duration_ms")
            if duration_ms_val is not None:
                duration_str = f"{duration_ms_val}ms" if duration_ms_val < 1000 else f"{duration_ms_val / 1000:.1f}s"
            else:
                duration_str = "完成"

            # 更新對應 tool 的狀態（找最後一個同名且 running 的）
            for tool in reversed(tool_status_lines):
                if tool["name"] == tool_name and tool["status"] == "running":
                    tool["status"] = "done"
                    tool["line"] = tool["line"].replace("⏳ 執行中...", f"✅ 完成 ({duration_str})")
                    break

            await _send_or_update_progress()
        except Exception as e:
            logger.debug(f"進度通知（tool_end）失敗: {e}")

    # 呼叫 AI（含對話歷史和進度通知）
    context_type = "telegram-group" if is_group else "telegram-personal"
    start_time = time.time()
    response = await call_claude(
        prompt=text,
        model=model,
        history=history,
        system_prompt=system_prompt,
        timeout=480,
        tools=all_tools,
        on_tool_start=_on_tool_start,
        on_tool_end=_on_tool_end,
        required_mcp_servers=required_mcp_servers,
    )
    duration_ms = int((time.time() - start_time) * 1000)

    # 刪除進度通知訊息
    if progress_message_id:
        try:
            await adapter.finish_progress(chat_id, progress_message_id)
        except Exception as e:
            logger.debug(f"刪除進度通知失敗: {e}")

    # 4.5 記錄 AI Log
    if message_uuid:
        try:
            await log_linebot_ai_call(
                message_uuid=message_uuid,
                line_group_id=bot_group_id,
                is_group=is_group,
                input_prompt=text,
                history=history,
                system_prompt=system_prompt,
                allowed_tools=all_tools,
                model=model,
                response=response,
                duration_ms=duration_ms,
                context_type_override=context_type,
                tool_routing=tool_routing,
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

    # 7. 發送回覆（文字失敗不影響後續圖片/檔案發送）
    if reply_text:
        try:
            await adapter.send_text(chat_id, reply_text)
        except Exception as e:
            logger.warning(f"發送文字回覆失敗: {e}")

    sent_file_msg_ids: list[tuple[int, dict]] = []  # (telegram_message_id, file_info)
    for file_info in files:
        file_type = file_info.get("type", "")
        url = file_info.get("url", "")
        if not url:
            continue
        try:
            if file_type == "image":
                sent_msg = await adapter.send_image(chat_id, url)
                sent_file_msg_ids.append((int(sent_msg.message_id), file_info))
            else:
                # 優先使用 download_url（直接下載連結），避免拿到分享頁面 HTML
                file_download_url = file_info.get("download_url") or url
                await adapter.send_file(
                    chat_id, file_download_url, file_info.get("name", "file")
                )
                # 附上分享連結（url 是分享頁面，方便用戶在瀏覽器開啟）
                share_url = file_info.get("url", "")
                if share_url and share_url != file_download_url:
                    file_name = file_info.get("name", "檔案")
                    file_size = file_info.get("size", "")
                    size_text = f"（{file_size}）" if file_size else ""
                    await adapter.send_text(
                        chat_id,
                        f"📎 {file_name}{size_text}\n🔗 {share_url}\n⏰ 連結 24 小時內有效",
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
                # 儲存文字回覆
                reply_msg_uuid = await _save_message(
                    conn,
                    message_id=f"tg_reply_{message_id}",
                    bot_user_id=bot_user_id,
                    bot_group_id=bot_group_id,
                    message_type="text",
                    content=reply_text or "",
                    is_from_bot=True,
                )

                # 儲存圖片檔案記錄（用 Telegram 回傳的 message_id，讓回覆時能查到）
                for sent_tg_msg_id, img_info in sent_file_msg_ids:
                    nas_path = img_info.get("nas_path")
                    file_name = img_info.get("name", "image")
                    if nas_path:
                        try:
                            img_msg_uuid = await _save_message(
                                conn,
                                message_id=f"tg_{sent_tg_msg_id}",
                                bot_user_id=bot_user_id,
                                bot_group_id=bot_group_id,
                                message_type="image",
                                content=f"[Bot 發送的圖片: {file_name}]",
                                is_from_bot=True,
                            )
                            await save_file_record(
                                message_uuid=img_msg_uuid,
                                file_type="image",
                                file_name=file_name,
                                nas_path=nas_path,
                            )
                            logger.info(f"已儲存 Telegram Bot 圖片記錄: tg_{sent_tg_msg_id} -> {file_name}")
                        except Exception as e:
                            logger.error(f"儲存圖片記錄失敗: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"儲存 Bot 回覆失敗: {e}", exc_info=True)
