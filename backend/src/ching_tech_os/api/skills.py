"""Skills API（僅限管理員）"""

import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..models.auth import SessionData
from .auth import require_admin
from ..skills import get_skill_manager
from ..services.clawhub_client import ClawHubClient, ClawHubError, get_clawhub_client_di, validate_slug
from ..services.skillhub_client import (
    SkillHubClient,
    SkillHubError,
    get_skillhub_client_di,
    skillhub_enabled,
)

# Per-skill 安裝鎖（防止同一 skill 的並發安裝競爭條件）
# value: (lock, ref_count)
_install_locks: dict[str, tuple[asyncio.Lock, int]] = {}
_lock_for_locks = asyncio.Lock()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _use_skillhub() -> bool:
    return skillhub_enabled()


def _hub_label() -> str:
    return "SkillHub" if _use_skillhub() else "ClawHub"


def _hub_source_tag() -> str:
    return "skillhub" if _use_skillhub() else "clawhub"


def _hub_error_class():
    return SkillHubError if _use_skillhub() else ClawHubError


def get_hub_client_di(request: Request) -> ClawHubClient | SkillHubClient:
    if _use_skillhub():
        return get_skillhub_client_di(request)
    return get_clawhub_client_di(request)


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
    version: str | None = Field(None, max_length=50)


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
    skill = await sm.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    meta = ClawHubClient.read_meta(sm.skills_dir / name)
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


# === Hub REST API 整合 ===

@router.post("/hub/search")
async def hub_search(
    data: HubSearchRequest,
    session: SessionData = Depends(require_admin),
    client: ClawHubClient | SkillHubClient = Depends(get_hub_client_di),
):
    """搜尋 Hub marketplace（使用 REST API）"""
    query = (data.query or "").strip()
    if not query or len(query) > 100:
        raise HTTPException(status_code=400, detail="搜尋關鍵字無效")
    try:
        results = await client.search(query)
    except (ClawHubError, SkillHubError) as e:
        raise HTTPException(
            status_code=e.status_code or 502,
            detail=f"{_hub_label()} 搜尋失敗: {e}",
        )

    return {"query": query, "results": results}


@router.post("/hub/inspect")
async def hub_inspect(
    data: HubInspectRequest,
    session: SessionData = Depends(require_admin),
    client: ClawHubClient | SkillHubClient = Depends(get_hub_client_di),
):
    """預覽 Hub skill（使用 REST API）"""
    if not validate_slug(data.slug):
        raise HTTPException(status_code=400, detail="Slug 格式無效")
    try:
        # 取得 skill 詳情（含 owner、stats、latestVersion）
        detail = await client.get_skill(data.slug)

        # 從 ZIP 取得 SKILL.md 內容（每次呼叫獨立下載，未來可加快取優化）
        skill_info = detail.get("skill", {})
        latest = detail.get("latestVersion", {})
        version = latest.get("version", "")

        content = ""
        if version:
            content = await client.extract_file_from_zip(
                data.slug, version, "SKILL.md"
            ) or ""

    except (ClawHubError, SkillHubError) as e:
        raise HTTPException(
            status_code=e.status_code or 502,
            detail=f"{_hub_label()} inspect 失敗: {e}",
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
    client: ClawHubClient | SkillHubClient = Depends(get_hub_client_di),
):
    """從 Hub 安裝 skill（使用 REST API）"""
    # 驗證名稱
    if not validate_slug(data.name):
        raise HTTPException(status_code=400, detail="Skill 名稱格式無效")

    # 取得 per-skill 鎖，確保同一 skill 的安裝操作序列化
    async with _lock_for_locks:
        entry = _install_locks.get(data.name)
        if entry is None:
            lock = asyncio.Lock()
            _install_locks[data.name] = (lock, 1)
            install_lock = lock
        else:
            lock, count = entry
            _install_locks[data.name] = (lock, count + 1)
            install_lock = lock

    version = ""
    try:
        async with install_lock:
            sm = get_skill_manager()

            # 檢查是否已安裝（在鎖內檢查，避免 TOCTOU）
            existing = await sm.get_skill(data.name)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Skill '{data.name}' 已安裝。如需更新請先移除。",
                )

            dest = sm.skills_dir / data.name
            try:
                with tempfile.TemporaryDirectory(dir=sm.skills_dir, prefix=f".{data.name}.installing-") as tmp_dir_path:
                    tmp_dest = Path(tmp_dir_path)

                    # 取得 skill 詳情以獲得版本號和 owner
                    detail = await client.get_skill(data.name)
                    latest = detail.get("latestVersion", {})
                    version = data.version or latest.get("version", "")
                    owner = detail.get("owner", {})
                    owner_handle = owner.get("handle", "")

                    if not version:
                        raise _hub_error_class()("找不到可用版本")

                    # 下載並解壓到臨時目錄
                    await client.download_and_extract(data.name, version, tmp_dest)

                    # 標記 source（讓前端顯示移除按鈕）
                    skill_md = tmp_dest / "SKILL.md"
                    if skill_md.exists():
                        content = skill_md.read_text(encoding="utf-8")
                        if "source:" not in content:
                            source_tag = _hub_source_tag()
                            content = content.replace("---\n\n", f"source: {source_tag}\n---\n\n", 1)
                            skill_md.write_text(content, encoding="utf-8")

                    # 寫入 _meta.json
                    meta_writer = SkillHubClient if _use_skillhub() else ClawHubClient
                    meta_writer.write_meta(tmp_dest, data.name, version, owner_handle)

                    # 原子移動到最終目錄
                    if dest.exists():
                        shutil.rmtree(dest)
                    tmp_dest.rename(dest)

            except (ClawHubError, SkillHubError) as e:
                raise HTTPException(
                    status_code=e.status_code or 502,
                    detail=f"安裝失敗: {e}",
                )
            except OSError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"安裝失敗（檔案系統錯誤）: {e}",
                )

            # 重載
            await sm.reload_skills()
            skill = await sm.get_skill(data.name)
    finally:
        # 釋放鎖引用，避免 _install_locks 長時間成長
        async with _lock_for_locks:
            entry = _install_locks.get(data.name)
            if entry and entry[0] is install_lock:
                lock, count = entry
                count -= 1
                if count <= 0:
                    _install_locks.pop(data.name, None)
                else:
                    _install_locks[data.name] = (lock, count)

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
