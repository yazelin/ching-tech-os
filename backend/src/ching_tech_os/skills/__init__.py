"""Skills 管理器

動態載入和管理 AI Skills，支援 SKILL.md（OpenClaw 相容）和舊版 skill.yaml + prompt.md 格式。
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

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


@dataclass
class Skill:
    """一個 AI Skill 的完整定義"""
    name: str
    description: str
    requires_app: Optional[str]  # None = 不需權限（base skill）
    tools: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    prompt: str = ""
    references: list[str] = field(default_factory=list)  # references/ 下的檔案路徑
    source: str = "native"  # native | openclaw | claude-code


class SkillManager:
    """Skills 載入和管理"""

    def __init__(self, skills_dir: Path | str | None = None):
        self._skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR
        self._skills: dict[str, Skill] = {}
        self._loaded = False
        self._load_lock = asyncio.Lock()

    async def load_skills(self) -> None:
        """掃描 skills 目錄，載入所有 skill 定義（async-safe）"""
        async with self._load_lock:
            if self._loaded:
                return
            await asyncio.to_thread(self._load_skills_sync)

    def _load_skill_from_skill_md(self, skill_dir: Path) -> Skill | None:
        """從 SKILL.md 載入（OpenClaw 相容格式）"""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        text = skill_md.read_text(encoding="utf-8")
        config, body = _parse_skill_md(text)
        if not config:
            logger.warning(f"SKILL.md 無 frontmatter: {skill_dir}")
            return None

        # 掃描 references/ 目錄
        refs = []
        refs_dir = skill_dir / "references"
        if refs_dir.is_dir():
            refs = sorted(
                str(f.relative_to(skill_dir))
                for f in refs_dir.rglob("*")
                if f.is_file()
            )

        return Skill(
            name=config.get("name", skill_dir.name),
            description=config.get("description", ""),
            requires_app=config.get("requires_app"),
            tools=config.get("tools", []),
            mcp_servers=config.get("mcp_servers", []),
            prompt=body,
            references=refs,
            source="native",
        )

    def _load_skill_from_yaml(self, skill_dir: Path) -> Skill | None:
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

        return Skill(
            name=config.get("name", skill_dir.name),
            description=config.get("description", ""),
            requires_app=config.get("requires_app"),
            tools=config.get("tools", []),
            mcp_servers=config.get("mcp_servers", []),
            prompt=prompt,
            source="native",
        )

    def _load_skills_sync(self) -> None:
        """同步載入 skills（在 thread pool 中執行，避免 blocking event loop）"""
        if not self._skills_dir.exists():
            logger.warning(f"Skills 目錄不存在: {self._skills_dir}")
            self._loaded = True
            return

        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue

            try:
                # 優先讀 SKILL.md，否則回退到 skill.yaml + prompt.md
                skill = self._load_skill_from_skill_md(skill_dir)
                if skill is None:
                    skill = self._load_skill_from_yaml(skill_dir)
                if skill is None:
                    continue

                self._skills[skill.name] = skill
                refs_info = f", {len(skill.references)} refs" if skill.references else ""
                logger.debug(
                    f"載入 skill: {skill.name} ({len(skill.tools)} tools{refs_info})"
                )

            except (yaml.YAMLError, OSError) as e:
                logger.error(f"載入 skill 失敗 {skill_dir}: {e}")

        self._loaded = True
        logger.info(f"共載入 {len(self._skills)} 個 skills")

    def import_openclaw_skill(self, skill_path: Path) -> Path:
        """從 OpenClaw SKILL.md 匯入，建立 CTOS 相容的 skill 目錄。

        OpenClaw 的 SKILL.md 只有 name + description，沒有 tools/mcp_servers/requires_app。
        匯入後管理員需手動設定權限和工具白名單。

        Args:
            skill_path: OpenClaw skill 目錄（含 SKILL.md）

        Returns:
            匯入後的 skill 目錄路徑
        """
        src_skill_md = skill_path / "SKILL.md"
        if not src_skill_md.exists():
            raise FileNotFoundError(f"找不到 SKILL.md: {skill_path}")

        text = src_skill_md.read_text(encoding="utf-8")
        config, body = _parse_skill_md(text)

        name = config.get("name", skill_path.name)
        dest_dir = self._skills_dir / name
        dest_dir.mkdir(parents=True, exist_ok=True)

        # 補上 CTOS 擴充欄位
        if "requires_app" not in config:
            config["requires_app"] = None
        if "tools" not in config:
            config["tools"] = []
        if "mcp_servers" not in config:
            config["mcp_servers"] = []

        # 寫出 SKILL.md
        fm_text = yaml.dump(config, allow_unicode=True, default_flow_style=False).strip()
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

        # 重設載入狀態，下次存取時重新掃描
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
            tools.extend(skill.tools)
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

    async def get_skill_reference(self, name: str, ref_path: str) -> str | None:
        """讀取 skill 的 reference 檔案內容"""
        await self.load_skills()
        skill = self._skills.get(name)
        if not skill:
            return None
        full_path = self._skills_dir / name / ref_path
        if not full_path.is_file():
            return None
        # 安全檢查：不允許路徑穿越
        try:
            full_path.resolve().relative_to((self._skills_dir / name).resolve())
        except ValueError:
            return None
        return full_path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def get_skill_manager() -> SkillManager:
    """取得全域 SkillManager（線程安全 singleton）"""
    return SkillManager()
