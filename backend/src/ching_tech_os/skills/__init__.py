"""Skills 管理器

動態載入和管理 AI Skills，取代 bot/agents.py 的硬編碼 prompt。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Skills 目錄
SKILLS_DIR = Path(__file__).parent


@dataclass
class Skill:
    """一個 AI Skill 的完整定義"""
    name: str
    description: str
    requires_app: Optional[str]  # None = 不需權限（base skill）
    tools: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    prompt: str = ""


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

    def _load_skills_sync(self) -> None:
        """同步載入 skills（在 thread pool 中執行，避免 blocking event loop）"""
        if not self._skills_dir.exists():
            logger.warning(f"Skills 目錄不存在: {self._skills_dir}")
            self._loaded = True
            return

        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue

            skill_yaml = skill_dir / "skill.yaml"
            prompt_md = skill_dir / "prompt.md"

            if not skill_yaml.exists():
                continue

            try:
                with open(skill_yaml) as f:
                    config = yaml.safe_load(f)

                prompt = ""
                if prompt_md.exists():
                    prompt = prompt_md.read_text(encoding="utf-8")

                skill = Skill(
                    name=config.get("name", skill_dir.name),
                    description=config.get("description", ""),
                    requires_app=config.get("requires_app"),
                    tools=config.get("tools", []),
                    mcp_servers=config.get("mcp_servers", []),
                    prompt=prompt,
                )
                self._skills[skill.name] = skill
                logger.debug(f"載入 skill: {skill.name} ({len(skill.tools)} tools)")

            except (OSError, yaml.YAMLError, KeyError, TypeError) as e:
                logger.error(f"載入 skill 失敗 {skill_dir}: {e}")

        self._loaded = True
        logger.info(f"共載入 {len(self._skills)} 個 skills")

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


# 全域 singleton
_skill_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    """取得全域 SkillManager"""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager
