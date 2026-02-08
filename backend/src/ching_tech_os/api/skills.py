"""Skills API"""

from fastapi import APIRouter, Depends, HTTPException

from ..models.auth import SessionData
from .auth import get_current_session
from ..skills import get_skill_manager

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("")
async def list_skills(session: SessionData = Depends(get_current_session)):
    """列出所有 skills"""
    sm = get_skill_manager()
    sm.load_skills()
    return [
        {
            "name": skill.name,
            "description": skill.description,
            "requires_app": skill.requires_app,
            "tools_count": len(skill.tools),
            "tools": skill.tools,
            "mcp_servers": skill.mcp_servers,
            "has_prompt": bool(skill.prompt),
        }
        for skill in sm._skills.values()
    ]


@router.get("/{name}")
async def get_skill(name: str, session: SessionData = Depends(get_current_session)):
    """取得單一 skill 詳情（含 prompt 內容）"""
    sm = get_skill_manager()
    sm.load_skills()
    skill = sm._skills.get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {
        "name": skill.name,
        "description": skill.description,
        "requires_app": skill.requires_app,
        "tools_count": len(skill.tools),
        "tools": skill.tools,
        "mcp_servers": skill.mcp_servers,
        "has_prompt": bool(skill.prompt),
        "prompt": skill.prompt,
    }
