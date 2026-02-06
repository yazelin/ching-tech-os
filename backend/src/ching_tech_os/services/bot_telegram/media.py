"""Telegram Bot 媒體處理

下載 Telegram 圖片和檔案，儲存到 NAS 並記錄到 bot_files。
"""

import logging
from datetime import datetime

from telegram import Bot, Message

from ..bot_line import save_file_record, save_to_nas

logger = logging.getLogger("bot_telegram.media")

PLATFORM_TYPE = "telegram"


def _generate_telegram_nas_path(
    file_type: str,
    message_id: int,
    chat_id: str,
    is_group: bool,
    file_name: str | None = None,
    ext: str = "",
) -> str:
    """生成 Telegram 檔案的 NAS 路徑

    路徑格式：
    - 群組：telegram/groups/{chat_id}/{type}s/{date}/{message_id}.{ext}
    - 個人：telegram/users/{chat_id}/{type}s/{date}/{message_id}.{ext}
    """
    prefix = f"groups/{chat_id}" if is_group else f"users/{chat_id}"
    date_str = datetime.now().strftime("%Y-%m-%d")
    subdir = f"{file_type}s"

    if file_name and file_type == "file":
        safe_name = file_name.replace("/", "_").replace("\\", "_")
        filename = f"{message_id}_{safe_name}"
    else:
        filename = f"{message_id}{ext}"

    return f"telegram/{prefix}/{subdir}/{date_str}/{filename}"


async def download_telegram_photo(
    bot: Bot,
    message: Message,
    message_uuid: str,
    chat_id: str,
    is_group: bool,
) -> str | None:
    """下載 Telegram 圖片並儲存到 NAS

    Args:
        bot: Telegram Bot 物件
        message: Telegram Message 物件
        message_uuid: bot_messages 的 UUID
        chat_id: chat ID
        is_group: 是否為群組

    Returns:
        NAS 路徑，失敗回傳 None
    """
    if not message.photo:
        return None

    # 取得最高解析度的圖片
    photo = message.photo[-1]

    try:
        # 下載圖片
        file = await bot.get_file(photo.file_id)
        content = await file.download_as_bytearray()
        content = bytes(content)

        # 生成 NAS 路徑
        nas_path = _generate_telegram_nas_path(
            file_type="image",
            message_id=message.message_id,
            chat_id=chat_id,
            is_group=is_group,
            ext=".jpg",
        )

        # 儲存到 NAS
        success = await save_to_nas(nas_path, content)
        if not success:
            logger.error(f"儲存圖片到 NAS 失敗: {nas_path}")
            return None

        # 記錄到 bot_files
        await save_file_record(
            message_uuid=message_uuid,
            file_type="image",
            file_size=photo.file_size,
            mime_type="image/jpeg",
            nas_path=nas_path,
        )

        logger.info(f"已儲存 Telegram 圖片: {nas_path}")
        return nas_path

    except Exception as e:
        logger.error(f"下載 Telegram 圖片失敗: {e}", exc_info=True)
        return None


async def download_telegram_document(
    bot: Bot,
    message: Message,
    message_uuid: str,
    chat_id: str,
    is_group: bool,
) -> str | None:
    """下載 Telegram 檔案並儲存到 NAS

    Args:
        bot: Telegram Bot 物件
        message: Telegram Message 物件
        message_uuid: bot_messages 的 UUID
        chat_id: chat ID
        is_group: 是否為群組

    Returns:
        NAS 路徑，失敗回傳 None
    """
    doc = message.document
    if not doc:
        return None

    try:
        # 下載檔案
        file = await bot.get_file(doc.file_id)
        content = await file.download_as_bytearray()
        content = bytes(content)

        file_name = doc.file_name or "unknown"
        ext = ""
        if "." in file_name:
            ext = "." + file_name.rsplit(".", 1)[-1].lower()

        # 生成 NAS 路徑
        nas_path = _generate_telegram_nas_path(
            file_type="file",
            message_id=message.message_id,
            chat_id=chat_id,
            is_group=is_group,
            file_name=file_name,
            ext=ext,
        )

        # 儲存到 NAS
        success = await save_to_nas(nas_path, content)
        if not success:
            logger.error(f"儲存檔案到 NAS 失敗: {nas_path}")
            return None

        # 記錄到 bot_files
        await save_file_record(
            message_uuid=message_uuid,
            file_type="file",
            file_name=file_name,
            file_size=doc.file_size,
            mime_type=doc.mime_type,
            nas_path=nas_path,
        )

        logger.info(f"已儲存 Telegram 檔案: {file_name} -> {nas_path}")
        return nas_path

    except Exception as e:
        logger.error(f"下載 Telegram 檔案失敗: {e}", exc_info=True)
        return None
