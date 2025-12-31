"""Line Bot AI 處理服務

使用 Claude CLI 處理 Line 訊息（與 AI 助手相同架構）
整合 AI Log 記錄功能
"""

import logging
import time
from uuid import UUID

from .claude_agent import call_claude
from .linebot import (
    reply_text,
    mark_message_ai_processed,
    should_trigger_ai,
    save_bot_response,
    reset_conversation,
    is_reset_command,
    ensure_temp_image,
    get_image_info_by_line_message_id,
    get_temp_image_path,
)
from . import ai_manager
from .linebot_agents import get_linebot_agent, AGENT_LINEBOT_PERSONAL, AGENT_LINEBOT_GROUP
from ..database import get_connection
from ..models.ai import AiLogCreate

logger = logging.getLogger("linebot_ai")


# ============================================================
# AI 處理主流程
# ============================================================


async def process_message_with_ai(
    message_uuid: UUID,
    content: str,
    line_group_id: UUID | None,
    line_user_id: str | None,
    reply_token: str | None,
    user_display_name: str | None = None,
    quoted_message_id: str | None = None,
) -> str | None:
    """
    使用 AI 處理訊息

    Args:
        message_uuid: 訊息的內部 UUID
        content: 訊息內容
        line_group_id: 群組 UUID（個人對話為 None）
        line_user_id: Line 用戶 ID（個人對話用）
        reply_token: Line 回覆 token（可能已過期）
        user_display_name: 發送者顯示名稱
        quoted_message_id: 被回覆的訊息 ID（Line 的 quotedMessageId）

    Returns:
        AI 回應文字，或 None（如果不需處理）
    """
    is_group = line_group_id is not None

    # 檢查是否為重置對話指令（僅限個人對話）
    if is_reset_command(content):
        if is_group:
            # 群組不支援重置，靜默忽略
            return None
        elif line_user_id:
            # 個人對話：執行重置
            await reset_conversation(line_user_id)
            reset_msg = "已清除對話歷史，開始新對話！有什麼可以幫你的嗎？"
            # 儲存 Bot 回應
            await save_bot_response(
                group_uuid=None,
                content=reset_msg,
                responding_to_line_user_id=line_user_id,
            )
            # 回覆訊息
            if reply_token:
                try:
                    await reply_text(reply_token, reset_msg)
                except Exception as e:
                    logger.warning(f"回覆重置訊息失敗: {e}")
            return reset_msg
        return None

    # 檢查是否應該觸發 AI
    should_trigger = should_trigger_ai(content, is_group)
    logger.info(f"AI 觸發判斷: is_group={is_group}, content={content[:50]!r}, should_trigger={should_trigger}")

    if not should_trigger:
        logger.debug(f"訊息不觸發 AI: {content[:50]}...")
        return None

    try:
        # 取得 Agent 設定
        agent = await get_linebot_agent(is_group)
        agent_name = AGENT_LINEBOT_GROUP if is_group else AGENT_LINEBOT_PERSONAL

        if not agent:
            error_msg = f"⚠️ AI 設定錯誤：Agent '{agent_name}' 不存在"
            logger.error(error_msg)
            if reply_token:
                await reply_text(reply_token, error_msg)
            return error_msg

        # 從 Agent 取得 model 和基礎 prompt
        model = agent["model"].replace("claude-", "")  # claude-sonnet -> sonnet
        base_prompt = agent.get("system_prompt", {}).get("content", "")
        # 從 Agent 取得內建工具權限（如 WebSearch, WebFetch）
        agent_tools = agent.get("tools") or []
        logger.info(f"使用 Agent '{agent_name}' 設定，內建工具: {agent_tools}")

        if not base_prompt:
            error_msg = f"⚠️ AI 設定錯誤：Agent '{agent_name}' 沒有設定 system_prompt"
            logger.error(error_msg)
            if reply_token:
                await reply_text(reply_token, error_msg)
            return error_msg

        # 建立系統提示（加入群組資訊）
        system_prompt = await build_system_prompt(line_group_id, base_prompt)

        # 取得對話歷史（20 則提供更好的上下文理解，包含圖片）
        history, images = await get_conversation_context(line_group_id, line_user_id, limit=20)

        # 處理回覆舊圖片（quotedMessageId）
        quoted_image_path = None
        if quoted_message_id:
            image_info = await get_image_info_by_line_message_id(quoted_message_id)
            if image_info and image_info.get("nas_path"):
                # 確保圖片暫存存在
                temp_path = await ensure_temp_image(quoted_message_id, image_info["nas_path"])
                if temp_path:
                    quoted_image_path = temp_path
                    logger.info(f"用戶回覆圖片: {quoted_message_id} -> {temp_path}")

        # 確保對話歷史中的圖片暫存存在
        for img in images:
            await ensure_temp_image(img["line_message_id"], img["nas_path"])

        # 準備用戶訊息
        user_message = content
        if user_display_name:
            user_message = f"{user_display_name}: {content}"

        # 如果是回覆圖片，在訊息開頭標註
        if quoted_image_path:
            user_message = f"[回覆圖片: {quoted_image_path}]\n{user_message}"

        # MCP 工具列表（固定）
        mcp_tools = [
            "mcp__ching-tech-os__query_project",
            "mcp__ching-tech-os__get_project_milestones",
            "mcp__ching-tech-os__get_project_meetings",
            "mcp__ching-tech-os__get_project_members",
            "mcp__ching-tech-os__summarize_chat",
            "mcp__ching-tech-os__search_knowledge",
            "mcp__ching-tech-os__get_knowledge_item",
            "mcp__ching-tech-os__update_knowledge_item",
            "mcp__ching-tech-os__delete_knowledge_item",
            "mcp__ching-tech-os__add_note",
        ]

        # 合併內建工具（從 Agent 設定）、MCP 工具和 Read（用於讀取圖片）
        all_tools = agent_tools + mcp_tools + ["Read"]

        # 計時開始
        start_time = time.time()

        # 呼叫 Claude CLI
        response = await call_claude(
            prompt=user_message,
            model=model,
            history=history,
            system_prompt=system_prompt,
            timeout=90,  # MCP 工具可能需要較長時間
            tools=all_tools,
        )

        # 計算耗時
        duration_ms = int((time.time() - start_time) * 1000)

        # 記錄 AI Log
        await log_linebot_ai_call(
            message_uuid=message_uuid,
            line_group_id=line_group_id,
            is_group=is_group,
            input_prompt=user_message,
            system_prompt=system_prompt,
            model=model,
            response=response,
            duration_ms=duration_ms,
        )

        if not response.success:
            logger.error(f"Claude CLI 失敗: {response.error}")
            return None

        ai_response = response.message

        # 標記訊息已處理
        await mark_message_ai_processed(message_uuid)

        # 儲存 Bot 回應到資料庫
        if ai_response:
            await save_bot_response(
                group_uuid=line_group_id,
                content=ai_response,
                responding_to_line_user_id=line_user_id if not is_group else None,
            )

        # 回覆訊息（如果有 reply_token）
        if reply_token and ai_response:
            try:
                await reply_text(reply_token, ai_response)
            except Exception as e:
                logger.warning(f"回覆訊息失敗（token 可能已過期）: {e}")

        return ai_response

    except Exception as e:
        logger.error(f"AI 處理訊息失敗: {e}")
        return None


