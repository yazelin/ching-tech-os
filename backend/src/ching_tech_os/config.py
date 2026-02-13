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


def _get_env_bool(key: str, default: bool = False) -> bool:
    """取得布林環境變數"""
    value = os.getenv(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    return default


class Settings:
    """應用程式設定"""

    # ===================
    # 資料庫設定
    # ===================
    db_host: str = _get_env("DB_HOST", "localhost")
    db_port: int = _get_env_int("DB_PORT", 5432)
    db_user: str = _get_env("DB_USER", "ching_tech")
    db_password: str = _get_env("DB_PASSWORD", required=True)
    db_name: str = _get_env("DB_NAME", "ching_tech_os")

    # ===================
    # NAS 認證
    enable_nas_auth: bool = _get_env_bool("ENABLE_NAS_AUTH", True)

    # NAS 設定（統一設定，各功能共用）
    # ===================
    nas_host: str = _get_env("NAS_HOST", "192.168.11.50")
    nas_port: int = _get_env_int("NAS_PORT", 445)
    smb_connect_timeout: int = _get_env_int("SMB_CONNECT_TIMEOUT", 10)  # SMB 連線逾時（秒）
    nas_user: str = _get_env("NAS_USER", required=True)
    nas_password: str = _get_env("NAS_PASSWORD", required=True)
    nas_share: str = _get_env("NAS_SHARE", "擎添開發")

    # NAS 掛載路徑（系統功能透過此路徑存取 NAS）
    nas_mount_path: str = _get_env("NAS_MOUNT_PATH", "/mnt/nas")
    ctos_mount_path: str = _get_env("CTOS_MOUNT_PATH", "/mnt/nas/ctos")
    projects_mount_path: str = _get_env("PROJECTS_MOUNT_PATH", "/mnt/nas/projects")
    circuits_mount_path: str = _get_env("CIRCUITS_MOUNT_PATH", "/mnt/nas/circuits")

    # ===================
    # Session 設定
    # ===================
    session_ttl_hours: int = _get_env_int("SESSION_TTL_HOURS", 8)
    session_cleanup_interval_minutes: int = 10

    # ===================
    # 路徑設定
    # ===================
    project_root: str = _get_env("PROJECT_ROOT", str(_project_root))
    frontend_dir: str = _get_env("FRONTEND_DIR", "/home/ct/SDD/ching-tech-os/frontend")

    # NAS 路徑（相對於 ctos_mount_path）
    knowledge_nas_path: str = _get_env("KNOWLEDGE_NAS_PATH", "knowledge")
    project_nas_path: str = _get_env("PROJECT_NAS_PATH", "projects")
    line_files_nas_path: str = _get_env("LINEBOT_NAS_PATH", "linebot/files")

    # 本機路徑
    project_attachments_path: str = _get_env(
        "PROJECT_ATTACHMENTS_PATH",
        "/home/ct/SDD/ching-tech-os/data/projects/attachments"
    )
    knowledge_data_path: str = _get_env(
        "KNOWLEDGE_DATA_PATH",
        "/home/ct/SDD/ching-tech-os/data/knowledge"
    )

    # ===================
    # Skill 系統設定
    # ===================
    # 外部 skill 根目錄（external-first 載入）
    skill_external_root: str = _get_env(
        "SKILL_EXTERNAL_ROOT",
        str(Path.home() / "SDD/skill"),
    )
    # 工具路由策略：script-first | mcp-first
    skill_route_policy: str = _get_env("SKILL_ROUTE_POLICY", "script-first")
    # script 失敗時是否允許 fallback 到對應 MCP
    skill_script_fallback_enabled: bool = _get_env_bool(
        "SKILL_SCRIPT_FALLBACK_ENABLED",
        True,
    )

    # ===================
    # Line Bot 設定
    # ===================
    line_channel_secret: str = _get_env("LINE_CHANNEL_SECRET", required=True)
    line_channel_access_token: str = _get_env("LINE_CHANNEL_ACCESS_TOKEN", required=True)

    # Bot 憑證加密金鑰（用於加密 bot_settings 資料）
    bot_secret_key: str = _get_env("BOT_SECRET_KEY", "")

    # Bot 觸發名稱（用於群組 @ 觸發，檢查訊息是否包含 @名稱）
    line_bot_trigger_names: list[str] = [
        "ChingTech 擎添工業",  # Line 自動填入的完整名稱
        "ChingTech",           # 簡稱
        "擎添",                # 中文簡稱
        "ctos",                # 系統簡稱
    ]

    # ===================
    # Telegram Bot 設定
    # ===================
    telegram_bot_token: str = _get_env("TELEGRAM_BOT_TOKEN", "")
    telegram_webhook_secret: str = _get_env("TELEGRAM_WEBHOOK_SECRET", "")
    telegram_admin_chat_id: str = _get_env("TELEGRAM_ADMIN_CHAT_ID", "")

    # ===================
    # 公開連結設定
    # ===================
    public_url: str = _get_env("PUBLIC_URL", "https://ching-tech.ddns.net/ctos")

    # ===================
    # MD2PPT/MD2DOC 外部應用程式 URL
    # ===================
    md2ppt_url: str = _get_env("MD2PPT_URL", "https://md-2-ppt-evolution.vercel.app")
    md2doc_url: str = _get_env("MD2DOC_URL", "https://md-2-doc-evolution.vercel.app")

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
        # MD2PPT/MD2DOC 外部應用程式
        "https://md-2-ppt-evolution.vercel.app",
        "https://md-2-doc-evolution.vercel.app",
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
    # 本機路徑（透過 NAS 掛載）
    # ===================
    @property
    def knowledge_local_path(self) -> str:
        """知識庫本機路徑（透過 NAS 掛載）"""
        return f"{self.ctos_mount_path}/{self.knowledge_nas_path}"

    @property
    def project_local_path(self) -> str:
        """專案本機路徑（透過 NAS 掛載）"""
        return f"{self.ctos_mount_path}/{self.project_nas_path}"

    @property
    def linebot_local_path(self) -> str:
        """Line Bot 檔案本機路徑（透過 NAS 掛載）"""
        return f"{self.ctos_mount_path}/{self.line_files_nas_path}"

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
