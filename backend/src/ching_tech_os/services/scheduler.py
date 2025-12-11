"""
ChingTech OS - 排程服務
使用 APScheduler 執行定時任務
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

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

    scheduler.start()
    logger.info("排程服務已啟動")


def stop_scheduler():
    """
    停止排程器
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("排程服務已停止")
