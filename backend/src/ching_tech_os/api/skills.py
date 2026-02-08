"""Skills API（僅限管理員）"""

from fastapi import APIRouter, Depends, HTTPException

from ..models.auth import SessionData
from .auth import require_admin
from ..skills import get_skill_manager

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("")
async def list_skills(session: SessionData = Depends(require_admin)):
    """列出所有 skills（僅限管理員）"""
    sm = get_skill_manager()
    all_skills = await sm.get_all_skills()
    return {
        "skills": [
            {
                "name": skill.name,
                "description": skill.description,
                "requires_app": skill.requires_app,
                "tools_count": len(skill.tools),
                "has_prompt": bool(skill.prompt),
            }
            for skill in all_skills
        ]
    }


@router.get("/{name}")
async def get_skill(name: str, session: SessionData = Depends(require_admin)):
    """取得單一 skill 詳情（含 prompt，僅限管理員）"""
    sm = get_skill_manager()
    skill = await sm.get_skill(name)
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
