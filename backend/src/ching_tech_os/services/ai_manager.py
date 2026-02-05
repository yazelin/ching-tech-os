"""AI 管理服務

提供 Prompt、Agent、Log 的 CRUD 操作，
以及統一的 AI 調用介面。
"""

import json
import time
from datetime import datetime
from typing import Any
from uuid import UUID

from ..config import settings
from ..database import get_connection
from ..models.ai import (
    AiAgentCreate,
    AiAgentResponse,
    AiAgentUpdate,
    AiLogCreate,
    AiLogFilter,
    AiLogStats,
    AiPromptCreate,
    AiPromptResponse,
    AiPromptUpdate,
)
from .claude_agent import call_claude, compose_prompt_with_history


def _get_tenant_id(tenant_id: UUID | str | None) -> UUID:
    """處理 tenant_id 參數"""
    if tenant_id is None:
        return UUID(settings.default_tenant_id)
    if isinstance(tenant_id, str):
        return UUID(tenant_id)
    return tenant_id


# ============================================================
# Prompt CRUD
# ============================================================


async def get_prompts(category: str | None = None, tenant_id: UUID | str | None = None) -> list[dict]:
    """取得 Prompt 列表"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        if category:
            rows = await conn.fetch(
                """
                SELECT id, name, display_name, category, description, updated_at
                FROM ai_prompts
                WHERE category = $1 AND tenant_id = $2
                ORDER BY name
                """,
                category,
                tid,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, name, display_name, category, description, updated_at
                FROM ai_prompts
                WHERE tenant_id = $1
                ORDER BY name
                """,
                tid,
            )
        return [dict(row) for row in rows]


async def get_prompt(prompt_id: UUID, tenant_id: UUID | str | None = None) -> dict | None:
    """取得 Prompt 詳情"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, display_name, category, content, description,
                   variables, created_at, updated_at
            FROM ai_prompts
            WHERE id = $1 AND tenant_id = $2
            """,
            prompt_id,
            tid,
        )
        if row is None:
            return None
        result = dict(row)
        if result.get("variables"):
            result["variables"] = json.loads(result["variables"])
        return result


async def get_prompt_by_name(name: str, tenant_id: UUID | str | None = None) -> dict | None:
    """依名稱取得 Prompt"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, display_name, category, content, description,
                   variables, created_at, updated_at
            FROM ai_prompts
            WHERE name = $1 AND tenant_id = $2
            """,
            name,
            tid,
        )
        if row is None:
            return None
        result = dict(row)
        if result.get("variables"):
            result["variables"] = json.loads(result["variables"])
        return result


async def create_prompt(data: AiPromptCreate, tenant_id: UUID | str | None = None) -> dict:
    """建立 Prompt"""
    tid = _get_tenant_id(tenant_id)
    variables_json = json.dumps(data.variables) if data.variables else None

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ai_prompts (name, display_name, category, content, description, variables, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
            RETURNING id, name, display_name, category, content, description,
                      variables, created_at, updated_at
            """,
            data.name,
            data.display_name,
            data.category,
            data.content,
            data.description,
            variables_json,
            tid,
        )
        result = dict(row)
        if result.get("variables"):
            result["variables"] = json.loads(result["variables"])
        return result


async def update_prompt(prompt_id: UUID, data: AiPromptUpdate, tenant_id: UUID | str | None = None) -> dict | None:
    """更新 Prompt"""
    tid = _get_tenant_id(tenant_id)
    updates = []
    params = []
    param_idx = 1

    if data.name is not None:
        updates.append(f"name = ${param_idx}")
        params.append(data.name)
        param_idx += 1

    if data.display_name is not None:
        updates.append(f"display_name = ${param_idx}")
        params.append(data.display_name)
        param_idx += 1

    if data.category is not None:
        updates.append(f"category = ${param_idx}")
        params.append(data.category)
        param_idx += 1

    if data.content is not None:
        updates.append(f"content = ${param_idx}")
        params.append(data.content)
        param_idx += 1

    if data.description is not None:
        updates.append(f"description = ${param_idx}")
        params.append(data.description)
        param_idx += 1

    if data.variables is not None:
        updates.append(f"variables = ${param_idx}::jsonb")
        params.append(json.dumps(data.variables))
        param_idx += 1

    if not updates:
        return await get_prompt(prompt_id, tenant_id=tid)

    updates.append("updated_at = NOW()")
    params.extend([prompt_id, tid])

    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE ai_prompts
            SET {", ".join(updates)}
            WHERE id = ${param_idx} AND tenant_id = ${param_idx + 1}
            RETURNING id, name, display_name, category, content, description,
                      variables, created_at, updated_at
            """,
            *params,
        )
        if row is None:
            return None
        result = dict(row)
        if result.get("variables"):
            result["variables"] = json.loads(result["variables"])
        return result


