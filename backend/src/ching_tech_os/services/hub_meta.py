"""共用的 Hub meta 工具函式（ClawHub / SkillHub 共用）"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


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
