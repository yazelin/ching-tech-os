"""應用程式設定"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 載入根目錄的 .env（應用程式設定）
_project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(_project_root / ".env")


class Settings:
    """應用程式設定"""

    # 前端目錄
    frontend_dir: str = "/home/ct/SDD/ching-tech-os/frontend"

    # NAS 設定
    nas_host: str = "192.168.11.50"
    nas_port: int = 445

    # 測試帳號（開發用）
    test_username: str = "yazelin"
    test_password: str = "REMOVED_PASSWORD"

    # 資料庫設定
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "ching_tech"
    db_password: str = "REMOVED_PASSWORD"
    db_name: str = "ching_tech_os"

    # Session 設定
    session_ttl_hours: int = 8
    session_cleanup_interval_minutes: int = 10

    # 知識庫 NAS 設定
    knowledge_nas_host: str = "192.168.11.50"
    knowledge_nas_share: str = "擎添開發"
    knowledge_nas_path: str = "ching-tech-os/knowledge"
    knowledge_nas_user: str = "yazelin"
    knowledge_nas_password: str = "REMOVED_PASSWORD"

    # 專案管理 NAS 設定
    project_nas_host: str = "192.168.11.50"
    project_nas_share: str = "擎添開發"
    project_nas_path: str = "ching-tech-os/projects"
    project_nas_user: str = "yazelin"
    project_nas_password: str = "REMOVED_PASSWORD"

    # 專案附件本機儲存路徑
    project_attachments_path: str = "/home/ct/SDD/ching-tech-os/data/projects/attachments"

    # Line Bot 設定（從環境變數載入）
    line_channel_secret: str = os.getenv("LINE_CHANNEL_SECRET", "")
    line_channel_access_token: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_files_nas_path: str = "ching-tech-os/linebot/files"
    # Bot 觸發名稱（用於群組 @ 觸發，檢查訊息是否包含 @名稱）
    line_bot_trigger_names: list[str] = [
        "ChingTech 擎添工業",  # Line 自動填入的完整名稱
        "ChingTech",           # 簡稱
        "擎添",                # 中文簡稱
        "ctos",                # 系統簡稱
    ]

    # CORS 設定（credentials=True 時不能用 "*"）
    cors_origins: list[str] = [
        "http://localhost:8080",
        "http://localhost:8088",
        "http://0.0.0.0:8080",
        "http://0.0.0.0:8088",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8088",
    ]

    @property
    def database_url(self) -> str:
        """同步 database URL (for Alembic/SQLAlchemy)"""
        return f"postgresql+psycopg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def async_database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
