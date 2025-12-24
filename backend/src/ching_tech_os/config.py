"""應用程式設定

所有敏感設定從環境變數讀取，請確保 .env 檔案正確設定。
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# 載入根目錄的 .env（應用程式設定）
_project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(_project_root / ".env")

logger = logging.getLogger(__name__)


def _get_env(key: str, default: str = "", required: bool = False) -> str:
    """取得環境變數，可設定是否必要"""
    value = os.getenv(key, default)
    if required and not value:
        logger.warning(f"環境變數 {key} 未設定，相關功能可能無法正常運作")
    return value


def _get_env_int(key: str, default: int) -> int:
    """取得整數環境變數"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(f"環境變數 {key} 不是有效的整數，使用預設值 {default}")
        return default


class Settings:
    """應用程式設定"""

    # ===================
    # 管理員設定
    # ===================
    admin_username: str = _get_env("ADMIN_USERNAME", required=True)

    # ===================
    # 資料庫設定
    # ===================
    db_host: str = _get_env("DB_HOST", "localhost")
    db_port: int = _get_env_int("DB_PORT", 5432)
    db_user: str = _get_env("DB_USER", "ching_tech")
    db_password: str = _get_env("DB_PASSWORD", required=True)
    db_name: str = _get_env("DB_NAME", "ching_tech_os")

    # ===================
    # NAS 設定（統一設定，各功能共用）
    # ===================
    nas_host: str = _get_env("NAS_HOST", "192.168.11.50")
    nas_port: int = _get_env_int("NAS_PORT", 445)
    nas_user: str = _get_env("NAS_USER", required=True)
    nas_password: str = _get_env("NAS_PASSWORD", required=True)
    nas_share: str = _get_env("NAS_SHARE", "擎添開發")

    # ===================
    # Session 設定
    # ===================
    session_ttl_hours: int = _get_env_int("SESSION_TTL_HOURS", 8)
    session_cleanup_interval_minutes: int = 10

    # ===================
    # 路徑設定
    # ===================
    frontend_dir: str = _get_env("FRONTEND_DIR", "/home/ct/SDD/ching-tech-os/frontend")

    # NAS 路徑（相對於 nas_share）
    knowledge_nas_path: str = _get_env("KNOWLEDGE_NAS_PATH", "ching-tech-os/knowledge")
    project_nas_path: str = _get_env("PROJECT_NAS_PATH", "ching-tech-os/projects")
    line_files_nas_path: str = _get_env("LINEBOT_NAS_PATH", "ching-tech-os/linebot/files")

    # 本機路徑
    project_attachments_path: str = _get_env(
        "PROJECT_ATTACHMENTS_PATH",
        "/home/ct/SDD/ching-tech-os/data/projects/attachments"
    )

    # ===================
    # Line Bot 設定
    # ===================
    line_channel_secret: str = _get_env("LINE_CHANNEL_SECRET", required=True)
    line_channel_access_token: str = _get_env("LINE_CHANNEL_ACCESS_TOKEN", required=True)

    # Bot 觸發名稱（用於群組 @ 觸發，檢查訊息是否包含 @名稱）
    line_bot_trigger_names: list[str] = [
        "ChingTech 擎添工業",  # Line 自動填入的完整名稱
        "ChingTech",           # 簡稱
        "擎添",                # 中文簡稱
        "ctos",                # 系統簡稱
    ]

    # ===================
    # CORS 設定
    # ===================
    # credentials=True 時不能用 "*"
    cors_origins: list[str] = [
        "http://localhost:8080",
        "http://localhost:8088",
        "http://0.0.0.0:8080",
        "http://0.0.0.0:8088",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8088",
    ]

    # ===================
    # 相容性屬性（向後相容，使用統一的 NAS 設定）
    # ===================
    @property
    def knowledge_nas_host(self) -> str:
        return self.nas_host

    @property
    def knowledge_nas_share(self) -> str:
        return self.nas_share

    @property
    def knowledge_nas_user(self) -> str:
        return self.nas_user

    @property
    def knowledge_nas_password(self) -> str:
        return self.nas_password

    @property
    def project_nas_host(self) -> str:
        return self.nas_host

    @property
    def project_nas_share(self) -> str:
        return self.nas_share

    @property
    def project_nas_user(self) -> str:
        return self.nas_user

    @property
    def project_nas_password(self) -> str:
        return self.nas_password

    # ===================
    # 資料庫 URL
    # ===================
    @property
    def database_url(self) -> str:
        """同步 database URL (for Alembic/SQLAlchemy)"""
        return f"postgresql+psycopg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def async_database_url(self) -> str:
        """非同步 database URL"""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
