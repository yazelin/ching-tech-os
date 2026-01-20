"""公開配置 API

無需認證即可存取的系統配置端點。
"""

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import settings

router = APIRouter(prefix="/api/config", tags=["config"])


class TenantModeResponse(BaseModel):
    """租戶模式回應"""

    multi_tenant_mode: bool


@router.get("/tenant-mode", response_model=TenantModeResponse)
async def get_tenant_mode() -> TenantModeResponse:
    """取得租戶模式設定

    公開端點，無需登入。用於前端判斷是否顯示租戶代碼輸入欄位。
    """
    return TenantModeResponse(multi_tenant_mode=settings.multi_tenant_mode)
