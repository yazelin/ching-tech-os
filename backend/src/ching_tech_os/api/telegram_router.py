"""Telegram Bot API 路由

包含：
- Webhook 端點（接收 Telegram 訊息）
- 啟動時自動設定 Webhook URL
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from telegram import Update

from ..config import settings
from ..services.bot_telegram.adapter import TelegramBotAdapter
from ..services.bot_telegram.handler import handle_update

logger = logging.getLogger("telegram_router")

router = APIRouter(tags=["Bot-Telegram"])

# 延遲初始化 adapter（需要 token）
_adapter: TelegramBotAdapter | None = None


def _get_adapter() -> TelegramBotAdapter:
    """取得或建立 TelegramBotAdapter"""
    global _adapter
    if _adapter is None:
        if not settings.telegram_bot_token:
            raise HTTPException(status_code=503, detail="Telegram Bot 未設定")
        _adapter = TelegramBotAdapter(token=settings.telegram_bot_token)
    return _adapter


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Telegram Webhook 端點

    接收並處理 Telegram Bot API 發送的 Update。
    透過 X-Telegram-Bot-Api-Secret-Token header 驗證來源。
    """
    # 驗證 secret token
    if settings.telegram_webhook_secret:
        secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret_header != settings.telegram_webhook_secret:
            logger.warning("Telegram Webhook secret 驗證失敗")
            raise HTTPException(status_code=403, detail="Invalid secret token")

    # 解析 Update
    try:
        body = await request.json()
        update = Update.de_json(body, _get_adapter().bot)
    except Exception as e:
        logger.error(f"解析 Telegram Update 失敗: {e}")
        raise HTTPException(status_code=400, detail="Invalid update body")

    # 背景處理
    adapter = _get_adapter()
    background_tasks.add_task(handle_update, update, adapter)

    return {"status": "ok"}


async def setup_telegram_webhook() -> None:
    """設定 Telegram Webhook URL

    在應用程式啟動時呼叫，向 Telegram 註冊 webhook。
    """
    if not settings.telegram_bot_token:
        logger.info("Telegram Bot Token 未設定，跳過 webhook 設定")
        return

    adapter = _get_adapter()
    await adapter.ensure_bot_info()
    webhook_url = f"{settings.public_url}/api/bot/telegram/webhook"

    try:
        kwargs = {"url": webhook_url}
        if settings.telegram_webhook_secret:
            kwargs["secret_token"] = settings.telegram_webhook_secret

        result = await adapter.bot.set_webhook(**kwargs)
        if result:
            logger.info(f"Telegram Webhook 已設定: {webhook_url}")
        else:
            logger.error("Telegram Webhook 設定失敗")
    except Exception as e:
        logger.error(f"設定 Telegram Webhook 時發生錯誤: {e}")

    # 通知管理員 Bot 已上線
    await _notify_admin_startup(adapter)


async def _notify_admin_startup(adapter: TelegramBotAdapter) -> None:
    """啟動時通知管理員"""
    if not settings.telegram_admin_chat_id:
        return

    try:
        bot_info = await adapter.bot.get_me()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await adapter.bot.send_message(
            chat_id=settings.telegram_admin_chat_id,
            text=(
                f"🟢 <b>CTOS Bot 已上線</b>\n\n"
                f"🤖 @{bot_info.username}\n"
                f"🕐 {now}"
            ),
            parse_mode="HTML",
        )
        logger.info("已通知管理員 Telegram Bot 啟動")
    except Exception as e:
        logger.warning(f"無法通知管理員: {e}")
