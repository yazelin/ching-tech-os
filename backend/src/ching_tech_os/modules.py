"""功能模組 registry 與啟停控制。"""

from __future__ import annotations

import logging
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, TypedDict

from .config import settings

logger = logging.getLogger(__name__)
_SKILL_LOAD_LOCK = threading.Lock()


class RouterSpec(TypedDict, total=False):
    """單一路由註冊規格。"""

    module: str
    attr: str
    kwargs: dict[str, Any]


class ModuleInfo(TypedDict, total=False):
    """模組定義。"""

    id: str
    source: str  # builtin | skill
    routers: list[RouterSpec]
    mcp_module: str
    mcp_tools_file: str
    app_manifest: list[dict[str, Any]]
    app_ids: list[str]
    permission_defaults: dict[str, bool]
    permission_display_names: dict[str, str]
    scheduler_jobs: list[dict[str, Any]]
    lifespan_startup: str


BUILTIN_MODULES: dict[str, ModuleInfo] = {
    "core": {
        "id": "core",
        "source": "builtin",
        "routers": [
            {"module": ".api.auth", "attr": "router"},
            {"module": ".api.messages", "attr": "router"},
            {"module": ".api.login_records", "attr": "router"},
            {"module": ".api.user", "attr": "router"},
            {"module": ".api.user", "attr": "admin_router"},
            {"module": ".api.config_public", "attr": "router"},
        ],
        "app_ids": ["settings"],
        "app_manifest": [
            {"id": "settings", "name": "系統設定", "icon": "mdi-cog"},
        ],
    },
    "knowledge-base": {
        "id": "knowledge-base",
        "source": "builtin",
        "routers": [{"module": ".api.knowledge", "attr": "router"}],
        "mcp_module": ".services.mcp.knowledge_tools",
        "app_ids": ["knowledge-base"],
        "app_manifest": [
            {
                "id": "knowledge-base",
                "name": "知識庫",
                "icon": "mdi-book-open-page-variant",
            }
        ],
    },
    "file-manager": {
        "id": "file-manager",
        "source": "builtin",
        "routers": [
            {"module": ".api.nas", "attr": "router"},
            {"module": ".api.files", "attr": "router"},
        ],
        "mcp_module": ".services.mcp.nas_tools",
        "scheduler_jobs": [
            {"fn": "cleanup_linebot_temp_files", "trigger": "interval", "hours": 1},
            {"fn": "cleanup_media_temp_folders", "trigger": "cron", "hour": 5, "minute": 0},
        ],
        "app_ids": ["file-manager"],
        "app_manifest": [
            {"id": "file-manager", "name": "檔案管理", "icon": "mdi-folder"},
        ],
    },
    "ai-agent": {
        "id": "ai-agent",
        "source": "builtin",
        "routers": [
            {"module": ".api.ai_router", "attr": "router"},
            {"module": ".api.ai_management", "attr": "router"},
        ],
        "mcp_module": ".services.mcp.media_tools",
        "scheduler_jobs": [
            {"fn": "cleanup_ai_images", "trigger": "cron", "hour": 4, "minute": 30},
        ],
        "app_ids": ["ai-assistant", "prompt-editor", "agent-settings", "ai-log", "memory-manager"],
        "app_manifest": [
            {"id": "ai-assistant", "name": "AI 助手", "icon": "mdi-robot"},
            {"id": "prompt-editor", "name": "Prompt 編輯器", "icon": "mdi-script-text"},
            {"id": "agent-settings", "name": "Agent 設定", "icon": "mdi-tune-variant"},
            {"id": "ai-log", "name": "AI Log", "icon": "mdi-history"},
            {"id": "memory-manager", "name": "記憶管理", "icon": "mdi-brain"},
        ],
    },
    "line-bot": {
        "id": "line-bot",
        "source": "builtin",
        "routers": [
            {"module": ".api.linebot_router", "attr": "router", "kwargs": {"prefix": "/api/bot"}},
            {"module": ".api.linebot_router", "attr": "line_router", "kwargs": {"prefix": "/api/bot/line"}},
            {"module": ".api.bot_settings", "attr": "router"},
        ],
        "app_ids": ["linebot"],
        "app_manifest": [
            {"id": "linebot", "name": "Bot 管理", "icon": "mdi-message-text"},
        ],
        "lifespan_startup": ".services.linebot_agents.ensure_default_linebot_agents",
    },
    "telegram-bot": {
        "id": "telegram-bot",
        "source": "builtin",
        "routers": [
            {"module": ".api.telegram_router", "attr": "router", "kwargs": {"prefix": "/api/bot/telegram"}},
        ],
    },
    "public-share": {
        "id": "public-share",
        "source": "builtin",
        "routers": [
            {"module": ".api.share", "attr": "router"},
            {"module": ".api.share", "attr": "public_router"},
        ],
        "mcp_module": ".services.mcp.share_tools",
        "app_ids": ["share-manager"],
        "app_manifest": [
            {"id": "share-manager", "name": "分享管理", "icon": "mdi-share-variant"},
        ],
    },
    "docs-tools": {
        "id": "docs-tools",
        "source": "builtin",
        "routers": [{"module": ".api.presentation", "attr": "router"}],
        "mcp_module": ".services.mcp.presentation_tools",
        "app_ids": ["md2ppt", "md2doc", "printer"],
        "app_manifest": [
            {"id": "md2ppt", "name": "md2ppt", "icon": "file-powerpoint"},
            {"id": "md2doc", "name": "md2doc", "icon": "file-word"},
        ],
    },
    "skills": {
        "id": "skills",
        "source": "builtin",
        "routers": [{"module": ".api.skills", "attr": "router"}],
        "mcp_module": ".services.mcp.skill_script_tools",
    },
    "terminal": {
        "id": "terminal",
        "source": "builtin",
        "app_ids": ["terminal"],
        "app_manifest": [
            {"id": "terminal", "name": "終端機", "icon": "mdi-console"},
        ],
    },
    "code-editor": {
        "id": "code-editor",
        "source": "builtin",
        "app_ids": ["code-editor"],
        "app_manifest": [
            {"id": "code-editor", "name": "VSCode", "icon": "mdi-code-braces"},
        ],
    },
    "erpnext": {
        "id": "erpnext",
        "source": "builtin",
        "app_ids": ["project-management", "inventory-management", "vendor-management"],
        "app_manifest": [
            {"id": "erpnext", "name": "ERPNext", "icon": "erpnext"},
        ],
    },
}