async def log_linebot_ai_call(
    message_uuid: UUID,
    line_group_id: UUID | None,
    is_group: bool,
    input_prompt: str,
    system_prompt: str,
    model: str,
    response,
    duration_ms: int,
) -> None:
    """
    記錄 Line Bot AI 調用到 AI Log

    Args:
        message_uuid: 訊息 UUID
        line_group_id: 群組 UUID
        is_group: 是否為群組對話
        input_prompt: 輸入的 prompt
        system_prompt: 系統提示
        model: 使用的模型
        response: Claude 回應物件
        duration_ms: 耗時（毫秒）
    """
    try:
        # 根據對話類型取得對應的 Agent
        agent_name = AGENT_LINEBOT_GROUP if is_group else AGENT_LINEBOT_PERSONAL
        agent = await ai_manager.get_agent_by_name(agent_name)
        agent_id = agent["id"] if agent else None
        prompt_id = agent.get("system_prompt", {}).get("id") if agent else None

        # 建立 Log
        log_data = AiLogCreate(
            agent_id=agent_id,
            prompt_id=prompt_id,
            context_type="linebot-group" if is_group else "linebot-personal",
            context_id=str(message_uuid),
            input_prompt=input_prompt,
            system_prompt=system_prompt,
            raw_response=response.message if response.success else None,
            model=model,
            success=response.success,
            error_message=response.error if not response.success else None,
            duration_ms=duration_ms,
        )

        await ai_manager.create_log(log_data)
        logger.debug(f"已記錄 AI Log: agent={agent_name}, message_uuid={message_uuid}, success={response.success}")

    except Exception as e:
        # Log 記錄失敗不影響主流程
        logger.warning(f"記錄 AI Log 失敗: {e}")