async def delete_prompt(prompt_id: UUID, tenant_id: UUID | str | None = None) -> tuple[bool, str | None]:
    """刪除 Prompt

    Returns:
        (success, error_message)
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 檢查是否被 Agent 引用（在同一租戶內）
        agents = await conn.fetch(
            """
            SELECT name FROM ai_agents WHERE system_prompt_id = $1 AND tenant_id = $2
            """,
            prompt_id,
            tid,
        )
        if agents:
            agent_names = [a["name"] for a in agents]
            return False, f"此 Prompt 被以下 Agent 引用：{', '.join(agent_names)}"

        result = await conn.execute(
            """
            DELETE FROM ai_prompts WHERE id = $1 AND tenant_id = $2
            """,
            prompt_id,
            tid,
        )
        return "DELETE 1" in result, None


async def get_prompt_referencing_agents(prompt_id: UUID, tenant_id: UUID | str | None = None) -> list[dict]:
    """取得引用此 Prompt 的 Agents"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, display_name
            FROM ai_agents
            WHERE system_prompt_id = $1 AND tenant_id = $2
            """,
            prompt_id,
            tid,
        )
        return [dict(row) for row in rows]


# ============================================================
# Agent CRUD
# ============================================================


async def get_agents(tenant_id: UUID | str | None = None) -> list[dict]:
    """取得 Agent 列表"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, display_name, model, is_active, tools, updated_at
            FROM ai_agents
            WHERE tenant_id = $1
            ORDER BY name
            """,
            tid,
        )
        result = []
        for row in rows:
            item = dict(row)
            # 解析 tools JSON
            if item.get("tools"):
                item["tools"] = json.loads(item["tools"]) if isinstance(item["tools"], str) else item["tools"]
            result.append(item)
        return result


async def get_agent(agent_id: UUID, tenant_id: UUID | str | None = None) -> dict | None:
    """取得 Agent 詳情（含關聯的 Prompt）"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT a.id, a.name, a.display_name, a.description, a.model,
                   a.system_prompt_id, a.is_active, a.tools, a.settings,
                   a.created_at, a.updated_at,
                   p.id as prompt_id, p.name as prompt_name, p.display_name as prompt_display_name,
                   p.category as prompt_category, p.content as prompt_content,
                   p.description as prompt_description, p.variables as prompt_variables,
                   p.created_at as prompt_created_at, p.updated_at as prompt_updated_at
            FROM ai_agents a
            LEFT JOIN ai_prompts p ON a.system_prompt_id = p.id
            WHERE a.id = $1 AND a.tenant_id = $2
            """,
            agent_id,
            tid,
        )
        if row is None:
            return None

        result = dict(row)
        if result.get("settings"):
            result["settings"] = json.loads(result["settings"])
        if result.get("tools"):
            result["tools"] = json.loads(result["tools"]) if isinstance(result["tools"], str) else result["tools"]

        # 組裝關聯的 Prompt
        if result.get("prompt_id"):
            prompt_vars = result.get("prompt_variables")
            result["system_prompt"] = {
                "id": result["prompt_id"],
                "name": result["prompt_name"],
                "display_name": result["prompt_display_name"],
                "category": result["prompt_category"],
                "content": result["prompt_content"],
                "description": result["prompt_description"],
                "variables": json.loads(prompt_vars) if prompt_vars else None,
                "created_at": result["prompt_created_at"],
                "updated_at": result["prompt_updated_at"],
            }
        else:
            result["system_prompt"] = None

        # 移除多餘欄位
        for key in list(result.keys()):
            if key.startswith("prompt_"):
                del result[key]

        return result


async def get_agent_by_name(name: str) -> dict | None:
    """依名稱取得 Agent（含關聯的 Prompt）"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT a.id, a.name, a.display_name, a.description, a.model,
                   a.system_prompt_id, a.is_active, a.tools, a.settings,
                   a.created_at, a.updated_at,
                   p.id as prompt_id, p.name as prompt_name, p.display_name as prompt_display_name,
                   p.category as prompt_category, p.content as prompt_content,
                   p.description as prompt_description, p.variables as prompt_variables,
                   p.created_at as prompt_created_at, p.updated_at as prompt_updated_at
            FROM ai_agents a
            LEFT JOIN ai_prompts p ON a.system_prompt_id = p.id
            WHERE a.name = $1
            """,
            name,
        )
        if row is None:
            return None

        result = dict(row)
        if result.get("settings"):
            result["settings"] = json.loads(result["settings"])
        if result.get("tools"):
            result["tools"] = json.loads(result["tools"]) if isinstance(result["tools"], str) else result["tools"]

        # 組裝關聯的 Prompt
        if result.get("prompt_id"):
            prompt_vars = result.get("prompt_variables")
            result["system_prompt"] = {
                "id": result["prompt_id"],
                "name": result["prompt_name"],
                "display_name": result["prompt_display_name"],
                "category": result["prompt_category"],
                "content": result["prompt_content"],
                "description": result["prompt_description"],
                "variables": json.loads(prompt_vars) if prompt_vars else None,
                "created_at": result["prompt_created_at"],
                "updated_at": result["prompt_updated_at"],
            }
        else:
            result["system_prompt"] = None

        # 移除多餘欄位
        for key in list(result.keys()):
            if key.startswith("prompt_"):
                del result[key]

        return result


async def create_agent(data: AiAgentCreate, tenant_id: UUID | str | None = None) -> dict:
    """建立 Agent"""
    tid = _get_tenant_id(tenant_id)
    settings_json = json.dumps(data.settings) if data.settings else None
    tools_json = json.dumps(data.tools) if data.tools else None

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ai_agents (name, display_name, description, model,
                                   system_prompt_id, is_active, tools, settings, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9)
            RETURNING id, name, display_name, description, model,
                      system_prompt_id, is_active, tools, settings, created_at, updated_at
            """,
            data.name,
            data.display_name,
            data.description,
            data.model,
            data.system_prompt_id,
            data.is_active,
            tools_json,
            settings_json,
            tid,
        )
        result = dict(row)
        if result.get("settings"):
            result["settings"] = json.loads(result["settings"])
        if result.get("tools"):
            result["tools"] = json.loads(result["tools"]) if isinstance(result["tools"], str) else result["tools"]
        return result


