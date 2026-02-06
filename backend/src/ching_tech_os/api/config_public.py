"""公開配置 API

無需認證即可存取的系統配置端點。
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/health")
async def config_health():
    """配置 API 健康檢查"""
    return {"status": "ok"}