async def get_conversation_context(
    line_group_id: UUID | None,
    line_user_id: str | None,
    limit: int = 20,
) -> tuple[list[dict], list[dict]]:
    """
    取得對話上下文（包含圖片訊息）

    Args:
        line_group_id: 群組 UUID（None 表示個人對話）
        line_user_id: Line 用戶 ID（個人對話用）
        limit: 取得的訊息數量

    Returns:
        (context, images) tuple:
        - context: 訊息列表 [{"role": "user/assistant", "content": "..."}]
        - images: 圖片資訊列表 [{"line_message_id": "...", "nas_path": "..."}]
    """
    from .linebot import get_temp_image_path

    async with get_connection() as conn:
        if line_group_id:
            # 群組對話（包含 text 和 image）
            rows = await conn.fetch(
                """
                SELECT m.content, m.is_from_bot, u.display_name,
                       m.message_type, m.message_id as line_message_id, f.nas_path
                FROM line_messages m
                LEFT JOIN line_users u ON m.line_user_id = u.id
                LEFT JOIN line_files f ON f.message_id = m.id AND f.file_type = 'image'
                WHERE m.line_group_id = $1
                  AND m.message_type IN ('text', 'image')
                  AND (m.content IS NOT NULL OR m.message_type = 'image')
                ORDER BY m.created_at DESC
                LIMIT $2
                """,
                line_group_id,
                limit,
            )
        elif line_user_id:
            # 個人對話：查詢該用戶的對話歷史，考慮對話重置時間
            rows = await conn.fetch(
                """
                SELECT m.content, m.is_from_bot, u.display_name,
                       m.message_type, m.message_id as line_message_id, f.nas_path
                FROM line_messages m
                LEFT JOIN line_users u ON m.line_user_id = u.id
                LEFT JOIN line_files f ON f.message_id = m.id AND f.file_type = 'image'
                WHERE u.line_user_id = $1
                  AND m.line_group_id IS NULL
                  AND m.message_type IN ('text', 'image')
                  AND (m.content IS NOT NULL OR m.message_type = 'image')
                  AND (
                    u.conversation_reset_at IS NULL
                    OR m.created_at > u.conversation_reset_at
                  )
                ORDER BY m.created_at DESC
                LIMIT $2
                """,
                line_user_id,
                limit,
            )
        else:
            return [], []

        # 反轉順序（從舊到新）
        rows = list(reversed(rows))

        # 找出最新的圖片訊息 ID（用於標記）
        latest_image_id = None
        for row in reversed(rows):  # 從新到舊找第一張有 nas_path 的圖片
            if row["message_type"] == "image" and row["nas_path"]:
                latest_image_id = row["line_message_id"]
                break

        context = []
        images = []

        for row in rows:
            role = "assistant" if row["is_from_bot"] else "user"

            if row["message_type"] == "image" and row["nas_path"]:
                # 圖片訊息：格式化為特殊標記
                temp_path = get_temp_image_path(row["line_message_id"])
                # 標記最新的圖片
                if row["line_message_id"] == latest_image_id:
                    content = f"[上傳圖片（最近）: {temp_path}]"
                else:
                    content = f"[上傳圖片: {temp_path}]"
                # 記錄圖片資訊供後續載入
                images.append({
                    "line_message_id": row["line_message_id"],
                    "nas_path": row["nas_path"],
                })
            else:
                content = row["content"]

            # 群組對話才加發送者名稱，個人對話不需要
            if line_group_id and not row["is_from_bot"] and row["display_name"]:
                content = f"{row['display_name']}: {content}"

            context.append({"role": role, "content": content})

        return context, images


async def build_system_prompt(line_group_id: UUID | None, base_prompt: str) -> str:
    """
    建立系統提示

    Args:
        line_group_id: 群組 UUID
        base_prompt: 從 Agent 取得的基礎 prompt

    Returns:
        系統提示文字
    """

    # 如果是群組，加入群組資訊
    if line_group_id:
        async with get_connection() as conn:
            group = await conn.fetchrow(
                """
                SELECT g.name, g.project_id, p.name as project_name
                FROM line_groups g
                LEFT JOIN projects p ON g.project_id = p.id
                WHERE g.id = $1
                """,
                line_group_id,
            )
            if group:
                base_prompt += f"\n\n目前群組：{group['name'] or '未命名群組'}"
                if group["project_name"]:
                    base_prompt += f"\n綁定專案：{group['project_name']}"
                    base_prompt += f"\n專案 ID（供工具查詢用）：{group['project_id']}"

    return base_prompt


# ============================================================
# Webhook 處理入口
# ============================================================


async def handle_text_message(
    message_id: str,
    message_uuid: UUID,
    content: str,
    line_user_id: str,
    line_group_id: UUID | None,
    reply_token: str | None,
    quoted_message_id: str | None = None,
) -> None:
    """
    處理文字訊息的 Webhook 入口

    Args:
        message_id: Line 訊息 ID
        message_uuid: 內部訊息 UUID
        content: 訊息內容
        line_user_id: Line 用戶 ID
        line_group_id: 內部群組 UUID（個人對話為 None）
        reply_token: Line 回覆 token
        quoted_message_id: 被回覆的訊息 ID（用戶回覆舊訊息時）
    """
    # 取得用戶顯示名稱
    user_display_name = None
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT display_name FROM line_users WHERE line_user_id = $1",
            line_user_id,
        )
        if row:
            user_display_name = row["display_name"]

    # 處理訊息
    await process_message_with_ai(
        message_uuid=message_uuid,
        content=content,
        line_group_id=line_group_id,
        line_user_id=line_user_id,
        reply_token=reply_token,
        user_display_name=user_display_name,
        quoted_message_id=quoted_message_id,
    )