async def update_agent(agent_id: UUID, data: AiAgentUpdate, tenant_id: UUID | str | None = None) -> dict | None:
    """更新 Agent"""
    tid = _get_tenant_id(tenant_id)
    updates = []
    params = []
    param_idx = 1

    if data.name is not None:
        updates.append(f"name = ${param_idx}")
        params.append(data.name)
        param_idx += 1

    if data.display_name is not None:
        updates.append(f"display_name = ${param_idx}")
        params.append(data.display_name)
        param_idx += 1

    if data.description is not None:
        updates.append(f"description = ${param_idx}")
        params.append(data.description)
        param_idx += 1

    if data.model is not None:
        updates.append(f"model = ${param_idx}")
        params.append(data.model)
        param_idx += 1

    if data.system_prompt_id is not None:
        updates.append(f"system_prompt_id = ${param_idx}")
        params.append(data.system_prompt_id)
        param_idx += 1

    if data.is_active is not None:
        updates.append(f"is_active = ${param_idx}")
        params.append(data.is_active)
        param_idx += 1

    if data.tools is not None:
        updates.append(f"tools = ${param_idx}::jsonb")
        params.append(json.dumps(data.tools))
        param_idx += 1

    if data.settings is not None:
        updates.append(f"settings = ${param_idx}::jsonb")
        params.append(json.dumps(data.settings))
        param_idx += 1

    if not updates:
        return await get_agent(agent_id, tenant_id=tid)

    updates.append("updated_at = NOW()")
    params.extend([agent_id, tid])

    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE ai_agents
            SET {", ".join(updates)}
            WHERE id = ${param_idx} AND tenant_id = ${param_idx + 1}
            RETURNING id, name, display_name, description, model,
                      system_prompt_id, is_active, tools, settings, created_at, updated_at
            """,
            *params,
        )
        if row is None:
            return None
        result = dict(row)
        if result.get("tools"):
            result["tools"] = json.loads(result["tools"]) if isinstance(result["tools"], str) else result["tools"]
        if result.get("settings"):
            result["settings"] = json.loads(result["settings"])
        return result


async def delete_agent(agent_id: UUID, tenant_id: UUID | str | None = None) -> bool:
    """刪除 Agent（相關的 ai_logs 會將 agent_id 設為 null）"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        result = await conn.execute(
            """
            DELETE FROM ai_agents WHERE id = $1 AND tenant_id = $2
            """,
            agent_id,
            tid,
        )
        return "DELETE 1" in result


