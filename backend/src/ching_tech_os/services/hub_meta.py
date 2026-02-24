"""共用的 Hub meta 工具函式（ClawHub / SkillHub 共用）"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def _validate_contributes(config: dict, skill_name: str = "") -> dict:
    """驗證 contributes 內容，必要時降級忽略錯誤欄位。"""
    contributes = config.get("contributes")
    if not isinstance(contributes, dict):
        return config

    app = contributes.get("app")
    if app is not None:
        if not isinstance(app, dict):
            logger.warning("Skill '%s' 的 contributes.app 格式錯誤，已忽略", skill_name or "unknown")
            contributes.pop("app", None)
        else:
            missing = [key for key in ("id", "name", "icon") if not app.get(key)]
            if missing:
                logger.warning(
                    "Skill '%s' 的 contributes.app 缺少欄位 %s，已忽略 app 宣告",
                    skill_name or "unknown",
                    ",".join(missing),
                )
                contributes.pop("app", None)

    config["contributes"] = contributes
    return config


def parse_skill_md(text: str, *, skill_name: str = "") -> tuple[dict, str]:
    """解析 SKILL.md frontmatter，並驗證 contributes。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    if not isinstance(fm, dict):
        fm = {}
    fm = _validate_contributes(fm, skill_name=skill_name)
    body = m.group(2).strip()
    return fm, body


def write_meta(
    dest: Path,
    slug: str,
    version: str,
    source: str,
    owner: str | None = None,
) -> None:
    """寫入 _meta.json 到 skill 目錄

    Args:
        dest: skill 目錄
        slug: skill slug
        version: 版本號
        source: 來源標籤（"clawhub" 或 "skillhub"）
        owner: 擁有者 handle
    """
    meta = {
        "slug": slug,
        "version": version,
        "source": source,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "owner": owner or "",
    }
    meta_path = dest / "_meta.json"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"寫入 _meta.json: {meta_path}")


def read_meta(skill_dir: Path) -> dict | None:
    """讀取 skill 目錄中的 _meta.json

    Args:
        skill_dir: skill 目錄

    Returns:
        _meta.json 內容字典，或 None（檔案不存在）
    """
    meta_path = skill_dir / "_meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"讀取 _meta.json 失敗: {meta_path}: {e}")
        return None
