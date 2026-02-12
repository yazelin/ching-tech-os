"""Skills 管理器

動態載入和管理 AI Skills。
支援 Agent Skills 開放標準（agentskills.io）格式，
CTOS 擴充欄位放在 metadata.ctos 下。
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from ..config import settings

logger = logging.getLogger(__name__)

# Skills 目錄
SKILLS_DIR = Path(__file__).parent

# YAML frontmatter 解析
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def _parse_skill_md(text: str) -> tuple[dict, str]:
    """解析 SKILL.md：YAML frontmatter + Markdown body。

    Returns:
        (frontmatter_dict, body_str)
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    body = m.group(2).strip()
    return fm, body


def _parse_allowed_tools(value: str | list | None) -> list[str]:
    """解析 allowed-tools 欄位（標準：空格分隔字串）或 tools（舊版：list）。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return value.split()
    return []


def _parse_mcp_servers(value: str | list | None) -> list[str]:
    """解析 mcp_servers（支援空格分隔字串或 list）。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return value.split()
    return []


@dataclass
class Skill:
    """一個 AI Skill 的完整定義（Agent Skills 標準 + CTOS 擴充）"""
    # === 標準欄位 ===
    name: str
    description: str
    license: str = ""
    compatibility: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # === CTOS 擴充（從 metadata.ctos 讀取）===
    requires_app: Optional[str] = None
    mcp_servers: list[str] = field(default_factory=list)

    # === 內部欄位 ===
    prompt: str = ""
    references: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    source: str = "native"  # native | openclaw | claude-code
    skill_dir: Path | None = None


def _extract_ctos_metadata(config: dict) -> tuple[Optional[str], list[str]]:
    """從 frontmatter 提取 CTOS 擴充欄位。

    優先從 metadata.ctos 讀取（標準相容），
    回退到頂層 requires_app / mcp_servers（舊版相容）。
    """
    ctos = (config.get("metadata") or {}).get("ctos", {})

    # requires_app
    requires_app = ctos.get("requires_app")
    if requires_app is None:
        requires_app = config.get("requires_app")

    # mcp_servers
    mcp_servers_raw = ctos.get("mcp_servers")
    if mcp_servers_raw is None:
        mcp_servers_raw = config.get("mcp_servers")
    mcp_servers = _parse_mcp_servers(mcp_servers_raw)

    return requires_app, mcp_servers


_VALID_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


def _validate_skill_name(name: str) -> str:
    """驗證 skill 名稱（防止路徑穿越，符合 Agent Skills 標準）。

    只允許小寫字母、數字、hyphen，不允許連續 hyphen。
    """
    if not name or len(name) > 64:
        raise ValueError(f"Skill name 長度無效: {name!r}")
    if "--" in name or not _VALID_NAME_RE.match(name):
        raise ValueError(f"Skill name 格式無效: {name!r}")
    return name


def _build_skill(config: dict, body: str, skill_dir: Path, source: str = "native") -> Skill:
    """從 frontmatter + body 建立 Skill 物件。"""
    # 使用目錄名作為 skill 識別名（確保與目錄一致，避免刪除時路徑不符）
    name = skill_dir.name
    _validate_skill_name(name)

    # allowed-tools（標準）或 tools（舊版）
    allowed_tools = _parse_allowed_tools(
        config.get("allowed-tools") or config.get("tools")
    )

    requires_app, mcp_servers = _extract_ctos_metadata(config)

    # 掃描 references/ scripts/ assets/ 目錄
    def _scan_subdir(subdir_name: str) -> list[str]:
        subdir = skill_dir / subdir_name
        if not subdir.is_dir():
            return []
        return sorted(
            str(f.relative_to(skill_dir))
            for f in subdir.rglob("*")
            if f.is_file()
        )

    return Skill(
        name=name,
        description=config.get("description", ""),
        license=config.get("license", ""),
        compatibility=config.get("compatibility", ""),
        allowed_tools=allowed_tools,
        metadata=config.get("metadata") or {},
        requires_app=requires_app,
        mcp_servers=mcp_servers,
        prompt=body,
        references=_scan_subdir("references"),
        scripts=_scan_subdir("scripts"),
        assets=_scan_subdir("assets"),
        source=config.get("source", source),
        skill_dir=skill_dir,
    )