# ============================================================
# AI Log CRUD
# ============================================================


async def create_log(data: AiLogCreate, tenant_id: UUID | str | None = None) -> dict:
    """建立 AI Log"""
    tid = _get_tenant_id(tenant_id)
    parsed_json = json.dumps(data.parsed_response) if data.parsed_response else None
    allowed_tools_json = json.dumps(data.allowed_tools) if data.allowed_tools else None

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ai_logs (agent_id, prompt_id, context_type, context_id,
                                input_prompt, system_prompt, allowed_tools, raw_response, parsed_response, model,
                                success, error_message, duration_ms, input_tokens, output_tokens, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9::jsonb, $10, $11, $12, $13, $14, $15, $16)
            RETURNING id, agent_id, prompt_id, context_type, context_id,
                      input_prompt, system_prompt, allowed_tools, raw_response, parsed_response, model,
                      success, error_message, duration_ms, input_tokens, output_tokens, created_at
            """,
            data.agent_id,
            data.prompt_id,
            data.context_type,
            data.context_id,
            data.input_prompt,
            data.system_prompt,
            allowed_tools_json,
            data.raw_response,
            parsed_json,
            data.model,
            data.success,
            data.error_message,
            data.duration_ms,
            data.input_tokens,
            data.output_tokens,
            tid,
        )
        result = dict(row)
        if result.get("parsed_response"):
            result["parsed_response"] = json.loads(result["parsed_response"])
        if result.get("allowed_tools"):
            result["allowed_tools"] = json.loads(result["allowed_tools"]) if isinstance(result["allowed_tools"], str) else result["allowed_tools"]
        return result


async def get_logs(
    filter_data: AiLogFilter | None = None,
    page: int = 1,
    page_size: int = 50,
    tenant_id: UUID | str | None = None,
) -> tuple[list[dict], int]:
    """取得 AI Log 列表（分頁）

    Returns:
        (items, total)
    """
    tid = _get_tenant_id(tenant_id)
    where_clauses = [f"l.tenant_id = ${1}"]
    params = [tid]
    param_idx = 2

    if filter_data:
        if filter_data.agent_id:
            where_clauses.append(f"l.agent_id = ${param_idx}")
            params.append(filter_data.agent_id)
            param_idx += 1

        if filter_data.context_type:
            where_clauses.append(f"l.context_type = ${param_idx}")
            params.append(filter_data.context_type)
            param_idx += 1

        if filter_data.success is not None:
            where_clauses.append(f"l.success = ${param_idx}")
            params.append(filter_data.success)
            param_idx += 1

        if filter_data.start_date:
            where_clauses.append(f"l.created_at >= ${param_idx}")
            params.append(filter_data.start_date)
            param_idx += 1

        if filter_data.end_date:
            where_clauses.append(f"l.created_at <= ${param_idx}")
            params.append(filter_data.end_date)
            param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    async with get_connection() as conn:
        # 取得總數
        count_row = await conn.fetchrow(
            f"""
            SELECT COUNT(*) as total
            FROM ai_logs l
            {where_sql}
            """,
            *params,
        )
        total = count_row["total"]

        # 取得分頁資料
        offset = (page - 1) * page_size
        params.extend([page_size, offset])

        rows = await conn.fetch(
            f"""
            SELECT l.id, l.agent_id, a.name as agent_name, l.context_type,
                   l.allowed_tools, l.parsed_response,
                   l.success, l.duration_ms, l.input_tokens, l.output_tokens, l.created_at
            FROM ai_logs l
            LEFT JOIN ai_agents a ON l.agent_id = a.id
            {where_sql}
            ORDER BY l.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params,
        )

        # 處理每筆資料，解析 allowed_tools 和 used_tools
        items = []
        for row in rows:
            item = dict(row)
            # 解析 allowed_tools
            if item.get("allowed_tools"):
                item["allowed_tools"] = json.loads(item["allowed_tools"]) if isinstance(item["allowed_tools"], str) else item["allowed_tools"]
            # 從 parsed_response 提取 used_tools
            if item.get("parsed_response"):
                parsed = json.loads(item["parsed_response"]) if isinstance(item["parsed_response"], str) else item["parsed_response"]
                tool_calls = parsed.get("tool_calls", []) if parsed else []
                item["used_tools"] = list(set(tc.get("name") for tc in tool_calls if tc.get("name")))
            else:
                item["used_tools"] = []
            # 移除 parsed_response（列表不需要完整內容）
            del item["parsed_response"]
            items.append(item)

        return items, total


