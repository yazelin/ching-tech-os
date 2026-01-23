"""AI 對話 CRUD 服務"""

import json
import time
from uuid import UUID

from ..config import settings
from ..database import get_connection


def _get_tenant_id(tenant_id: UUID | str | None) -> UUID:
    """處理 tenant_id 參數"""
    if tenant_id is None:
        return UUID(settings.default_tenant_id)
    if isinstance(tenant_id, str):
        return UUID(tenant_id)
    return tenant_id


# ============================================================
# Agent/Prompt 查詢（使用資料庫）
# ============================================================


async def get_available_agents(tenant_id: UUID | str | None = None) -> list[dict]:
    """取得可用的 Agent 列表（從資料庫）"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, display_name, description, model, is_active
            FROM ai_agents
            WHERE is_active = true AND tenant_id = $1
            ORDER BY name
            """,
            tid,
        )
        return [dict(row) for row in rows]


async def get_agent_system_prompt(agent_name: str, tenant_id: UUID | str | None = None) -> str | None:
    """取得 Agent 的 system prompt 內容

    Args:
        agent_name: Agent 名稱
        tenant_id: 租戶 ID

    Returns:
        System prompt 內容，若 Agent 不存在或無設定 prompt 則返回 None
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT p.content
            FROM ai_agents a
            LEFT JOIN ai_prompts p ON a.system_prompt_id = p.id
            WHERE a.name = $1 AND a.is_active = true AND a.tenant_id = $2
            """,
            agent_name,
            tid,
        )
        if row is None:
            return None
        return row["content"]


async def get_agent_config(agent_name: str, tenant_id: UUID | str | None = None) -> dict | None:
    """取得 Agent 設定（model、system_prompt、tools 等）

    Args:
        agent_name: Agent 名稱
        tenant_id: 租戶 ID

    Returns:
        Agent 設定 dict，若不存在則返回 None
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT a.id, a.name, a.display_name, a.model, a.is_active, a.tools, a.settings,
                   p.content as system_prompt
            FROM ai_agents a
            LEFT JOIN ai_prompts p ON a.system_prompt_id = p.id
            WHERE a.name = $1 AND a.tenant_id = $2
            """,
            agent_name,
            tid,
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


async def get_user_chats(user_id: int, tenant_id: UUID | str | None = None) -> list[dict]:
    """取得使用者的對話列表（不含 messages）"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, title, model, prompt_name, created_at, updated_at
            FROM ai_chats
            WHERE user_id = $1 AND tenant_id = $2
            ORDER BY updated_at DESC
            """,
            user_id,
            tid,
        )
        return [dict(row) for row in rows]


async def create_chat(
    user_id: int,
    title: str = "新對話",
    model: str = "claude-sonnet",
    prompt_name: str = "default",
    tenant_id: UUID | str | None = None,
) -> dict:
    """建立新對話"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ai_chats (user_id, title, model, prompt_name, messages, tenant_id)
            VALUES ($1, $2, $3, $4, '[]'::jsonb, $5)
            RETURNING id, user_id, title, model, prompt_name, messages, created_at, updated_at
            """,
            user_id,
            title,
            model,
            prompt_name,
            tid,
        )
        result = dict(row)
        # Parse JSONB messages
        result["messages"] = json.loads(result["messages"])
        return result


async def get_chat(chat_id: UUID, user_id: int | None = None, tenant_id: UUID | str | None = None) -> dict | None:
    """取得對話詳情（含 messages）"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        if user_id is not None:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, title, model, prompt_name, messages, created_at, updated_at
                FROM ai_chats
                WHERE id = $1 AND user_id = $2 AND tenant_id = $3
                """,
                chat_id,
                user_id,
                tid,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, title, model, prompt_name, messages, created_at, updated_at
                FROM ai_chats
                WHERE id = $1 AND tenant_id = $2
                """,
                chat_id,
                tid,
            )
        if row is None:
            return None
        result = dict(row)
        # Parse JSONB messages
        result["messages"] = json.loads(result["messages"])
        return result


async def delete_chat(chat_id: UUID, user_id: int, tenant_id: UUID | str | None = None) -> bool:
    """刪除對話"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        result = await conn.execute(
            """
            DELETE FROM ai_chats
            WHERE id = $1 AND user_id = $2 AND tenant_id = $3
            """,
            chat_id,
            user_id,
            tid,
        )
        return result == "DELETE 1"


async def update_chat(
    chat_id: UUID,
    user_id: int,
    title: str | None = None,
    model: str | None = None,
    prompt_name: str | None = None,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """更新對話（標題、模型等）"""
    tid = _get_tenant_id(tenant_id)
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
        return await get_chat(chat_id, user_id, tenant_id=tid)

    updates.append("updated_at = NOW()")
    params.extend([chat_id, user_id, tid])

    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE ai_chats
            SET {", ".join(updates)}
            WHERE id = ${param_idx} AND user_id = ${param_idx + 1} AND tenant_id = ${param_idx + 2}
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
    chat_id: UUID, messages: list[dict], user_id: int | None = None, tenant_id: UUID | str | None = None
) -> dict | None:
    """更新對話訊息"""
    tid = _get_tenant_id(tenant_id)
    messages_json = json.dumps(messages, ensure_ascii=False)

    async with get_connection() as conn:
        if user_id is not None:
            row = await conn.fetchrow(
                """
                UPDATE ai_chats
                SET messages = $1::jsonb, updated_at = NOW()
                WHERE id = $2 AND user_id = $3 AND tenant_id = $4
                RETURNING id, user_id, title, model, prompt_name, messages, created_at, updated_at
                """,
                messages_json,
                chat_id,
                user_id,
                tid,
            )
        else:
            row = await conn.fetchrow(
                """
                UPDATE ai_chats
                SET messages = $1::jsonb, updated_at = NOW()
                WHERE id = $2 AND tenant_id = $3
                RETURNING id, user_id, title, model, prompt_name, messages, created_at, updated_at
                """,
                messages_json,
                chat_id,
                tid,
            )
        if row is None:
            return None
        result = dict(row)
        result["messages"] = json.loads(result["messages"])
        return result


async def append_message(
    chat_id: UUID, role: str, content: str, user_id: int | None = None, tenant_id: UUID | str | None = None
) -> dict | None:
    """新增一則訊息到對話"""
    chat = await get_chat(chat_id, user_id, tenant_id=tenant_id)
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

    return await update_chat_messages(chat_id, messages, user_id, tenant_id=tenant_id)


async def update_chat_title(chat_id: UUID, title: str, user_id: int | None = None, tenant_id: UUID | str | None = None) -> bool:
    """更新對話標題"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        if user_id is not None:
            result = await conn.execute(
                """
                UPDATE ai_chats
                SET title = $1, updated_at = NOW()
                WHERE id = $2 AND user_id = $3 AND tenant_id = $4
                """,
                title,
                chat_id,
                user_id,
                tid,
            )
        else:
            result = await conn.execute(
                """
                UPDATE ai_chats
                SET title = $1, updated_at = NOW()
                WHERE id = $2 AND tenant_id = $3
                """,
                title,
                chat_id,
                tid,
            )
        return "UPDATE 1" in result
