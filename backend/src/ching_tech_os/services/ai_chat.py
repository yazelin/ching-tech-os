"""AI 對話 CRUD 服務"""

import json
import time
from uuid import UUID

from ..database import get_connection


# ============================================================
# Agent/Prompt 查詢（使用資料庫）
# ============================================================


async def get_available_agents() -> list[dict]:
    """取得可用的 Agent 列表（從資料庫）"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, display_name, description, model, is_active
            FROM ai_agents
            WHERE is_active = true
            ORDER BY name
            """
        )
        return [dict(row) for row in rows]


async def get_agent_system_prompt(agent_name: str) -> str | None:
    """取得 Agent 的 system prompt 內容

    Args:
        agent_name: Agent 名稱

    Returns:
        System prompt 內容，若 Agent 不存在或無設定 prompt 則返回 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT p.content
            FROM ai_agents a
            LEFT JOIN ai_prompts p ON a.system_prompt_id = p.id
            WHERE a.name = $1 AND a.is_active = true
            """,
            agent_name,
        )
        if row is None:
            return None
        return row["content"]


async def get_agent_config(agent_name: str) -> dict | None:
    """取得 Agent 設定（model、system_prompt、tools 等）

    Args:
        agent_name: Agent 名稱

    Returns:
        Agent 設定 dict，若不存在則返回 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT a.id, a.name, a.display_name, a.model, a.is_active, a.tools, a.settings,
                   p.content as system_prompt
            FROM ai_agents a
            LEFT JOIN ai_prompts p ON a.system_prompt_id = p.id
            WHERE a.name = $1
            """,
            agent_name,
        )
        if row is None:
            return None
        result = dict(row)
        if result.get("settings"):
            result["settings"] = json.loads(result["settings"])
        if result.get("tools"):
            result["tools"] = json.loads(result["tools"]) if isinstance(result["tools"], str) else result["tools"]
        return result


# ============================================================
# Chat CRUD 操作
# ============================================================


async def get_user_chats(user_id: int) -> list[dict]:
    """取得使用者的對話列表（不含 messages）"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, title, model, prompt_name, created_at, updated_at
            FROM ai_chats
            WHERE user_id = $1
            ORDER BY updated_at DESC
            """,
            user_id,
        )
        return [dict(row) for row in rows]


async def create_chat(
    user_id: int,
    title: str = "新對話",
    model: str = "claude-sonnet",
    prompt_name: str = "default",
) -> dict:
    """建立新對話"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ai_chats (user_id, title, model, prompt_name, messages)
            VALUES ($1, $2, $3, $4, '[]'::jsonb)
            RETURNING id, user_id, title, model, prompt_name, messages, created_at, updated_at
            """,
            user_id,
            title,
            model,
            prompt_name,
        )
        result = dict(row)
        # Parse JSONB messages
        result["messages"] = json.loads(result["messages"])
        return result


async def get_chat(chat_id: UUID, user_id: int | None = None) -> dict | None:
    """取得對話詳情（含 messages）"""
    async with get_connection() as conn:
        if user_id is not None:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, title, model, prompt_name, messages, created_at, updated_at
                FROM ai_chats
                WHERE id = $1 AND user_id = $2
                """,
                chat_id,
                user_id,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, title, model, prompt_name, messages, created_at, updated_at
                FROM ai_chats
                WHERE id = $1
                """,
                chat_id,
            )
        if row is None:
            return None
        result = dict(row)
        # Parse JSONB messages
        result["messages"] = json.loads(result["messages"])
        return result


async def delete_chat(chat_id: UUID, user_id: int) -> bool:
    """刪除對話"""
    async with get_connection() as conn:
        result = await conn.execute(
            """
            DELETE FROM ai_chats
            WHERE id = $1 AND user_id = $2
            """,
            chat_id,
            user_id,
        )
        return result == "DELETE 1"


async def update_chat(
    chat_id: UUID,
    user_id: int,
    title: str | None = None,
    model: str | None = None,
    prompt_name: str | None = None,
) -> dict | None:
    """更新對話（標題、模型等）"""
    updates = []
    params = []
    param_idx = 1

    if title is not None:
        updates.append(f"title = ${param_idx}")
        params.append(title)
        param_idx += 1

    if model is not None:
        updates.append(f"model = ${param_idx}")
        params.append(model)
        param_idx += 1

    if prompt_name is not None:
        updates.append(f"prompt_name = ${param_idx}")
        params.append(prompt_name)
        param_idx += 1

    if not updates:
        return await get_chat(chat_id, user_id)

    updates.append("updated_at = NOW()")
    params.extend([chat_id, user_id])

    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE ai_chats
            SET {", ".join(updates)}
            WHERE id = ${param_idx} AND user_id = ${param_idx + 1}
            RETURNING id, user_id, title, model, prompt_name, messages, created_at, updated_at
            """,
            *params,
        )
        if row is None:
            return None
        result = dict(row)
        result["messages"] = json.loads(result["messages"])
        return result


async def update_chat_messages(
    chat_id: UUID, messages: list[dict], user_id: int | None = None
) -> dict | None:
    """更新對話訊息"""
    messages_json = json.dumps(messages, ensure_ascii=False)

    async with get_connection() as conn:
        if user_id is not None:
            row = await conn.fetchrow(
                """
                UPDATE ai_chats
                SET messages = $1::jsonb, updated_at = NOW()
                WHERE id = $2 AND user_id = $3
                RETURNING id, user_id, title, model, prompt_name, messages, created_at, updated_at
                """,
                messages_json,
                chat_id,
                user_id,
            )
        else:
            row = await conn.fetchrow(
                """
                UPDATE ai_chats
                SET messages = $1::jsonb, updated_at = NOW()
                WHERE id = $2
                RETURNING id, user_id, title, model, prompt_name, messages, created_at, updated_at
                """,
                messages_json,
                chat_id,
            )
        if row is None:
            return None
        result = dict(row)
        result["messages"] = json.loads(result["messages"])
        return result


async def append_message(
    chat_id: UUID, role: str, content: str, user_id: int | None = None
) -> dict | None:
    """新增一則訊息到對話"""
    chat = await get_chat(chat_id, user_id)
    if chat is None:
        return None

    messages = chat["messages"]
    messages.append(
        {
            "role": role,
            "content": content,
            "timestamp": int(time.time()),
        }
    )

    return await update_chat_messages(chat_id, messages, user_id)


async def update_chat_title(chat_id: UUID, title: str, user_id: int | None = None) -> bool:
    """更新對話標題"""
    async with get_connection() as conn:
        if user_id is not None:
            result = await conn.execute(
                """
                UPDATE ai_chats
                SET title = $1, updated_at = NOW()
                WHERE id = $2 AND user_id = $3
                """,
                title,
                chat_id,
                user_id,
            )
        else:
            result = await conn.execute(
                """
                UPDATE ai_chats
                SET title = $1, updated_at = NOW()
                WHERE id = $2
                """,
                title,
                chat_id,
            )
        return "UPDATE 1" in result
