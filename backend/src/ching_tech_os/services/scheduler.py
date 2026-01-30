"""
ChingTech OS - 排程服務
使用 APScheduler 執行定時任務
"""

import logging
import os
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings
from ..database import get_connection

logger = logging.getLogger(__name__)

# 全域排程器實例
scheduler = AsyncIOScheduler()


async def cleanup_old_messages():
    """
    清理過期的訊息和登入記錄
    刪除超過 1 年的分區資料
    """
    logger.info("開始執行訊息清理任務...")

    try:
        async with get_connection() as conn:
            # 計算 1 年前的日期
            one_year_ago = datetime.now() - timedelta(days=365)
            cutoff_date = one_year_ago

            # 清理 messages 表中超過 1 年的資料
            deleted_messages = await conn.execute(
                """
                DELETE FROM messages
                WHERE created_at < $1
                """,
                cutoff_date
            )

            # 清理 login_records 表中超過 1 年的資料
            deleted_login_records = await conn.execute(
                """
                DELETE FROM login_records
                WHERE created_at < $1
                """,
                cutoff_date
            )

            logger.info(
                f"訊息清理完成: {deleted_messages}, {deleted_login_records}"
            )

    except Exception as e:
        logger.error(f"訊息清理失敗: {e}")


async def create_next_month_partitions():
    """
    建立下個月的分區表
    確保分區表提前存在，避免資料插入失敗
    """
    logger.info("開始建立下月分區...")

    try:
        async with get_connection() as conn:
            # 計算下個月
            today = datetime.now()
            if today.month == 12:
                next_month = datetime(today.year + 1, 1, 1)
            else:
                next_month = datetime(today.year, today.month + 1, 1)

            # 計算下下個月（分區結束邊界）
            if next_month.month == 12:
                month_after = datetime(next_month.year + 1, 1, 1)
            else:
                month_after = datetime(next_month.year, next_month.month + 1, 1)

            partition_suffix = next_month.strftime('%Y_%m')
            start_date = next_month.strftime('%Y-%m-%d')
            end_date = month_after.strftime('%Y-%m-%d')

            # 建立 messages 分區
            messages_partition = f"messages_{partition_suffix}"
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {messages_partition}
                PARTITION OF messages
                FOR VALUES FROM ('{start_date}') TO ('{end_date}')
            """)

            # 建立 login_records 分區
            login_partition = f"login_records_{partition_suffix}"
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {login_partition}
                PARTITION OF login_records
                FOR VALUES FROM ('{start_date}') TO ('{end_date}')
            """)

            logger.info(f"已建立分區: {messages_partition}, {login_partition}")

    except Exception as e:
        # 分區已存在時會拋出錯誤，這是正常的
        if "already exists" in str(e):
            logger.debug("分區已存在，跳過建立")
        else:
            logger.error(f"建立分區失敗: {e}")


async def cleanup_expired_share_links():
    """
    清理過期的分享連結
    刪除所有 expires_at < 當前時間 的連結
    """
    from .share import cleanup_expired_links

    logger.debug("開始清理過期分享連結...")

    try:
        deleted_count = await cleanup_expired_links()
        if deleted_count > 0:
            logger.info(f"清理過期分享連結: 刪除 {deleted_count} 個連結")
        else:
            logger.debug("過期分享連結清理: 無過期連結")
    except Exception as e:
        logger.error(f"清理過期分享連結失敗: {e}")


async def cleanup_linebot_temp_files():
    """
    清理 Line Bot 暫存檔（圖片和檔案）
    刪除修改時間超過 1 小時的暫存檔
    """
    temp_dirs = [
        "/tmp/bot-images",
        "/tmp/bot-files",
    ]

    one_hour_ago = time.time() - 3600  # 1 小時前
    total_deleted = 0

    for temp_dir in temp_dirs:
        if not os.path.exists(temp_dir):
            continue

        try:
            deleted_count = 0

            for filename in os.listdir(temp_dir):
                filepath = os.path.join(temp_dir, filename)
                if os.path.isfile(filepath):
                    if os.path.getmtime(filepath) < one_hour_ago:
                        os.unlink(filepath)
                        deleted_count += 1

            total_deleted += deleted_count

        except Exception as e:
            logger.error(f"清理 {temp_dir} 失敗: {e}")

    if total_deleted > 0:
        logger.info(f"清理 Line Bot 暫存檔: 刪除 {total_deleted} 個檔案")
    else:
        logger.debug("Line Bot 暫存檔清理: 無過期檔案")


