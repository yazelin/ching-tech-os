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
)
from . import ai_manager
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
    reply_token: str | None,
    user_display_name: str | None = None,
) -> str | None:
    """
    使用 AI 處理訊息

    Args:
        message_uuid: 訊息的內部 UUID
        content: 訊息內容
        line_group_id: 群組 UUID（個人對話為 None）
        reply_token: Line 回覆 token（可能已過期）
        user_display_name: 發送者顯示名稱

    Returns:
        AI 回應文字，或 None（如果不需處理）
    """
    is_group = line_group_id is not None

    # 檢查是否應該觸發 AI
    should_trigger = should_trigger_ai(content, is_group)
    logger.info(f"AI 觸發判斷: is_group={is_group}, content={content[:50]!r}, should_trigger={should_trigger}")

    if not should_trigger:
        logger.debug(f"訊息不觸發 AI: {content[:50]}...")
        return None

    try:
        # 取得對話歷史
        history = await get_conversation_context(line_group_id, limit=10)

        # 建立系統提示
        system_prompt = await build_system_prompt(line_group_id)

        # 準備用戶訊息
        user_message = content
        if user_display_name:
            user_message = f"{user_display_name}: {content}"

        # MCP 工具列表
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

        # 計時開始
        start_time = time.time()

        # 呼叫 Claude CLI
        response = await call_claude(
            prompt=user_message,
            model="sonnet",
            history=history,
            system_prompt=system_prompt,
            timeout=90,  # MCP 工具可能需要較長時間
            tools=mcp_tools,
        )

        # 計算耗時
        duration_ms = int((time.time() - start_time) * 1000)

        # 記錄 AI Log
        await log_linebot_ai_call(
            message_uuid=message_uuid,
            line_group_id=line_group_id,
            input_prompt=user_message,
            system_prompt=system_prompt,
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
    input_prompt: str,
    system_prompt: str,
    response,
    duration_ms: int,
) -> None:
    """
    記錄 Line Bot AI 調用到 AI Log

    Args:
        message_uuid: 訊息 UUID
        line_group_id: 群組 UUID
        input_prompt: 輸入的 prompt
        system_prompt: 系統提示
        response: Claude 回應物件
        duration_ms: 耗時（毫秒）
    """
    try:
        # 取得 linebot Agent ID（如果有設定的話）
        agent = await ai_manager.get_agent_by_name("linebot")
        agent_id = agent["id"] if agent else None
        prompt_id = agent.get("system_prompt", {}).get("id") if agent else None

        # 建立 Log
        log_data = AiLogCreate(
            agent_id=agent_id,
            prompt_id=prompt_id,
            context_type="linebot",
            context_id=str(message_uuid),
            input_prompt=input_prompt,
            system_prompt=system_prompt,
            raw_response=response.message if response.success else None,
            model="sonnet",
            success=response.success,
            error_message=response.error if not response.success else None,
            duration_ms=duration_ms,
        )

        await ai_manager.create_log(log_data)
        logger.debug(f"已記錄 AI Log: message_uuid={message_uuid}, success={response.success}")

    except Exception as e:
        # Log 記錄失敗不影響主流程
        logger.warning(f"記錄 AI Log 失敗: {e}")


async def get_conversation_context(
    line_group_id: UUID | None,
    limit: int = 10,
) -> list[dict]:
    """
    取得對話上下文

    Args:
        line_group_id: 群組 UUID（None 表示個人對話）
        limit: 取得的訊息數量

    Returns:
        訊息列表 [{"role": "user/assistant", "content": "..."}]
    """
    async with get_connection() as conn:
        if line_group_id:
            # 群組對話
            rows = await conn.fetch(
                """
                SELECT m.content, m.is_from_bot, u.display_name
                FROM line_messages m
                LEFT JOIN line_users u ON m.line_user_id = u.id
                WHERE m.line_group_id = $1
                  AND m.message_type = 'text'
                  AND m.content IS NOT NULL
                ORDER BY m.created_at DESC
                LIMIT $2
                """,
                line_group_id,
                limit,
            )
        else:
            # 個人對話（目前簡化處理）
            return []

        # 反轉順序（從舊到新）
        rows = list(reversed(rows))

        context = []
        for row in rows:
            role = "assistant" if row["is_from_bot"] else "user"
            content = row["content"]
            if not row["is_from_bot"] and row["display_name"]:
                content = f"{row['display_name']}: {content}"
            context.append({"role": role, "content": content})

        return context


async def build_system_prompt(line_group_id: UUID | None) -> str:
    """
    建立系統提示

    Args:
        line_group_id: 群組 UUID

    Returns:
        系統提示文字
    """
    base_prompt = """你是擎添科技的 AI 助理，透過 Line 與用戶互動。

你可以使用以下工具：

【專案查詢】
- query_project: 查詢專案（可用關鍵字搜尋，取得專案 ID）
- get_project_milestones: 取得專案里程碑（需要 project_id）
- get_project_meetings: 取得專案會議記錄（需要 project_id）
- get_project_members: 取得專案成員與聯絡人（需要 project_id）
- summarize_chat: 取得群組聊天記錄（需要 line_group_id）

【知識庫】
- search_knowledge: 搜尋知識庫（輸入關鍵字，回傳標題列表）
- get_knowledge_item: 取得知識庫文件完整內容（輸入 kb_id，如 kb-001）
- update_knowledge_item: 更新知識庫文件（可更新標題、內容、分類、標籤）
- delete_knowledge_item: 刪除知識庫文件
- add_note: 新增筆記到知識庫（輸入標題和內容）

使用工具的流程：
1. 如果下方有提供「專案 ID」，直接使用該 ID 查詢
2. 如果沒有專案 ID，先用 query_project 搜尋專案名稱取得 ID
3. 查詢知識庫時，先用 search_knowledge 找到文件 ID，再用 get_knowledge_item 取得完整內容
4. 用戶要求「記住」或「記錄」某事時，使用 add_note 新增筆記
5. 用戶要求修改或更新知識時，使用 update_knowledge_item
6. 用戶要求刪除知識時，使用 delete_knowledge_item

回應原則：
- 使用繁體中文
- 保持簡潔（Line 訊息不宜過長）
- 善用工具查詢資訊，主動提供有用的資料
- 回覆用戶時不要顯示 UUID，只顯示名稱"""

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
        reply_token=reply_token,
        user_display_name=user_display_name,
    )
