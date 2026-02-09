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
                "tools_count": len(skill.allowed_tools),
                "has_prompt": bool(skill.prompt),
                "references": skill.references,
                "source": skill.source,
                "license": skill.license,
                "compatibility": skill.compatibility,
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
        "tools_count": len(skill.allowed_tools),
        "allowed_tools": skill.allowed_tools,
        "mcp_servers": skill.mcp_servers,
        "has_prompt": bool(skill.prompt),
        "prompt": skill.prompt,
        "references": skill.references,
        "source": skill.source,
        "license": skill.license,
        "compatibility": skill.compatibility,
        "metadata": skill.metadata,
    }


@router.get("/{name}/references/{ref_path:path}")
async def get_skill_reference(
    name: str,
    ref_path: str,
    session: SessionData = Depends(require_admin),
):
    """讀取 skill 的 reference 檔案"""
    sm = get_skill_manager()
    content = await sm.get_skill_reference(name, ref_path)
    if content is None:
        raise HTTPException(status_code=404, detail="Reference not found")
    return {"path": ref_path, "content": content}
