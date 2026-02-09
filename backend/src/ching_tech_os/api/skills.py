"""Skills API（僅限管理員）"""

import asyncio
import logging
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models.auth import SessionData
from .auth import require_admin
from ..skills import get_skill_manager

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
    file: str = "SKILL.md"


class HubInstallRequest(BaseModel):
    name: str
    version: str | None = None


# ClawHub CLI 解析
_SEARCH_LINE_RE = re.compile(
    r"^(\S+)\s+v([\d.]+)\s+(.+?)\s+\(([\d.]+)\)$"
)


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
    }


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


# === ClawHub 整合 ===

async def _run_clawhub(
    *args: str, timeout: int = 30, cwd: str | Path | None = None,
) -> tuple[int, str, str]:
    """執行 clawhub CLI 命令。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "clawhub", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="clawhub CLI 未安裝。請執行 npm install -g clawhub",
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="ClawHub 操作逾時")


@router.post("/hub/search")
async def hub_search(
    data: HubSearchRequest,
    session: SessionData = Depends(require_admin),
):
    """搜尋 ClawHub marketplace"""
    if not data.query or len(data.query) > 100:
        raise HTTPException(status_code=400, detail="搜尋關鍵字無效")

    code, stdout, stderr = await _run_clawhub("search", data.query)
    if code != 0:
        raise HTTPException(status_code=502, detail=f"ClawHub 搜尋失敗: {stderr}")

    results = []
    for line in stdout.strip().splitlines():
        line = line.strip()
        m = _SEARCH_LINE_RE.match(line)
        if m:
            results.append({
                "name": m.group(1),
                "version": m.group(2),
                "description": m.group(3).strip(),
                "score": float(m.group(4)),
            })

    return {"query": data.query, "results": results}


@router.post("/hub/inspect")
async def hub_inspect(
    data: HubInspectRequest,
    session: SessionData = Depends(require_admin),
):
    """預覽 ClawHub skill 的檔案內容"""
    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", data.slug) or len(data.slug) > 100:
        raise HTTPException(status_code=400, detail="Slug 格式無效")

    path_components = data.file.split("/")
    if (
        not re.match(r"^[\w.\-]+(/[\w.\-]+)*$", data.file)
        or ".." in path_components
        or "." in path_components
        or any(not comp for comp in path_components)
        or data.file.startswith("/")
        or len(data.file) > 200
    ):
        raise HTTPException(status_code=400, detail="檔案名稱無效")

    code, stdout, stderr = await _run_clawhub(
        "inspect", data.slug, "--file", data.file,
    )
    if code != 0:
        raise HTTPException(status_code=502, detail=f"ClawHub inspect 失敗: {stderr}")

    return {"slug": data.slug, "file": data.file, "content": stdout}


@router.post("/hub/install")
async def hub_install(
    data: HubInstallRequest,
    session: SessionData = Depends(require_admin),
):
    """從 ClawHub 安裝 skill"""
    # 驗證名稱
    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", data.name):
        raise HTTPException(status_code=400, detail="Skill 名稱格式無效")

    sm = get_skill_manager()

    # 檢查是否已安裝
    existing = await sm.get_skill(data.name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Skill '{data.name}' 已安裝。如需更新請先移除。",
        )

    # 下載到暫存目錄
    with tempfile.TemporaryDirectory() as tmpdir:
        args = ["install", data.name, "--force"]
        if data.version:
            args.extend(["--version", data.version])

        code, downloaded, stderr = await _run_clawhub(
            *args, timeout=60, cwd=tmpdir,
        )
        if code != 0:
            raise HTTPException(
                status_code=502,
                detail=f"安裝失敗: {stderr}",
            )
        logger.info(f"ClawHub install output: {downloaded}")

        # clawhub 會安裝到 skills/<name> 或直接 <name>
        skill_path = None
        for candidate in [
            Path(tmpdir) / data.name,
            Path(tmpdir) / "skills" / data.name,
        ]:
            if (candidate / "SKILL.md").exists():
                skill_path = candidate
                break

        # 也嘗試從 output 解析路徑
        if skill_path is None:
            for line in downloaded.splitlines():
                if "->" in line:
                    path_str = line.split("->")[-1].strip()
                    p = Path(path_str)
                    if (p / "SKILL.md").exists():
                        skill_path = p
                        break

        if skill_path is None:
            raise HTTPException(
                status_code=502,
                detail="安裝完成但找不到 SKILL.md",
            )

        # 匯入到 CTOS skills 目錄
        dest = sm.import_openclaw_skill(skill_path)

    # 重載
    await sm.reload_skills()
    skill = await sm.get_skill(data.name)

    return {
        "installed": data.name,
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
