"""CLI 設定檔管理

設定存於 ~/.ctos/config.json（chmod 600），可用環境變數覆寫：
- CTOS_URL：服務網址
- CTOS_TOKEN：API token
- CTOS_CONFIG：設定檔路徑
"""

import json
import os
import stat
from pathlib import Path


def config_path() -> Path:
    """取得設定檔路徑"""
    custom = os.environ.get("CTOS_CONFIG")
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".ctos" / "config.json"


def load_config() -> dict:
    """載入設定檔，不存在時回傳空 dict"""
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def save_config(cfg: dict) -> None:
    """寫入設定檔並限制權限為 600"""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows 上 chmod 行為有限，略過
        pass


def get_url(cfg: dict | None = None) -> str | None:
    """取得服務網址（環境變數優先）"""
    env = os.environ.get("CTOS_URL")
    if env:
        return env.rstrip("/")
    cfg = cfg if cfg is not None else load_config()
    url = cfg.get("url")
    return url.rstrip("/") if url else None


def get_token(cfg: dict | None = None) -> str | None:
    """取得 API token（環境變數優先）"""
    env = os.environ.get("CTOS_TOKEN")
    if env:
        return env
    cfg = cfg if cfg is not None else load_config()
    return cfg.get("token")
