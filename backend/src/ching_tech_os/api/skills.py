"""Skills API（僅限管理員）"""

import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Literal
from pydantic import BaseModel, Field

# 允許的 Hub 來源
HubSource = Literal["clawhub", "skillhub"]

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
from ..services.hub_meta import read_meta

# Per-skill 安裝鎖（防止同一 skill 的並發安裝競爭條件）
# value: (lock, ref_count)
_install_locks: dict[str, tuple[asyncio.Lock, int]] = {}
_lock_for_locks = asyncio.Lock()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])

# Hub 錯誤類型聯集
_HubError = (ClawHubError, SkillHubError)


def _get_clients(request: Request) -> list[tuple[str, ClawHubClient | SkillHubClient]]:
    """取得所有可用的 Hub clients（ClawHub 永遠可用，SkillHub 依 feature flag）"""
    clients: list[tuple[str, ClawHubClient | SkillHubClient]] = []
    # ClawHub 永遠啟用
    clients.append(("clawhub", get_clawhub_client_di(request)))
    # SkillHub 依 feature flag
    if skillhub_enabled():
        try:
            clients.append(("skillhub", get_skillhub_client_di(request)))
        except SkillHubError:
            logger.warning("SkillHub 已啟用但 client 初始化失敗，略過")
    return clients


def _get_client_for_source(
    request: Request, source: HubSource,
) -> ClawHubClient | SkillHubClient:
    """根據來源標籤取得對應的 client"""
    if source == "skillhub":
        if not skillhub_enabled():
            raise HTTPException(status_code=400, detail="SkillHub 未啟用")
        return get_skillhub_client_di(request)
    return get_clawhub_client_di(request)


def _source_label(source: str) -> str:
    return "SkillHub" if source == "skillhub" else "ClawHub"


def _flatten_single_subdir(dest: Path) -> None:
    """若解壓後只有一個子目錄（ZIP 巢狀），將內容提升到上層。"""
    entries = [e for e in dest.iterdir() if not e.name.startswith("_meta")]
    subdirs = [e for e in entries if e.is_dir()]
    files = [e for e in entries if e.is_file()]
    if len(subdirs) == 1 and len(files) == 0:
        nested = subdirs[0]
        logger.info(f"偵測到 ZIP 巢狀目錄，提升: {nested.name}/")
        for item in nested.iterdir():
            target = dest / item.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            item.rename(target)
        nested.rmdir()


import re as _re
_FRONTMATTER_RE = _re.compile(r"^---\s*\n", _re.MULTILINE)


def _ensure_skill_md_frontmatter(
    skill_md: Path, slug: str, detail: dict, source_tag: str,
) -> None:
    """確保 SKILL.md 有 YAML frontmatter；沒有的話從 detail 生成。"""
    if not skill_md.exists():
        # 完全沒有 SKILL.md，建立一個基本的
        skill_info = detail.get("skill", {})
        name = skill_info.get("name") or slug
        desc = skill_info.get("description") or ""
        skill_md.write_text(
            f"---\nname: {slug}\ndescription: \"{desc}\"\nsource: {source_tag}\n---\n\n# {name}\n\n{desc}\n",
            encoding="utf-8",
        )
        return

    md_content = skill_md.read_text(encoding="utf-8")
    if _FRONTMATTER_RE.match(md_content):
        # 已有 frontmatter，修正 name 為安裝 slug 並補 source
        changed = False
        # 確保 name 和目錄名一致
        name_re = _re.compile(r"^name:\s*.+$", _re.MULTILINE)
        if name_re.search(md_content):
            new_content = name_re.sub(f"name: {slug}", md_content, count=1)
            if new_content != md_content:
                md_content = new_content
                changed = True
        if "source:" not in md_content:
            md_content = md_content.replace(
                "---\n\n", f"source: {source_tag}\n---\n\n", 1
            )
            changed = True
        if changed:
            skill_md.write_text(md_content, encoding="utf-8")
        return

    # 沒有 frontmatter，從 detail 生成
    skill_info = detail.get("skill", {})
    name = skill_info.get("name") or slug
    desc = skill_info.get("description") or ""
    tags = skill_info.get("tags") or []
    tags_str = ", ".join(tags) if tags else ""
    frontmatter = f"---\nname: {slug}\ndescription: \"{desc}\"\nsource: {source_tag}\n"
    if tags_str:
        frontmatter += f"tags: [{tags_str}]\n"
    frontmatter += "---\n\n"
    skill_md.write_text(frontmatter + md_content, encoding="utf-8")


# === Request Models ===

class SkillUpdateRequest(BaseModel):
    requires_app: str | None = None
    allowed_tools: list[str] | None = None
    mcp_servers: list[str] | None = None


class HubSearchRequest(BaseModel):
    query: str
    source: HubSource | None = None  # None = both


class HubInspectRequest(BaseModel):
    slug: str
    source: HubSource = "clawhub"


class HubInstallRequest(BaseModel):
    name: str
    version: str | None = Field(None, max_length=50)
    source: HubSource = "clawhub"


# === Endpoints ===