async def cleanup_ai_images():
    """
    清理 AI 生成的圖片
    刪除修改時間超過 1 個月的圖片檔案
    """
    from ..config import settings

    ai_images_dir = f"{settings.linebot_local_path}/ai-images"

    if not os.path.exists(ai_images_dir):
        logger.debug(f"AI 圖片目錄不存在: {ai_images_dir}")
        return

    one_month_ago = time.time() - (30 * 24 * 3600)  # 30 天前
    deleted_count = 0
    total_size = 0

    try:
        for filename in os.listdir(ai_images_dir):
            filepath = os.path.join(ai_images_dir, filename)
            if os.path.isfile(filepath):
                if os.path.getmtime(filepath) < one_month_ago:
                    file_size = os.path.getsize(filepath)
                    os.unlink(filepath)
                    deleted_count += 1
                    total_size += file_size

        if deleted_count > 0:
            size_mb = total_size / (1024 * 1024)
            logger.info(f"清理 AI 圖片: 刪除 {deleted_count} 個檔案，釋放 {size_mb:.1f} MB")
        else:
            logger.debug("AI 圖片清理: 無過期檔案")

    except Exception as e:
        logger.error(f"清理 AI 圖片失敗: {e}")


async def check_telegram_webhook_health():
    """
    檢查 Telegram Webhook 健康狀態
    若偵測到錯誤或有 pending updates，重新設定 webhook
    """
    if not settings.telegram_bot_token:
        return

    try:
        from telegram import Bot

        bot = Bot(token=settings.telegram_bot_token)
        info = await bot.get_webhook_info()

        if info.last_error_date or info.pending_update_count > 0:
            logger.warning(
                f"Telegram Webhook 異常: "
                f"error={info.last_error_message}, "
                f"pending={info.pending_update_count}"
            )

            # 刪除並重設 webhook 以重置退避計時器
            await bot.delete_webhook()

            kwargs = {
                "url": f"{settings.public_url}/api/bot/telegram/webhook"
            }
            if settings.telegram_webhook_secret:
                kwargs["secret_token"] = settings.telegram_webhook_secret

            await bot.set_webhook(**kwargs)
            logger.info("Telegram Webhook 已重新設定")
        else:
            logger.debug("Telegram Webhook 狀態正常")

    except Exception as e:
        logger.error(f"檢查 Telegram Webhook 失敗: {e}")


def start_scheduler():
    """
    啟動排程器
    """
    # 每天凌晨 3 點執行清理任務
    scheduler.add_job(
        cleanup_old_messages,
        CronTrigger(hour=3, minute=0),
        id='cleanup_old_messages',
        name='清理過期訊息',
        replace_existing=True
    )

    # 每月 25 日凌晨 4 點建立下月分區
    scheduler.add_job(
        create_next_month_partitions,
        CronTrigger(day=25, hour=4, minute=0),
        id='create_next_month_partitions',
        name='建立下月分區',
        replace_existing=True
    )

    # 每小時清理 Line Bot 暫存檔（圖片和檔案）
    scheduler.add_job(
        cleanup_linebot_temp_files,
        IntervalTrigger(hours=1),
        id='cleanup_linebot_temp_files',
        name='清理 Line Bot 暫存',
        replace_existing=True
    )

    # 每小時清理過期分享連結
    scheduler.add_job(
        cleanup_expired_share_links,
        IntervalTrigger(hours=1),
        id='cleanup_expired_share_links',
        name='清理過期分享連結',
        replace_existing=True
    )

    # 每天凌晨 4 點清理超過 1 個月的 AI 生成圖片
    scheduler.add_job(
        cleanup_ai_images,
        CronTrigger(hour=4, minute=30),
        id='cleanup_ai_images',
        name='清理 AI 生成圖片',
        replace_existing=True
    )

    # 每 5 分鐘檢查 Telegram Webhook 健康狀態
    scheduler.add_job(
        check_telegram_webhook_health,
        IntervalTrigger(minutes=5),
        id='check_telegram_webhook_health',
        name='檢查 Telegram Webhook',
        replace_existing=True
    )

    scheduler.start()
    logger.info("排程服務已啟動")


def stop_scheduler():
    """
    停止排程器
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("排程服務已停止")
