"""Bot 設定服務

管理 Line Bot / Telegram Bot 的憑證設定。
優先從資料庫讀取，若無資料則 fallback 到環境變數。
"""

import logging
from datetime import datetime, timezone

from ..config import settings
from ..database import get_connection
from ..utils.crypto import encrypt_credential, decrypt_credential, is_encrypted

logger = logging.getLogger(__name__)

# 支援的平台
SUPPORTED_PLATFORMS = {"line", "telegram"}

# 各平台的憑證欄位
PLATFORM_KEYS = {
    "line": ["channel_secret", "channel_access_token"],
    "telegram": ["bot_token", "webhook_secret", "admin_chat_id"],
}

# 需要加密儲存的欄位
ENCRYPTED_KEYS = {"channel_secret", "channel_access_token", "bot_token", "webhook_secret"}


def _get_env_fallback(platform: str, key: str) -> str:
    """從環境變數取得 fallback 值"""
    mapping = {
        ("line", "channel_secret"): settings.line_channel_secret,
        ("line", "channel_access_token"): settings.line_channel_access_token,
        ("telegram", "bot_token"): settings.telegram_bot_token,
        ("telegram", "webhook_secret"): settings.telegram_webhook_secret,
        ("telegram", "admin_chat_id"): settings.telegram_admin_chat_id,
    }
    return mapping.get((platform, key), "")


def _mask_value(value: str) -> str:
    """遮罩敏感值，只顯示前 4 和後 4 字元"""
    if not value or len(value) <= 12:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


async def get_bot_credentials(platform: str) -> dict[str, str]:
    """取得 Bot 憑證

    優先從資料庫讀取，若無則 fallback 到環境變數。

    Args:
        platform: 平台名稱（line / telegram）

    Returns:
        包含各憑證欄位的字典（明文）
    """
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"不支援的平台: {platform}")

    result = {}
    keys = PLATFORM_KEYS[platform]

    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM bot_settings WHERE platform = $1",
            platform,
        )
        db_values = {row["key"]: row["value"] for row in rows}

    for key in keys:
        db_val = db_values.get(key, "")
        if db_val:
            # 資料庫有值，解密後回傳
            if key in ENCRYPTED_KEYS and is_encrypted(db_val):
                result[key] = decrypt_credential(db_val)
            else:
                result[key] = db_val
        else:
            # fallback 到環境變數
            result[key] = _get_env_fallback(platform, key)

    return result


async def get_bot_credentials_status(platform: str) -> dict:
    """取得 Bot 憑證狀態（遮罩顯示）

    Args:
        platform: 平台名稱

    Returns:
        包含各欄位狀態的字典
    """
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"不支援的平台: {platform}")

    credentials = await get_bot_credentials(platform)
    keys = PLATFORM_KEYS[platform]

    # 檢查來源
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT key, updated_at FROM bot_settings WHERE platform = $1",
            platform,
        )
        db_keys = {row["key"]: row["updated_at"] for row in rows}

    fields = {}
    for key in keys:
        value = credentials.get(key, "")
        is_sensitive = key in ENCRYPTED_KEYS
        fields[key] = {
            "has_value": bool(value),
            "masked_value": _mask_value(value) if (value and is_sensitive) else (value if value else ""),
            "source": "database" if key in db_keys else ("env" if value else "none"),
            "updated_at": db_keys[key].isoformat() if key in db_keys else None,
        }

    return {
        "platform": platform,
        "fields": fields,
    }


async def update_bot_credentials(platform: str, credentials: dict[str, str]) -> None:
    """更新 Bot 憑證

    Args:
        platform: 平台名稱
        credentials: 欄位名稱 → 值的字典（明文）
    """
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"不支援的平台: {platform}")

    valid_keys = set(PLATFORM_KEYS[platform])
    now = datetime.now(timezone.utc)

    async with get_connection() as conn:
        for key, value in credentials.items():
            if key not in valid_keys:
                continue

            # 敏感欄位加密
            stored_value = encrypt_credential(value) if (key in ENCRYPTED_KEYS and value) else value

            await conn.execute(
                """
                INSERT INTO bot_settings (platform, key, value, updated_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (platform, key)
                DO UPDATE SET value = $3, updated_at = $4
                """,
                platform, key, stored_value, now,
            )

    logger.info(f"已更新 {platform} 憑證: {list(credentials.keys())}")


async def delete_bot_credentials(platform: str) -> int:
    """刪除 Bot 憑證

    Args:
        platform: 平台名稱

    Returns:
        刪除的記錄數
    """
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"不支援的平台: {platform}")

    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM bot_settings WHERE platform = $1",
            platform,
        )

    # result 格式: "DELETE N"
    count = int(result.split()[-1])
    logger.info(f"已刪除 {platform} 憑證: {count} 筆")
    return count


# 便利函數（供測試和其他模組使用）

async def get_line_credentials() -> dict[str, str]:
    """取得 Line Bot 憑證"""
    return await get_bot_credentials("line")


async def get_telegram_credentials() -> dict[str, str]:
    """取得 Telegram Bot 憑證"""
    return await get_bot_credentials("telegram")
