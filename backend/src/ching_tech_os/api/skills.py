"""Skills API（僅限管理員）"""

import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models.auth import SessionData
from .auth import require_admin
from ..skills import get_skill_manager
from ..services.clawhub_client import ClawHubClient, ClawHubError, get_clawhub_client, validate_slug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


# === Request Models ===

class SkillUpdateRequest(BaseModel):
    requires_app: str | None = None
    allowed_tools: list[str] | None = None
    mcp_servers: list[str] | None = None


class HubSearchRequest(BaseModel):
    query: str


class HubInspectRequest(BaseModel):
    slug: str


class HubInstallRequest(BaseModel):
    name: str
    version: str | None = None


# === Endpoints ===

@router.get("")
async def list_skills(session: SessionData = Depends(require_admin)):
    """列出所有 skills"""
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
                "scripts": skill.scripts,
                "scripts_count": len(skill.scripts) if skill.scripts else 0,
                "assets": skill.assets,
                "source": skill.source,
                "license": skill.license,
                "compatibility": skill.compatibility,
            }
            for skill in all_skills
        ]
    }


@router.get("/{name}")
async def get_skill(name: str, session: SessionData = Depends(require_admin)):
    """取得單一 skill 詳情"""
    sm = get_skill_manager()
    skill = await sm.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    # 取得 script tools 資訊
    script_tools = await sm.get_scripts_info(name)

    # 讀取 _meta.json
    meta = ClawHubClient.read_meta(sm.skills_dir / name)

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
        "scripts": skill.scripts,
        "script_tools": script_tools,
        "assets": skill.assets,
        "source": skill.source,
        "license": skill.license,
        "compatibility": skill.compatibility,
        "metadata": skill.metadata,
        "meta": meta,
    }


@router.get("/{name}/meta")
async def get_skill_meta(name: str, session: SessionData = Depends(require_admin)):
    """取得 skill 的 _meta.json 資訊"""
    sm = get_skill_manager()
    skill_dir = sm.skills_dir / name
    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    meta = ClawHubClient.read_meta(skill_dir)
    return {"name": name, "meta": meta}


@router.put("/{name}")
async def update_skill(
    name: str,
    data: SkillUpdateRequest,
    session: SessionData = Depends(require_admin),
):
    """編輯 skill 的權限和工具白名單"""
    sm = get_skill_manager()

    # 只包含使用者明確設定的欄位
    kwargs = data.model_dump(exclude_unset=True)

    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    ok = await sm.update_skill_metadata(name, **kwargs)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    # 回傳更新後的 skill
    skill = await sm.get_skill(name)
    return {
        "name": skill.name,
        "requires_app": skill.requires_app,
        "allowed_tools": skill.allowed_tools,
        "mcp_servers": skill.mcp_servers,
    }


