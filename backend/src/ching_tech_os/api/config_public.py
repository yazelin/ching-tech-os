"""配置 API

/health 無需認證；/apps 會洩露已啟用模組與 skill 清單，需登入才能存取。
"""

from fastapi import APIRouter, Depends

from ..models.auth import SessionData
from ..modules import get_enabled_app_manifests
from .auth import get_session_from_token_or_query

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/health")
async def config_health():
    """配置 API 健康檢查"""
    return {"status": "ok"}


@router.get("/apps")
async def config_apps(
    session: SessionData = Depends(get_session_from_token_or_query),
):
    """回傳啟用模組的桌面應用清單（需登入，含 skill 貢獻的 loader 路徑，避免未登入者偵察已裝模組）。"""
    return get_enabled_app_manifests()