class SkillManager:
    """Skills 載入和管理"""

    def __init__(
        self,
        skills_dir: Path | str | None = None,
        external_skills_dir: Path | str | None = None,
    ):
        self._native_skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR
        configured_external = external_skills_dir or settings.skill_external_root
        self._external_skills_dir = Path(configured_external).expanduser()
        # 外部目錄做為可寫入目錄（Hub 安裝/匯入）
        self._writable_skills_dir = self._external_skills_dir
        self._skills: dict[str, Skill] = {}
        self._skill_dirs: dict[str, Path] = {}
        self._loaded = False
        self._load_lock = asyncio.Lock()

    @property
    def skills_dir(self) -> Path:
        """可寫入的 Skills 目錄路徑（external root）。"""
        return self._writable_skills_dir

    @property
    def native_skills_dir(self) -> Path:
        """內建 Skills 目錄路徑。"""
        return self._native_skills_dir

    @property
    def external_skills_dir(self) -> Path:
        """外部 Skills 目錄路徑。"""
        return self._external_skills_dir

    async def load_skills(self) -> None:
        """掃描 skills 目錄，載入所有 skill 定義（async-safe）"""
        async with self._load_lock:
            if self._loaded:
                return
            await asyncio.to_thread(self._load_skills_sync)

    def _load_skill_from_skill_md(self, skill_dir: Path, source: str) -> Skill | None:
        """從 SKILL.md 載入（Agent Skills 標準格式）"""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        text = skill_md.read_text(encoding="utf-8")
        config, body = _parse_skill_md(text)
        if not config:
            logger.warning(f"SKILL.md 無 frontmatter: {skill_dir}")
            return None

        return _build_skill(config, body, skill_dir, source=source)

    def _load_skill_from_yaml(self, skill_dir: Path, source: str) -> Skill | None:
        """從舊版 skill.yaml + prompt.md 載入（向下相容）"""
        skill_yaml = skill_dir / "skill.yaml"
        if not skill_yaml.exists():
            return None

        with open(skill_yaml, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        prompt = ""
        prompt_md = skill_dir / "prompt.md"
        if prompt_md.exists():
            prompt = prompt_md.read_text(encoding="utf-8")

        return _build_skill(config, prompt, skill_dir, source=source)

    def _load_skills_sync(self) -> None:
        """同步載入 skills（在 thread pool 中執行，避免 blocking event loop）"""
        self._skills.clear()
        self._skill_dirs.clear()

        # 確保 external root 存在（預設 ~/SDD/skill）
        try:
            self._external_skills_dir.mkdir(parents=True, exist_ok=True)
            from .seed_external import ensure_seed_skills
            ensure_seed_skills(self._external_skills_dir)
        except Exception as e:
            logger.warning(f"建立/初始化 external skills 目錄失敗: {self._external_skills_dir} ({e})")

        def _load_root(root: Path, source: str, can_override_existing: bool) -> None:
            if not root.exists():
                logger.warning(f"Skills 目錄不存在: {root}")
                return

            for skill_dir in sorted(root.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                    continue

                try:
                    # 優先讀 SKILL.md，否則回退到 skill.yaml + prompt.md
                    skill = self._load_skill_from_skill_md(skill_dir, source=source)
                    if skill is None:
                        skill = self._load_skill_from_yaml(skill_dir, source=source)
                    if skill is None:
                        continue

                    existing = self._skills.get(skill.name)
                    if existing:
                        if can_override_existing:
                            prev_dir = self._skill_dirs.get(skill.name)
                            logger.info(
                                "skill 來源覆蓋: %s (%s -> %s)",
                                skill.name,
                                prev_dir,
                                skill_dir,
                            )
                        else:
                            logger.info(
                                "跳過同名 skill（保留 external 優先）: %s (%s)",
                                skill.name,
                                skill_dir,
                            )
                            continue

                    self._skills[skill.name] = skill
                    self._skill_dirs[skill.name] = skill_dir
                    refs_info = f", {len(skill.references)} refs" if skill.references else ""
                    logger.debug(
                        "載入 skill: %s (%s, %s tools%s)",
                        skill.name,
                        source,
                        len(skill.allowed_tools),
                        refs_info,
                    )

                except (yaml.YAMLError, OSError) as e:
                    logger.error(f"載入 skill 失敗 {skill_dir}: {e}")

        # external-first：同名 skill 由 external 覆蓋 native
        _load_root(self._external_skills_dir, source="external", can_override_existing=True)
        _load_root(self._native_skills_dir, source="native", can_override_existing=False)

        self._loaded = True
        logger.info(
            "共載入 %s 個 skills（external: %s, native: %s）",
            len(self._skills),
            self._external_skills_dir,
            self._native_skills_dir,
        )

    def import_openclaw_skill(self, skill_path: Path) -> Path:
        """從 OpenClaw / Agent Skills 標準 SKILL.md 匯入。

        匯入後管理員需手動設定 metadata.ctos 的權限和 MCP servers。

        Args:
            skill_path: Skill 目錄（含 SKILL.md）

        Returns:
            匯入後的 skill 目錄路徑
        """
        src_skill_md = skill_path / "SKILL.md"
        if not src_skill_md.exists():
            raise FileNotFoundError(f"找不到 SKILL.md: {skill_path}")

        text = src_skill_md.read_text(encoding="utf-8")
        config, body = _parse_skill_md(text)

        name = config.get("name", skill_path.name)
        _validate_skill_name(name)
        dest_dir = self.skills_dir / name
        dest_dir.mkdir(parents=True, exist_ok=True)

        # 確保 metadata.ctos 存在（防禦 metadata: null）
        if not isinstance(config.get("metadata"), dict):
            config["metadata"] = {}
        if not isinstance(config["metadata"].get("ctos"), dict):
            config["metadata"]["ctos"] = {
                "requires_app": None,
                "mcp_servers": "",
            }

        # 標記來源
        config["source"] = "openclaw"

        # 寫出 SKILL.md
        fm_text = yaml.dump(
            config, allow_unicode=True, default_flow_style=False
        ).strip()
        dest_skill_md = dest_dir / "SKILL.md"
        dest_skill_md.write_text(
            f"---\n{fm_text}\n---\n\n{body}\n",
            encoding="utf-8",
        )

        # 複製 references/ scripts/ assets/（如果有）
        import shutil
        for subdir_name in ("references", "scripts", "assets"):
            src_sub = skill_path / subdir_name
            if src_sub.is_dir():
                dest_sub = dest_dir / subdir_name
                if dest_sub.exists():
                    shutil.rmtree(dest_sub)
                shutil.copytree(src_sub, dest_sub)

        logger.info(f"匯入 OpenClaw skill: {name} → {dest_dir}")

        # 重設載入狀態
        self._loaded = False
        self._skills.clear()

        return dest_dir

    async def get_skill(self, name: str) -> Skill | None:
        """根據名稱取得 skill"""
        await self.load_skills()
        return self._skills.get(name)

    async def get_all_skills(self) -> list[Skill]:
        """取得所有 skills"""
        await self.load_skills()
        return list(self._skills.values())

    def _is_within_skill_roots(self, path: Path) -> bool:
        """檢查路徑是否在受信任的 skill roots 內。"""
        resolved = path.resolve()
        for root in (self._external_skills_dir, self._native_skills_dir):
            try:
                resolved.relative_to(root.resolve())
                return True
            except ValueError:
                continue
        return False

    async def get_skill_dir(self, name: str) -> Path | None:
        """取得 skill 實際目錄（可能為 external 或 native）。"""
        await self.load_skills()
        return self._skill_dirs.get(name)

    async def get_skills_for_user(
        self,
        app_permissions: dict[str, bool],
    ) -> list[Skill]:
        """根據使用者權限回傳可用的 skills"""
        await self.load_skills()
        result = []
        for skill in self._skills.values():
            if skill.requires_app is None:
                result.append(skill)
            elif app_permissions.get(skill.requires_app, False):
                result.append(skill)
        return result

    async def generate_tools_prompt(
        self,
        app_permissions: dict[str, bool],
        is_group: bool = False,
    ) -> str:
        """根據使用者權限動態生成工具說明 prompt"""
        skills = await self.get_skills_for_user(app_permissions)
        sections = [skill.prompt for skill in skills if skill.prompt]
        return "\n\n".join(sections)

    async def get_tool_names(
        self,
        app_permissions: dict[str, bool],
    ) -> list[str]:
        """回傳使用者可用的所有工具名稱"""
        skills = await self.get_skills_for_user(app_permissions)
        tools = []
        for skill in skills:
            tools.extend(skill.allowed_tools)
        return tools

    async def get_required_mcp_servers(
        self,
        app_permissions: dict[str, bool],
    ) -> set[str]:
        """回傳使用者需要的 MCP server 名稱"""
        skills = await self.get_skills_for_user(app_permissions)
        servers = set()
        for skill in skills:
            servers.update(skill.mcp_servers)
        return servers

    async def reload_skills(self) -> int:
        """重新載入所有 skills（不需重啟服務）。

        Returns:
            載入的 skill 數量
        """
        async with self._load_lock:
            self._loaded = False
            self._skills.clear()
        await self.load_skills()
        return len(self._skills)

    async def update_skill_metadata(
        self,
        name: str,
        *,
        requires_app: str | None = ...,
        allowed_tools: list[str] | None = ...,
        mcp_servers: list[str] | None = ...,
    ) -> bool:
        """更新 skill 的 CTOS 擴充欄位，寫回 SKILL.md frontmatter。

        只更新 frontmatter，保留 Markdown body 不動。
        使用 ... (Ellipsis) 區分「未傳」和「傳 null」。
        更新後自動觸發重載。

        Returns:
            True if successful
        """
        await self.load_skills()
        if name not in self._skills:
            return False

        skill_dir = self._skill_dirs.get(name)
        if not skill_dir:
            return False
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            return False

        # 安全檢查：確保在受信任的 skills roots 下（防止 symlink 攻擊）
        if not self._is_within_skill_roots(skill_md_path):
            return False

        text = skill_md_path.read_text(encoding="utf-8")
        config, body = _parse_skill_md(text)
        if not config:
            return False

        # 更新 allowed-tools
        if allowed_tools is not ...:
            if allowed_tools is None:
                config.pop("allowed-tools", None)
            else:
                config["allowed-tools"] = " ".join(allowed_tools)

        # 更新 metadata.ctos
        if not isinstance(config.get("metadata"), dict):
            config["metadata"] = {}
        if not isinstance(config["metadata"].get("ctos"), dict):
            config["metadata"]["ctos"] = {}

        if requires_app is not ...:
            config["metadata"]["ctos"]["requires_app"] = requires_app
        if mcp_servers is not ...:
            if mcp_servers is None:
                config["metadata"]["ctos"].pop("mcp_servers", None)
            else:
                config["metadata"]["ctos"]["mcp_servers"] = " ".join(mcp_servers)

        # 寫回 SKILL.md
        fm_text = yaml.dump(
            config, allow_unicode=True, default_flow_style=False, sort_keys=False
        ).strip()
        skill_md_path.write_text(
            f"---\n{fm_text}\n---\n\n{body}\n",
            encoding="utf-8",
        )

        logger.info(f"更新 skill metadata: {name}")
        await self.reload_skills()
        return True

    async def remove_skill(self, name: str) -> bool:
        """移除 skill 目錄。

        Returns:
            True if removed
        """
        await self.load_skills()
        if name not in self._skills:
            return False

        import shutil
        skill_dir = self._skill_dirs.get(name)
        if not skill_dir:
            return False
        if not skill_dir.is_dir():
            return False

        # 安全檢查：確保在受信任的 skills roots 下
        if not self._is_within_skill_roots(skill_dir):
            return False

        shutil.rmtree(skill_dir)
        logger.info(f"移除 skill: {name}")
        await self.reload_skills()
        return True

    async def get_skill_file(self, name: str, file_path: str) -> str | None:
        """讀取 skill 的檔案內容（references/ scripts/ assets/ 下）。"""
        await self.load_skills()
        skill = self._skills.get(name)
        if not skill:
            return None

        # 只允許存取 references/ scripts/ assets/ 下的檔案
        allowed_prefixes = ("references/", "scripts/", "assets/")
        if not any(file_path.startswith(p) for p in allowed_prefixes):
            return None

        skill_dir = self._skill_dirs.get(name)
        if not skill_dir:
            return None

        full_path = skill_dir / file_path
        if not full_path.is_file():
            return None

        # 安全檢查：不允許路徑穿越
        try:
            full_path.resolve().relative_to(skill_dir.resolve())
        except ValueError:
            return None
        return full_path.read_text(encoding="utf-8")

    # === Script Runner 相關方法 ===

    async def has_scripts(self, skill_name: str) -> bool:
        """檢查 skill 是否有 scripts/ 目錄"""
        await self.load_skills()
        skill = self._skills.get(skill_name)
        if not skill:
            return False
        return bool(skill.scripts)

    async def get_script_path(self, skill_name: str, script_name: str) -> Path | None:
        """取得 script 的完整路徑（含路徑穿越驗證）"""
        await self.load_skills()
        if skill_name not in self._skills:
            return None

        # 驗證 script_name 格式（跨平台路徑分隔符檢查）
        if not script_name or any(p in script_name for p in ("..", os.path.sep, os.path.altsep) if p):
            return None

        skill_dir = self._skill_dirs.get(skill_name)
        if not skill_dir:
            return None

        scripts_dir = skill_dir / "scripts"
        if not scripts_dir.is_dir():
            return None

        for ext in (".py", ".sh"):
            path = scripts_dir / f"{script_name}{ext}"
            if path.is_file():
                try:
                    path.resolve().relative_to(scripts_dir.resolve())
                except ValueError:
                    return None
                return path
        return None

    async def get_scripts_info(self, skill_name: str) -> list[dict]:
        """取得 skill 的所有 script 資訊（name, description）"""
        await self.load_skills()
        if skill_name not in self._skills:
            return []

        skill_dir = self._skill_dirs.get(skill_name)
        if not skill_dir:
            return []

        from .script_runner import ScriptRunner
        runner = ScriptRunner(skill_dir.parent)
        return runner.list_scripts(skill_name)

    async def get_all_script_skills(self) -> list[str]:
        """取得所有有 scripts/ 的 skill 名稱"""
        await self.load_skills()
        return [
            name for name, skill in self._skills.items()
            if skill.scripts
        ]

    async def get_script_fallback_map(self, skill_name: str) -> dict[str, str]:
        """取得 script -> MCP tool fallback 對應表。"""
        await self.load_skills()
        skill = self._skills.get(skill_name)
        if not skill:
            return {}

        ctos_meta = (skill.metadata or {}).get("ctos") or {}
        raw_mapping = ctos_meta.get("script_mcp_fallback") or {}
        if not isinstance(raw_mapping, dict):
            return {}

        mapping: dict[str, str] = {}
        for script_name, tool_name in raw_mapping.items():
            if not isinstance(script_name, str) or not isinstance(tool_name, str):
                continue
            if script_name and tool_name:
                mapping[script_name] = tool_name
        return mapping

    # 禁止 skill 存取的敏感環境變數
    _ENV_BLOCKLIST = frozenset({
        "DATABASE_URL", "DB_PASSWORD", "DB_HOST", "DB_USER",
        "SECRET_KEY", "BOT_SECRET_KEY", "JWT_SECRET",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "NAS_PASSWORD", "NAS_USER",
        "LINE_CHANNEL_SECRET", "LINE_CHANNEL_ACCESS_TOKEN",
        "TELEGRAM_BOT_TOKEN",
    })

    def get_skill_env_overrides(self, skill: "Skill") -> dict[str, str]:
        """從 SKILL.md metadata.openclaw.requires.env 取得需要繼承的 .env 變數

        有 blocklist 防止 skill 存取敏感變數。
        """
        env = {}
        metadata = skill.metadata or {}
        openclaw_meta = metadata.get("openclaw") or {}
        requires = openclaw_meta.get("requires") or {}
        env_keys = requires.get("env") or []

        def _process_key(key: str, is_primary: bool = False) -> None:
            log_source = f"primaryEnv '{key}'" if is_primary else f"環境變數 '{key}'"
            if key.upper() in self._ENV_BLOCKLIST:
                logger.warning(f"Skill '{skill.name}' 請求的 {log_source} 被封鎖，已拒絕")
                return
            val = os.environ.get(key)
            if val:
                env[key] = val
            else:
                logger.warning(f"Skill '{skill.name}' 需要的 {log_source} 未設定")

        for key in env_keys:
            _process_key(key)

        # primaryEnv 也繼承（同樣受 blocklist 限制）
        primary = openclaw_meta.get("primaryEnv")
        if primary and primary not in env:
            _process_key(primary, is_primary=True)

        return env

    # 向下相容別名
    async def get_skill_reference(self, name: str, ref_path: str) -> str | None:
        """讀取 skill 的 reference 檔案（向下相容）。"""
        if not ref_path.startswith("references/"):
            ref_path = f"references/{ref_path}"
        return await self.get_skill_file(name, ref_path)


@lru_cache(maxsize=1)
def get_skill_manager() -> SkillManager:
    """取得全域 SkillManager（線程安全 singleton）"""
    return SkillManager()
