"""Telegram Bot Polling 服務

以 long polling 模式從 Telegram API 拉取訊息更新，
取代 webhook 被動接收模式，不受伺服器 IP 變動影響。
"""

import asyncio
import logging
from datetime import datetime

from telegram import Update
from telegram.request import HTTPXRequest

from ...config import settings
from .adapter import TelegramBotAdapter
from .handler import handle_update

logger = logging.getLogger("bot_telegram.polling")

# Long polling 參數
POLL_TIMEOUT = 30  # getUpdates timeout（秒），Telegram 建議 > 0
MAX_RETRY_DELAY = 60  # 最大重試間隔（秒）


async def run_telegram_polling() -> None:
    """執行 Telegram polling 迴圈

    啟動時先刪除 webhook（polling 與 webhook 不能同時使用），
    然後以 long polling 持續拉取更新。

    此函式設計為在 asyncio.Task 中執行，
    透過 task.cancel() 優雅停止。
    """
    if not settings.telegram_bot_token:
        logger.info("Telegram Bot Token 未設定，跳過 polling")
        return

    adapter = TelegramBotAdapter(token=settings.telegram_bot_token)
    await adapter.ensure_bot_info()

    # 建立專用 Bot 實例，read_timeout 必須大於 POLL_TIMEOUT
    # （adapter.bot 的預設 timeout 太短，不適合 long polling）
    from telegram import Bot
    bot = Bot(
        token=settings.telegram_bot_token,
        request=HTTPXRequest(read_timeout=POLL_TIMEOUT + 10),
    )

    # 刪除現有 webhook，確保 getUpdates 可用
    try:
        await bot.delete_webhook()
        logger.info("已刪除 Telegram webhook，切換為 polling 模式")
    except Exception as e:
        logger.error(f"刪除 webhook 失敗: {e}")

    # 通知管理員 Bot 已上線（polling 模式）
    await _notify_admin_startup(adapter)

    # Polling 迴圈
    offset: int | None = None
    retry_delay = 1  # 初始重試間隔（秒）

    try:
        while True:
            try:
                updates = await bot.get_updates(
                    offset=offset,
                    timeout=POLL_TIMEOUT,
                    allowed_updates=["message"],
                )

                # 成功取得更新，重置重試間隔
                retry_delay = 1

                for update in updates:
                    # 更新 offset（下次從這之後開始）
                    offset = update.update_id + 1

                    # 背景處理每則訊息（與 webhook 行為一致）
                    asyncio.create_task(
                        _safe_handle_update(update, adapter)
                    )

            except asyncio.CancelledError:
                raise  # 讓外層捕獲以優雅停止
            except Exception as e:
                logger.error(f"Polling 錯誤: {e}")
                # 指數退避重試
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)

    except asyncio.CancelledError:
        logger.info("Telegram polling 已停止")


async def _safe_handle_update(update: Update, adapter: TelegramBotAdapter) -> None:
    """安全地處理 update，捕獲所有例外避免影響 polling 迴圈"""
    try:
        await handle_update(update, adapter)
    except Exception as e:
        logger.error(f"處理 Update {update.update_id} 失敗: {e}", exc_info=True)


async def _notify_admin_startup(adapter: TelegramBotAdapter) -> None:
    """啟動時通知管理員（polling 模式）"""
    if not settings.telegram_admin_chat_id:
        return

    try:
        bot_info = await adapter.bot.get_me()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await adapter.bot.send_message(
            chat_id=settings.telegram_admin_chat_id,
            text=(
                f"🟢 <b>CTOS Bot 已上線</b>（Polling 模式）\n\n"
                f"🤖 @{bot_info.username}\n"
                f"🕐 {now}"
            ),
            parse_mode="HTML",
        )
        logger.info("已通知管理員 Telegram Bot 啟動（polling 模式）")
    except Exception as e:
        logger.warning(f"無法通知管理員: {e}")
