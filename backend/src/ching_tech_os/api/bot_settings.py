"""Bot 設定管理 API（管理員限定）

端點：
- GET    /api/admin/bot-settings/{platform}       取得設定狀態
- PUT    /api/admin/bot-settings/{platform}       更新憑證
- DELETE /api/admin/bot-settings/{platform}       清除憑證
- POST   /api/admin/bot-settings/{platform}/test  測試連線
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..services.session import SessionData
from ..api.auth import get_current_session
from ..services.bot_settings import (
    SUPPORTED_PLATFORMS,
    get_bot_credentials_status,
    get_bot_credentials,
    update_bot_credentials,
    delete_bot_credentials,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/bot-settings", tags=["Bot Settings"])


# ============================================================
# 權限檢查
# ============================================================

async def require_admin(session: SessionData = Depends(get_current_session)) -> SessionData:
    """要求管理員權限"""
    if session.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理員權限")
    return session


def _validate_platform(platform: str) -> str:
    """驗證平台名稱"""
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支援的平台: {platform}")
    return platform


# ============================================================
# 請求/回應模型
# ============================================================

class LineBotCredentials(BaseModel):
    """Line Bot 憑證"""
    channel_secret: str = ""
    channel_access_token: str = ""


class TelegramBotCredentials(BaseModel):
    """Telegram Bot 憑證"""
    bot_token: str = ""
    webhook_secret: str = ""
    admin_chat_id: str = ""


class FieldStatus(BaseModel):
    """欄位狀態"""
    has_value: bool
    masked_value: str
    source: str  # database / env / none
    updated_at: str | None


class BotSettingsStatusResponse(BaseModel):
    """Bot 設定狀態回應"""
    platform: str
    fields: dict[str, FieldStatus]


class BotSettingsDeleteResponse(BaseModel):
    """刪除回應"""
    deleted: int


class TestConnectionResponse(BaseModel):
    """連線測試回應"""
    success: bool
    message: str


# ============================================================
# API 端點
# ============================================================

@router.get("/{platform}", response_model=BotSettingsStatusResponse)
async def get_settings_status(
    platform: str,
    session: SessionData = Depends(require_admin),
):
    """取得 Bot 設定狀態（遮罩顯示）"""
    _validate_platform(platform)
    return await get_bot_credentials_status(platform)


@router.put("/{platform}")
async def update_settings(
    platform: str,
    body: dict,
    session: SessionData = Depends(require_admin),
):
    """更新 Bot 憑證"""
    _validate_platform(platform)

    # 過濾空值（不更新空字串的欄位）
    credentials = {k: v for k, v in body.items() if v}
    if not credentials:
        raise HTTPException(status_code=400, detail="至少需要一個非空欄位")

    await update_bot_credentials(platform, credentials)
    return {"success": True, "message": f"{platform} 設定已更新"}


@router.delete("/{platform}", response_model=BotSettingsDeleteResponse)
async def delete_settings(
    platform: str,
    session: SessionData = Depends(require_admin),
):
    """清除 Bot 憑證（回復到使用環境變數）"""
    _validate_platform(platform)
    count = await delete_bot_credentials(platform)
    return {"deleted": count}


@router.post("/{platform}/test", response_model=TestConnectionResponse)
async def test_connection(
    platform: str,
    session: SessionData = Depends(require_admin),
):
    """測試 Bot 連線"""
    _validate_platform(platform)

    try:
        credentials = await get_bot_credentials(platform)

        if platform == "line":
            return await _test_line_connection(credentials)
        elif platform == "telegram":
            return await _test_telegram_connection(credentials)

    except Exception as e:
        logger.error(f"測試 {platform} 連線失敗: {e}")
        return TestConnectionResponse(success=False, message=f"連線失敗: {str(e)}")


async def _test_line_connection(credentials: dict) -> TestConnectionResponse:
    """測試 Line Bot 連線"""
    token = credentials.get("channel_access_token", "")
    if not token:
        return TestConnectionResponse(success=False, message="未設定 Channel Access Token")

    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.line.me/v2/bot/info",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )

    if resp.status_code == 200:
        data = resp.json()
        bot_name = data.get("displayName", "未知")
        return TestConnectionResponse(success=True, message=f"連線成功！Bot 名稱: {bot_name}")
    else:
        return TestConnectionResponse(success=False, message=f"API 回應 {resp.status_code}: {resp.text[:200]}")


async def _test_telegram_connection(credentials: dict) -> TestConnectionResponse:
    """測試 Telegram Bot 連線"""
    token = credentials.get("bot_token", "")
    if not token:
        return TestConnectionResponse(success=False, message="未設定 Bot Token")

    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=10,
        )

    if resp.status_code == 200:
        data = resp.json()
        if data.get("ok"):
            bot_name = data["result"].get("first_name", "未知")
            bot_username = data["result"].get("username", "")
            return TestConnectionResponse(
                success=True,
                message=f"連線成功！Bot: {bot_name} (@{bot_username})",
            )

    return TestConnectionResponse(success=False, message=f"API 回應 {resp.status_code}: {resp.text[:200]}")
