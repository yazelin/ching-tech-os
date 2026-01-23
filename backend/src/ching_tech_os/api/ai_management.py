"""AI 管理 REST API 路由

提供 Prompt、Agent、Log 的 CRUD API。
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models.auth import SessionData
from .auth import get_current_session
from ..models.ai import (
    AiAgentCreate,
    AiAgentListResponse,
    AiAgentResponse,
    AiAgentUpdate,
    AiLogFilter,
    AiLogListResponse,
    AiLogResponse,
    AiLogStats,
    AiPromptCreate,
    AiPromptListResponse,
    AiPromptResponse,
    AiPromptUpdate,
    AiTestRequest,
    AiTestResponse,
)
from ..services import ai_manager

router = APIRouter(prefix="/api/ai", tags=["AI Management"])


# ============================================================
# Prompt API
# ============================================================


@router.get("/prompts", response_model=AiPromptListResponse)
async def list_prompts(
    category: str | None = None,
    session: SessionData = Depends(get_current_session),
):
    """取得 Prompt 列表

    可選參數：
    - category: 依分類過濾（system, task, template）
    """
    items = await ai_manager.get_prompts(category, tenant_id=session.tenant_id)
    return {"items": items, "total": len(items)}


@router.post("/prompts", response_model=AiPromptResponse)
async def create_prompt(
    data: AiPromptCreate,
    session: SessionData = Depends(get_current_session),
):
    """建立新 Prompt"""
    try:
        prompt = await ai_manager.create_prompt(data, tenant_id=session.tenant_id)
        return prompt
    except Exception as e:
        if "duplicate key" in str(e):
            raise HTTPException(status_code=400, detail=f"Prompt 名稱 '{data.name}' 已存在")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompts/{prompt_id}", response_model=AiPromptResponse)
async def get_prompt(
    prompt_id: UUID,
    session: SessionData = Depends(get_current_session),
):
    """取得 Prompt 詳情"""
    prompt = await ai_manager.get_prompt(prompt_id, tenant_id=session.tenant_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt 不存在")

    # 取得引用此 Prompt 的 Agents
    agents = await ai_manager.get_prompt_referencing_agents(prompt_id, tenant_id=session.tenant_id)
    prompt["referencing_agents"] = agents

    return prompt


@router.put("/prompts/{prompt_id}", response_model=AiPromptResponse)
async def update_prompt(
    prompt_id: UUID,
    data: AiPromptUpdate,
    session: SessionData = Depends(get_current_session),
):
    """更新 Prompt"""
    try:
        prompt = await ai_manager.update_prompt(prompt_id, data, tenant_id=session.tenant_id)
        if prompt is None:
            raise HTTPException(status_code=404, detail="Prompt 不存在")
        return prompt
    except Exception as e:
        if "duplicate key" in str(e):
            raise HTTPException(status_code=400, detail=f"Prompt 名稱 '{data.name}' 已存在")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: UUID,
    session: SessionData = Depends(get_current_session),
):
    """刪除 Prompt

    如果 Prompt 被 Agent 引用，會回傳錯誤。
    """
    success, error = await ai_manager.delete_prompt(prompt_id, tenant_id=session.tenant_id)
    if not success:
        if error:
            raise HTTPException(status_code=400, detail=error)
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    return {"success": True}


# ============================================================
# Agent API
# ============================================================


@router.get("/agents", response_model=AiAgentListResponse)
async def list_agents(
    session: SessionData = Depends(get_current_session),
):
    """取得 Agent 列表"""
    items = await ai_manager.get_agents(tenant_id=session.tenant_id)
    return {"items": items, "total": len(items)}


@router.post("/agents", response_model=AiAgentResponse)
async def create_agent(
    data: AiAgentCreate,
    session: SessionData = Depends(get_current_session),
):
    """建立新 Agent"""
    try:
        agent = await ai_manager.create_agent(data, tenant_id=session.tenant_id)
        return agent
    except Exception as e:
        if "duplicate key" in str(e):
            raise HTTPException(status_code=400, detail=f"Agent 名稱 '{data.name}' 已存在")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/by-name/{name}", response_model=AiAgentResponse)
async def get_agent_by_name(
    name: str,
    session: SessionData = Depends(get_current_session),
):
    """依名稱取得 Agent"""
    agent = await ai_manager.get_agent_by_name(name, tenant_id=session.tenant_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return agent


@router.get("/agents/{agent_id}", response_model=AiAgentResponse)
async def get_agent(
    agent_id: UUID,
    session: SessionData = Depends(get_current_session),
):
    """取得 Agent 詳情"""
    agent = await ai_manager.get_agent(agent_id, tenant_id=session.tenant_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return agent


@router.put("/agents/{agent_id}", response_model=AiAgentResponse)
async def update_agent(
    agent_id: UUID,
    data: AiAgentUpdate,
    session: SessionData = Depends(get_current_session),
):
    """更新 Agent"""
    try:
        agent = await ai_manager.update_agent(agent_id, data, tenant_id=session.tenant_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent 不存在")
        return agent
    except Exception as e:
        if "duplicate key" in str(e):
            raise HTTPException(status_code=400, detail=f"Agent 名稱 '{data.name}' 已存在")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: UUID,
    session: SessionData = Depends(get_current_session),
):
    """刪除 Agent

    相關的 AI logs 會保留（agent_id 設為 null）。
    """
    success = await ai_manager.delete_agent(agent_id, tenant_id=session.tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return {"success": True}


# ============================================================
# Log API
# ============================================================


@router.get("/logs", response_model=AiLogListResponse)
async def list_logs(
    agent_id: UUID | None = None,
    context_type: str | None = None,
    success: bool | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: SessionData = Depends(get_current_session),
):
    """取得 AI Log 列表（分頁）

    可選過濾參數：
    - agent_id: 依 Agent 過濾
    - context_type: 依情境類型過濾
    - success: 依成功/失敗過濾
    - start_date: 開始日期
    - end_date: 結束日期
    """
    filter_data = AiLogFilter(
        agent_id=agent_id,
        context_type=context_type,
        success=success,
        start_date=start_date,
        end_date=end_date,
    )
    items, total = await ai_manager.get_logs(
        filter_data, page, page_size, tenant_id=session.tenant_id
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/logs/stats", response_model=AiLogStats)
async def get_log_stats(
    agent_id: UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    session: SessionData = Depends(get_current_session),
):
    """取得 AI Log 統計

    可選過濾參數：
    - agent_id: 依 Agent 過濾
    - start_date: 開始日期
    - end_date: 結束日期
    """
    stats = await ai_manager.get_log_stats(
        agent_id, start_date, end_date, tenant_id=session.tenant_id
    )
    return stats


@router.get("/logs/{log_id}", response_model=AiLogResponse)
async def get_log(
    log_id: UUID,
    session: SessionData = Depends(get_current_session),
):
    """取得 AI Log 詳情"""
    log = await ai_manager.get_log(log_id, tenant_id=session.tenant_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Log 不存在")
    return log


# ============================================================
# Test API
# ============================================================


@router.post("/test", response_model=AiTestResponse)
async def test_agent(
    data: AiTestRequest,
    session: SessionData = Depends(get_current_session),
):
    """測試 Agent

    使用指定的 Agent 處理測試訊息，並記錄到 ai_logs。
    """
    result = await ai_manager.test_agent(data.agent_id, data.message, tenant_id=session.tenant_id)
    return result