@router.get("/hub/sources")
async def hub_sources(
    request: Request,
    session: SessionData = Depends(require_admin),
):
    """列出可用的 Hub 來源"""
    sources = [{"id": "clawhub", "name": "ClawHub", "enabled": True}]
    if skillhub_enabled():
        sources.append({"id": "skillhub", "name": "SkillHub", "enabled": True})
    return {"sources": sources}


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
    meta = read_meta(sm.skills_dir / name)

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

    meta = read_meta(sm.skills_dir / name)
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


# === Hub REST API 整合（雙來源） ===

@router.post("/hub/search")
async def hub_search(
    data: HubSearchRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
):
    """搜尋 Hub marketplace（支援雙來源合併）

    - source=None → 同時搜尋 ClawHub + SkillHub，合併結果
    - source="clawhub" → 只搜 ClawHub
    - source="skillhub" → 只搜 SkillHub
    """
    query = (data.query or "").strip()
    if not query or len(query) > 100:
        raise HTTPException(status_code=400, detail="搜尋關鍵字無效")

    # 決定要查哪些來源
    if data.source:
        # 指定單一來源
        client = _get_client_for_source(request, data.source)
        try:
            results = await client.search(query)
        except _HubError as e:
            raise HTTPException(
                status_code=getattr(e, "status_code", None) or 502,
                detail=f"{_source_label(data.source)} 搜尋失敗: {e}",
            )
        # 確保每個結果都有 source 標籤
        for r in results:
            r.setdefault("source", data.source)
        return {"query": query, "results": results}

    # 雙來源：並行搜尋，合併結果
    clients = _get_clients(request)
    all_results: list[dict] = []
    errors: list[str] = []

    async def _search_one(source: str, client: ClawHubClient | SkillHubClient) -> None:
        try:
            results = await client.search(query)
            for r in results:
                r["source"] = source
            all_results.extend(results)
        except Exception as e:
            errors.append(f"{_source_label(source)}: {e}")
            logger.warning("搜尋 %s 失敗: %s", source, e)

    await asyncio.gather(*[_search_one(src, cli) for src, cli in clients])

    # 如果全部失敗才報錯
    if not all_results and errors:
        raise HTTPException(status_code=502, detail="搜尋失敗: " + "; ".join(errors))

    return {
        "query": query,
        "results": all_results,
        "sources": [src for src, _ in clients],
        "errors": errors or None,
    }


@router.post("/hub/inspect")
async def hub_inspect(
    data: HubInspectRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
):
    """預覽 Hub skill（根據 source 選擇來源）"""
    if not validate_slug(data.slug):
        raise HTTPException(status_code=400, detail="Slug 格式無效")

    client = _get_client_for_source(request, data.source)
    try:
        # 取得 skill 詳情（含 owner、stats、latestVersion）
        detail = await client.get_skill(data.slug)

        # 從 ZIP 取得 SKILL.md 內容
        skill_info = detail.get("skill", {})
        latest = detail.get("latestVersion", {})
        version = latest.get("version", "")

        content = ""
        if version:
            content = await client.extract_file_from_zip(
                data.slug, version, "SKILL.md"
            ) or ""

    except _HubError as e:
        raise HTTPException(
            status_code=getattr(e, "status_code", None) or 502,
            detail=f"{_source_label(data.source)} inspect 失敗: {e}",
        )

    return {
        "slug": data.slug,
        "source": data.source,
        "content": content,
        "skill": skill_info,
        "owner": detail.get("owner", {}),
        "latestVersion": latest,
    }


@router.post("/hub/install")
async def hub_install(
    data: HubInstallRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
):
    """從 Hub 安裝 skill（根據 source 選擇來源）"""
    # 驗證名稱
    if not validate_slug(data.name):
        raise HTTPException(status_code=400, detail="Skill 名稱格式無效")

    client = _get_client_for_source(request, data.source)
    source_tag = data.source

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
            dest = sm.skills_dir / data.name
            if existing or dest.exists():
                raise HTTPException(
                    status_code=409,
                    detail=f"Skill '{data.name}' 已安裝。如需更新請先移除。",
                )
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
                        raise HTTPException(
                            status_code=404,
                            detail=f"在 {_source_label(source_tag)} 中找不到可用版本",
                        )

                    # 下載並解壓到臨時目錄
                    await client.download_and_extract(data.name, version, tmp_dest)

                    # 處理巢狀目錄：ZIP 內若只有一個子目錄，提升其內容
                    _flatten_single_subdir(tmp_dest)

                    # 確保 SKILL.md 有 YAML frontmatter（外部來源可能沒有）
                    skill_md = tmp_dest / "SKILL.md"
                    _ensure_skill_md_frontmatter(
                        skill_md, data.name, detail, source_tag,
                    )

                    # 寫入 _meta.json（使用對應的 client）
                    client.write_meta(tmp_dest, data.name, version, owner_handle)

                    # 原子移動到最終目錄
                    if dest.exists():
                        shutil.rmtree(dest)
                    tmp_dest.rename(dest)

            except _HubError as e:
                raise HTTPException(
                    status_code=getattr(e, "status_code", None) or 502,
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
        "source": source_tag,
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
