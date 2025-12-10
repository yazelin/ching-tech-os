"""應用程式設定"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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

    model_config = {"env_prefix": "CHING_TECH_"}


settings = Settings()