@router.delete("/{name}")
async def delete_skill(name: str, session: SessionData = Depends(require_admin)):
    """移除已安裝的 skill"""
    sm = get_skill_manager()
    ok = await sm.remove_skill(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {"removed": name}


@router.post("/reload")
async def reload_skills(session: SessionData = Depends(require_admin)):
    """重新載入所有 skills（不需重啟服務）"""
    sm = get_skill_manager()
    count = await sm.reload_skills()
    return {"reloaded": count}


# === ClawHub REST API 整合 ===

@router.post("/hub/search")
async def hub_search(
    data: HubSearchRequest,
    session: SessionData = Depends(require_admin),
):
    """搜尋 ClawHub marketplace（使用 REST API）"""
    query = (data.query or "").strip()
    if not query or len(query) > 100:
        raise HTTPException(status_code=400, detail="搜尋關鍵字無效")

    client = get_clawhub_client()
    try:
        results = await client.search(query)
    except ClawHubError as e:
        raise HTTPException(
            status_code=e.status_code or 502,
            detail=f"ClawHub 搜尋失敗: {e}",
        )

    return {"query": query, "results": results}


@router.post("/hub/inspect")
async def hub_inspect(
    data: HubInspectRequest,
    session: SessionData = Depends(require_admin),
):
    """預覽 ClawHub skill（使用 REST API）"""
    if not validate_slug(data.slug):
        raise HTTPException(status_code=400, detail="Slug 格式無效")

    client = get_clawhub_client()
    try:
        # 取得 skill 詳情（含 owner、stats、latestVersion）
        detail = await client.get_skill(data.slug)

        # 從 ZIP 取得 SKILL.md 內容（下載一次，傳入 zip_data 避免重複下載）
        skill_info = detail.get("skill", {})
        latest = detail.get("latestVersion", {})
        version = latest.get("version", "")

        content = ""
        if version:
            zip_data = await client.download_zip(data.slug, version)
            content = await client.extract_file_from_zip(
                data.slug, version, "SKILL.md", zip_data=zip_data
            ) or ""

    except ClawHubError as e:
        raise HTTPException(
            status_code=e.status_code or 502,
            detail=f"ClawHub inspect 失敗: {e}",
        )

    return {
        "slug": data.slug,
        "content": content,
        "skill": skill_info,
        "owner": detail.get("owner", {}),
        "latestVersion": latest,
    }


@router.post("/hub/install")
async def hub_install(
    data: HubInstallRequest,
    session: SessionData = Depends(require_admin),
):
    """從 ClawHub 安裝 skill（使用 REST API）"""
    # 驗證名稱
    if not validate_slug(data.name):
        raise HTTPException(status_code=400, detail="Skill 名稱格式無效")

    sm = get_skill_manager()

    # 檢查是否已安裝
    existing = await sm.get_skill(data.name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Skill '{data.name}' 已安裝。如需更新請先移除。",
        )

    client = get_clawhub_client()
    dest = sm.skills_dir / data.name
    tmp_dest = sm.skills_dir / f".{data.name}.installing"
    try:
        # 取得 skill 詳情以獲得版本號和 owner
        detail = await client.get_skill(data.name)
        latest = detail.get("latestVersion", {})
        version = data.version or latest.get("version", "")
        owner = detail.get("owner", {})
        owner_handle = owner.get("handle", "")

        if not version:
            raise ClawHubError("找不到可用版本")

        # 清理可能殘留的臨時目錄
        if tmp_dest.exists():
            shutil.rmtree(tmp_dest)

        # 下載並解壓到臨時目錄（避免並發衝突）
        await client.download_and_extract(data.name, version, tmp_dest)

        # 寫入 _meta.json
        ClawHubClient.write_meta(tmp_dest, data.name, version, owner_handle)

        # 原子移動到最終目錄
        if dest.exists():
            shutil.rmtree(dest)
        tmp_dest.rename(dest)

    except ClawHubError as e:
        raise HTTPException(
            status_code=e.status_code or 502,
            detail=f"安裝失敗: {e}",
        )
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"安裝失敗（檔案系統錯誤）: {e}",
        )
    finally:
        # 清理臨時目錄
        if tmp_dest.exists():
            shutil.rmtree(tmp_dest)

    # 重載
    await sm.reload_skills()
    skill = await sm.get_skill(data.name)

    return {
        "installed": data.name,
        "version": version,
        "path": str(dest),
        "description": skill.description if skill else "",
        "scripts_count": len(skill.scripts) if skill and skill.scripts else 0,
    }


@router.get("/{name}/files/{file_path:path}")
async def get_skill_file(
    name: str,
    file_path: str,
    session: SessionData = Depends(require_admin),
):
    """讀取 skill 的檔案（references/ scripts/ assets/）"""
    sm = get_skill_manager()
    content = await sm.get_skill_file(name, file_path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": file_path, "content": content}


# 向下相容
@router.get("/{name}/references/{ref_path:path}")
async def get_skill_reference(
    name: str,
    ref_path: str,
    session: SessionData = Depends(require_admin),
):
    """讀取 skill 的 reference 檔案（向下相容）"""
    sm = get_skill_manager()
    content = await sm.get_skill_reference(name, ref_path)
    if content is None:
        raise HTTPException(status_code=404, detail="Reference not found")
    return {"path": ref_path, "content": content}