def is_module_enabled(module_id: str) -> bool:
    """檢查模組是否啟用。"""

    if module_id == "core":
        return True
    enabled = (settings.enabled_modules or "*").strip()
    if enabled in {"", "*"}:
        return True
    enabled_set = {item.strip() for item in enabled.split(",") if item.strip()}
    return module_id in enabled_set


def _normalize_frontend_asset(skill_name: str, raw_path: str) -> str | None:
    """將 skill frontend 檔案路徑轉成 API 路徑。"""

    clean = raw_path.strip().replace("\\", "/")
    if clean.startswith("./"):
        clean = clean[2:]
    if clean.startswith("frontend/"):
        clean = clean[len("frontend/"):]
    if not clean or clean.startswith("/") or ".." in Path(clean).parts:
        return None
    return f"/api/skills/{skill_name}/frontend/{clean}"


def _resolve_skill_file(skill_dir: Path, raw_path: str) -> str | None:
    """解析 skill 相對檔案路徑並做路徑穿越防護。"""

    candidate = (skill_dir / raw_path).resolve()
    try:
        candidate.relative_to(skill_dir.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return str(candidate)


def _build_skill_module(skill: Any) -> ModuleInfo | None:
    """將 Skill 轉換為 ModuleInfo。"""

    metadata = skill.metadata or {}
    contributes = metadata.get("contributes")
    if not isinstance(contributes, dict):
        return None

    app_data = contributes.get("app") if isinstance(contributes.get("app"), dict) else {}
    module_id = app_data.get("id") if isinstance(app_data.get("id"), str) else skill.name

    permission_defaults: dict[str, bool] = {}
    permission_display_names: dict[str, str] = {}
    raw_permissions = contributes.get("permissions")
    if isinstance(raw_permissions, dict):
        for app_id, cfg in raw_permissions.items():
            if not isinstance(app_id, str):
                continue
            if isinstance(cfg, dict):
                permission_defaults[app_id] = bool(cfg.get("default", True))
                display_name = cfg.get("display_name")
                if isinstance(display_name, str) and display_name:
                    permission_display_names[app_id] = display_name
            elif isinstance(cfg, bool):
                permission_defaults[app_id] = cfg

    app_manifest: list[dict[str, Any]] = []
    app_ids = list(permission_defaults.keys())
    if app_data:
        app_id = app_data.get("id")
        app_name = app_data.get("name")
        app_icon = app_data.get("icon")
        if isinstance(app_id, str) and isinstance(app_name, str) and isinstance(app_icon, str):
            app_item: dict[str, Any] = {"id": app_id, "name": app_name, "icon": app_icon}
            loader = app_data.get("loader")
            if isinstance(loader, dict):
                src = loader.get("src")
                global_name = loader.get("globalName")
                if isinstance(src, str) and isinstance(global_name, str):
                    api_src = _normalize_frontend_asset(skill.name, src)
                    if api_src:
                        app_item["loader"] = {"src": api_src, "globalName": global_name}
            css = app_data.get("css")
            if isinstance(css, str):
                api_css = _normalize_frontend_asset(skill.name, css)
                if api_css:
                    app_item["css"] = api_css
            app_manifest.append(app_item)
            if app_id not in app_ids:
                app_ids.append(app_id)

    skill_dir = skill.skill_dir if isinstance(skill.skill_dir, Path) else None
    mcp_tools_file = None
    raw_mcp_tools = contributes.get("mcp_tools")
    if isinstance(raw_mcp_tools, str) and skill_dir:
        mcp_tools_file = _resolve_skill_file(skill_dir, raw_mcp_tools)
        if mcp_tools_file is None:
            logger.warning("Skill '%s' 的 contributes.mcp_tools 路徑無效，已忽略", skill.name)

    module: ModuleInfo = {
        "id": module_id,
        "source": "skill",
        "app_manifest": app_manifest,
        "app_ids": app_ids,
        "permission_defaults": permission_defaults,
        "permission_display_names": permission_display_names,
    }
    if mcp_tools_file:
        module["mcp_tools_file"] = mcp_tools_file
    if isinstance(contributes.get("scheduler"), list):
        module["scheduler_jobs"] = contributes["scheduler"]
    return module


def get_module_registry() -> dict[str, ModuleInfo]:
    """取得完整模組 registry（內建 + Skill）。"""

    registry = deepcopy(BUILTIN_MODULES)
    try:
        from .skills import get_skill_manager

        sm = get_skill_manager()
        with _SKILL_LOAD_LOCK:
            skills = sm.get_loaded_skills()
        for skill in skills:
            info = _build_skill_module(skill)
            if not info:
                continue
            module_id = info["id"]
            if module_id in registry:
                logger.warning("Skill '%s' 模組 ID '%s' 衝突，已跳過註冊", skill.name, module_id)
                continue
            registry[module_id] = info
    except Exception as e:
        logger.warning("Skill 模組 registry 載入失敗，僅使用內建模組: %s", e)
    return registry


def get_enabled_app_manifests() -> list[dict[str, Any]]:
    """回傳啟用模組的前端 App 清單。"""

    apps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for module_id, info in get_module_registry().items():
        if not is_module_enabled(module_id):
            continue
        for app in info.get("app_manifest", []):
            app_id = app.get("id")
            if not isinstance(app_id, str) or app_id in seen:
                continue
            seen.add(app_id)
            apps.append(deepcopy(app))
    return apps