async def get_log(log_id: UUID, tenant_id: UUID | str | None = None) -> dict | None:
    """取得 AI Log 詳情"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT l.id, l.agent_id, a.name as agent_name, l.prompt_id,
                   l.context_type, l.context_id, l.input_prompt, l.system_prompt,
                   l.allowed_tools, l.raw_response, l.parsed_response, l.model, l.success, l.error_message,
                   l.duration_ms, l.input_tokens, l.output_tokens, l.created_at
            FROM ai_logs l
            LEFT JOIN ai_agents a ON l.agent_id = a.id
            WHERE l.id = $1 AND l.tenant_id = $2
            """,
            log_id,
            tid,
        )
        if row is None:
            return None
        result = dict(row)
        if result.get("parsed_response"):
            result["parsed_response"] = json.loads(result["parsed_response"])
        if result.get("allowed_tools"):
            result["allowed_tools"] = json.loads(result["allowed_tools"]) if isinstance(result["allowed_tools"], str) else result["allowed_tools"]
        return result


async def get_log_stats(
    agent_id: UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    tenant_id: UUID | str | None = None,
) -> dict:
    """取得 AI Log 統計"""
    tid = _get_tenant_id(tenant_id)
    where_clauses = [f"tenant_id = ${1}"]
    params = [tid]
    param_idx = 2

    if agent_id:
        where_clauses.append(f"agent_id = ${param_idx}")
        params.append(agent_id)
        param_idx += 1

    if start_date:
        where_clauses.append(f"created_at >= ${param_idx}")
        params.append(start_date)
        param_idx += 1

    if end_date:
        where_clauses.append(f"created_at <= ${param_idx}")
        params.append(end_date)
        param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT
                COUNT(*) as total_calls,
                COUNT(*) FILTER (WHERE success = true) as success_count,
                COUNT(*) FILTER (WHERE success = false) as failure_count,
                AVG(duration_ms) FILTER (WHERE duration_ms IS NOT NULL) as avg_duration_ms,
                COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                COALESCE(SUM(output_tokens), 0) as total_output_tokens
            FROM ai_logs
            {where_sql}
            """,
            *params,
        )

        total_calls = row["total_calls"]
        success_count = row["success_count"]
        success_rate = (success_count / total_calls * 100) if total_calls > 0 else 0.0

        return {
            "total_calls": total_calls,
            "success_count": success_count,
            "failure_count": row["failure_count"],
            "success_rate": round(success_rate, 2),
            "avg_duration_ms": round(row["avg_duration_ms"], 2) if row["avg_duration_ms"] else None,
            "total_input_tokens": row["total_input_tokens"],
            "total_output_tokens": row["total_output_tokens"],
        }


# ============================================================
# 統一 AI 調用介面
# ============================================================


async def call_agent(
    agent_name: str,
    message: str,
    context_type: str | None = None,
    context_id: str | None = None,
    history: list[dict] | None = None,
    tenant_id: UUID | str | None = None,
) -> dict:
    """透過 Agent 調用 AI

    會自動取得 Agent 設定、調用 AI、記錄 Log。

    Args:
        agent_name: Agent 名稱
        message: 使用者訊息
        context_type: 調用情境類型
        context_id: 調用情境 ID
        history: 對話歷史
        tenant_id: 租戶 ID

    Returns:
        {
            "success": bool,
            "response": str | None,
            "error": str | None,
            "duration_ms": int | None,
            "log_id": UUID | None
        }
    """
    tid = _get_tenant_id(tenant_id)

    # 取得 Agent
    agent = await get_agent_by_name(agent_name)
    if agent is None:
        return {
            "success": False,
            "response": None,
            "error": f"Agent '{agent_name}' 不存在",
            "duration_ms": None,
            "log_id": None,
        }

    if not agent["is_active"]:
        return {
            "success": False,
            "response": None,
            "error": f"Agent '{agent_name}' 已停用",
            "duration_ms": None,
            "log_id": None,
        }

    # 取得 system prompt
    system_prompt = None
    prompt_id = None
    if agent.get("system_prompt"):
        system_prompt = agent["system_prompt"]["content"]
        prompt_id = agent["system_prompt"]["id"]

    # 取得工具列表
    tools = agent.get("tools") if agent.get("tools") else None

    # 調用 AI
    start_time = time.time()
    result = await call_claude(
        prompt=message,
        model=agent["model"],
        history=history,
        system_prompt=system_prompt,
        tools=tools,
    )
    duration_ms = int((time.time() - start_time) * 1000)

    # 組合完整輸入（含歷史對話）
    if history:
        full_input = compose_prompt_with_history(history, message)
    else:
        full_input = message

    # 建立 Log
    log_data = AiLogCreate(
        agent_id=agent["id"],
        prompt_id=prompt_id,
        context_type=context_type,
        context_id=context_id,
        input_prompt=full_input,
        system_prompt=system_prompt,
        allowed_tools=tools,
        raw_response=result.message if result.success else None,
        model=agent["model"],
        success=result.success,
        error_message=result.error if not result.success else None,
        duration_ms=duration_ms,
    )
    log = await create_log(log_data, tenant_id=tid)

    return {
        "success": result.success,
        "response": result.message if result.success else None,
        "error": result.error if not result.success else None,
        "duration_ms": duration_ms,
        "log_id": log["id"],
    }


async def test_agent(agent_id: UUID, message: str, tenant_id: UUID | str | None = None) -> dict:
    """測試 Agent

    Returns:
        {
            "success": bool,
            "response": str | None,
            "error": str | None,
            "duration_ms": int | None,
            "log_id": UUID | None
        }
    """
    tid = _get_tenant_id(tenant_id)

    # 取得 Agent
    agent = await get_agent(agent_id, tenant_id=tid)
    if agent is None:
        return {
            "success": False,
            "response": None,
            "error": "Agent 不存在",
            "duration_ms": None,
            "log_id": None,
        }

    # 使用 agent name 調用
    return await call_agent(
        agent_name=agent["name"],
        message=message,
        context_type="test",
        context_id=str(agent_id),
        tenant_id=tid,
    )


# ============================================================
# 分區表管理
# ============================================================


async def ensure_log_partitions() -> None:
    """確保 AI Log 分區存在（呼叫資料庫函數）"""
    async with get_connection() as conn:
        await conn.execute("SELECT create_ai_logs_partition()")
