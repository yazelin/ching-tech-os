"""AI 對話 CRUD 服務"""

import json
import time
from pathlib import Path
from uuid import UUID

from ..config import settings
from ..database import get_connection


# Prompts 目錄路徑
PROMPTS_DIR = Path(settings.frontend_dir).parent / "data" / "prompts"


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


def get_available_prompts() -> list[dict]:
    """取得可用的 prompts 列表（掃描 data/prompts/ 目錄）"""
    prompts = []

    if not PROMPTS_DIR.exists():
        return prompts

    for prompt_file in PROMPTS_DIR.glob("*.md"):
        name = prompt_file.stem
        # 跳過 summarizer（內部使用）
        if name == "summarizer":
            continue

        # 讀取檔案第一行作為顯示名稱
        try:
            content = prompt_file.read_text(encoding="utf-8")
            lines = content.strip().split("\n")
            display_name = name
            description = ""

            for line in lines:
                if line.startswith("# "):
                    display_name = line[2:].strip()
                    break

            # 取得描述（第一段非標題文字）
            in_description = False
            for line in lines:
                if line.startswith("# "):
                    in_description = True
                    continue
                if in_description and line.strip():
                    if not line.startswith("#"):
                        description = line.strip()
                        break

            prompts.append(
                {
                    "name": name,
                    "display_name": display_name,
                    "description": description,
                }
            )
        except Exception:
            prompts.append(
                {
                    "name": name,
                    "display_name": name,
                    "description": "",
                }
            )

    return prompts


def get_prompt_content(prompt_name: str) -> str | None:
    """讀取 prompt 檔案內容"""
    prompt_file = PROMPTS_DIR / f"{prompt_name}.md"
    if not prompt_file.exists():
        return None
    return prompt_file.read_text(encoding="utf-8")
