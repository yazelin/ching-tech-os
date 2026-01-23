"""Line Bot 服務

處理：
- Webhook 簽章驗證（多租戶支援）
- 訊息儲存（群組+個人）
- 群組加入/離開事件
- NAS 檔案儲存
- 用戶綁定與存取控制
"""

import hashlib
import hmac
import base64
import logging
import mimetypes
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, TypeVar
from uuid import UUID

import httpx
from linebot.v3 import WebhookParser
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    TextMessageV2,
    ImageMessage,
    MentionSubstitutionObject,
    UserMentionTarget,
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    VideoMessageContent,
    AudioMessageContent,
    FileMessageContent,
    JoinEvent,
    LeaveEvent,
    FollowEvent,
    UnfollowEvent,
)

from ..config import settings
from ..database import get_connection
from .local_file import LocalFileService, LocalFileError, create_linebot_file_service
from . import document_reader

logger = logging.getLogger("linebot")


# ============================================================
# 租戶處理
# ============================================================


def _get_tenant_id(tenant_id: UUID | str | None) -> UUID:
    """處理 tenant_id 參數"""
    if tenant_id is None:
        return UUID(settings.default_tenant_id)
    if isinstance(tenant_id, str):
        return UUID(tenant_id)
    return tenant_id


async def get_group_tenant_id(line_group_id: str) -> UUID | None:
    """從 Line 群組 ID 取得 tenant_id

    Args:
        line_group_id: Line 群組 ID

    Returns:
        租戶 UUID，若群組不存在則回傳 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT tenant_id FROM line_groups WHERE line_group_id = $1",
            line_group_id,
        )
        return row["tenant_id"] if row else None


async def get_user_tenant_id(line_user_id: str) -> UUID | None:
    """從 Line 用戶 ID 取得 tenant_id

    透過用戶的 CTOS 帳號綁定來判斷租戶。
    如果用戶已綁定 CTOS 帳號，從 users 表取得 tenant_id。

    Args:
        line_user_id: Line 用戶 ID

    Returns:
        租戶 UUID，若用戶未綁定或找不到則回傳 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.tenant_id
            FROM line_users lu
            JOIN users u ON lu.user_id = u.id
            WHERE lu.line_user_id = $1 AND lu.user_id IS NOT NULL
            """,
            line_user_id,
        )
        return row["tenant_id"] if row else None


async def resolve_tenant_for_message(
    line_group_id: str | None,
    line_user_id: str | None,
) -> UUID:
    """解析訊息的租戶 ID

    優先順序：
    1. 群組訊息且群組已綁定非預設租戶：使用群組的 tenant_id
    2. 群組訊息但群組在預設租戶，且用戶已綁定：自動遷移群組到用戶的租戶
    3. 個人訊息：使用用戶綁定的 CTOS 帳號的 tenant_id
    4. 都找不到：使用預設租戶

    Args:
        line_group_id: Line 群組 ID（群組訊息）
        line_user_id: Line 用戶 ID

    Returns:
        租戶 UUID
    """
    default_tid = UUID(settings.default_tenant_id)

    # 群組訊息：檢查群組的租戶
    if line_group_id:
        group_tenant_id = await get_group_tenant_id(line_group_id)

        # 如果群組已綁定到非預設租戶，直接使用
        if group_tenant_id and group_tenant_id != default_tid:
            return group_tenant_id

        # 群組在預設租戶或不存在，檢查用戶是否已綁定
        if line_user_id:
            user_tenant_id = await get_user_tenant_id(line_user_id)
            if user_tenant_id and user_tenant_id != default_tid:
                # 用戶已綁定到非預設租戶，自動遷移群組
                if group_tenant_id == default_tid:
                    await _migrate_group_to_tenant(line_group_id, user_tenant_id)
                    logger.info(
                        f"已自動將群組 {line_group_id} 從預設租戶遷移到 {user_tenant_id}"
                    )
                return user_tenant_id

        # 群組存在但在預設租戶，且用戶未綁定
        if group_tenant_id:
            return group_tenant_id

    # 個人訊息：使用用戶綁定的租戶
    if line_user_id:
        tenant_id = await get_user_tenant_id(line_user_id)
        if tenant_id:
            return tenant_id

    # 預設租戶
    return default_tid


async def _migrate_group_to_tenant(line_group_id: str, tenant_id: UUID) -> None:
    """將群組遷移到指定租戶（內部函數）"""
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE line_groups
            SET tenant_id = $2, updated_at = NOW()
            WHERE line_group_id = $1
            """,
            line_group_id,
            tenant_id,
        )


# ============================================================
# 常數定義
# ============================================================

# 檔案類型對應的副檔名
FILE_TYPE_EXTENSIONS = {
    "image": ".jpg",
    "video": ".mp4",
    "audio": ".m4a",
    "file": "",  # 檔案類型會有自己的副檔名
}

# MIME 類型對應的副檔名
MIME_TO_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "audio/m4a": ".m4a",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
}


# ============================================================
# 租戶 Line Bot 憑證快取
# ============================================================

# 快取 TTL（5 分鐘）
TENANT_SECRETS_CACHE_TTL = 300

# 快取資料結構
_tenant_secrets_cache: list[dict] | None = None
_tenant_secrets_cache_time: float = 0


async def _load_tenant_secrets() -> list[dict]:
    """從資料庫載入所有租戶的 Line Bot secrets"""
    from . import tenant as tenant_service
    return await tenant_service.get_all_tenant_line_secrets()


async def get_cached_tenant_secrets() -> list[dict]:
    """取得快取的租戶 secrets

    包含 TTL 機制，5 分鐘後自動重新載入。

    Returns:
        包含 tenant_id, channel_id, channel_secret 的列表
    """
    global _tenant_secrets_cache, _tenant_secrets_cache_time

    now = time.time()

    # 檢查快取是否過期
    if _tenant_secrets_cache is None or (now - _tenant_secrets_cache_time) > TENANT_SECRETS_CACHE_TTL:
        _tenant_secrets_cache = await _load_tenant_secrets()
        _tenant_secrets_cache_time = now
        logger.debug(f"已重新載入租戶 secrets 快取，共 {len(_tenant_secrets_cache)} 筆")

    return _tenant_secrets_cache


def invalidate_tenant_secrets_cache():
    """清除租戶 secrets 快取

    當租戶更新 Line Bot 設定時呼叫。
    """
    global _tenant_secrets_cache, _tenant_secrets_cache_time
    _tenant_secrets_cache = None
    _tenant_secrets_cache_time = 0
    logger.debug("已清除租戶 secrets 快取")


# ============================================================
# Line Bot 客戶端（多租戶支援）
# ============================================================

def get_line_config(access_token: str | None = None) -> Configuration:
    """取得 Line API 設定

    Args:
        access_token: 指定的 access token，不指定則使用環境變數
    """
    token = access_token or settings.line_channel_access_token
    return Configuration(access_token=token)


def get_webhook_parser(channel_secret: str | None = None) -> WebhookParser:
    """取得 Webhook 解析器

    Args:
        channel_secret: 指定的 channel secret，不指定則使用環境變數
    """
    secret = channel_secret or settings.line_channel_secret
    return WebhookParser(secret)


async def get_messaging_api(tenant_id: UUID | str | None = None) -> AsyncMessagingApi:
    """取得 Messaging API 客戶端

    Args:
        tenant_id: 租戶 ID，指定時會使用該租戶的 access token

    Returns:
        AsyncMessagingApi 客戶端
    """
    access_token = None

    # 如果指定租戶，嘗試取得該租戶的 access token
    if tenant_id:
        from . import tenant as tenant_service
        credentials = await tenant_service.get_tenant_line_credentials(tenant_id)
        if credentials:
            access_token = credentials.get("access_token")

    config = get_line_config(access_token)
    api_client = AsyncApiClient(config)
    return AsyncMessagingApi(api_client)


# ============================================================
# Webhook 簽章驗證（多租戶支援）
# ============================================================

def verify_signature(body: bytes, signature: str, channel_secret: str | None = None) -> bool:
    """驗證 Line Webhook 簽章

    Args:
        body: 請求內容
        signature: X-Line-Signature header
        channel_secret: 指定的 channel secret，不指定則使用環境變數

    Returns:
        簽章是否正確
    """
    secret = channel_secret or settings.line_channel_secret
    if not secret:
        logger.warning("Line channel secret 未設定")
        return False

    hash_value = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(hash_value).decode("utf-8")

    return hmac.compare_digest(signature, expected_signature)


async def verify_signature_multi_tenant(body: bytes, signature: str) -> UUID | None:
    """多租戶簽章驗證

    遍歷所有租戶的 channel_secret 進行驗證，
    驗證成功則回傳該租戶的 ID。

    流程：
    1. 先嘗試各租戶的 secret（獨立 Bot 模式）
    2. 全部失敗則嘗試環境變數的 secret（共用 Bot 模式）

    Args:
        body: 請求內容
        signature: X-Line-Signature header

    Returns:
        租戶 UUID 或 None（使用預設 Bot 時回傳 None，需從群組綁定判斷）
    """
    # 1. 嘗試各租戶的 secret（獨立 Bot 模式）
    tenant_secrets = await get_cached_tenant_secrets()

    for tenant_info in tenant_secrets:
        secret = tenant_info.get("channel_secret")
        if secret and verify_signature(body, signature, secret):
            tenant_id = tenant_info["tenant_id"]
            logger.debug(f"簽章驗證成功，租戶: {tenant_id}")
            return tenant_id

    # 2. 嘗試環境變數的 secret（共用 Bot 模式）
    if verify_signature(body, signature):
        logger.debug("簽章驗證成功，使用共用 Bot")
        return None  # None 表示使用共用 Bot，需從群組綁定判斷租戶

    logger.warning("所有簽章驗證失敗")
    return None  # 這裡也回傳 None，但外層需要檢查是否驗證失敗


async def verify_webhook_signature(body: bytes, signature: str) -> tuple[bool, UUID | None, str | None]:
    """驗證 Webhook 簽章並識別租戶

    這是對外的主要驗證函數。

    Args:
        body: 請求內容
        signature: X-Line-Signature header

    Returns:
        (是否驗證成功, 租戶 UUID, channel_secret)
        - (True, tenant_id, secret): 驗證成功，識別為指定租戶（獨立 Bot）
        - (True, None, None): 驗證成功，使用共用 Bot（需從群組綁定判斷租戶）
        - (False, None, None): 驗證失敗
    """
    # 1. 先嘗試各租戶的 secret
    tenant_secrets = await get_cached_tenant_secrets()

    for tenant_info in tenant_secrets:
        secret = tenant_info.get("channel_secret")
        if secret and verify_signature(body, signature, secret):
            tenant_id = tenant_info["tenant_id"]
            logger.debug(f"Webhook 驗證成功（獨立 Bot），租戶: {tenant_id}")
            return True, tenant_id, secret

    # 2. 嘗試環境變數的 secret
    if verify_signature(body, signature):
        logger.debug("Webhook 驗證成功（共用 Bot）")
        return True, None, None

    logger.warning("Webhook 簽章驗證失敗")
    return False, None, None


# ============================================================
# 用戶管理
# ============================================================

async def get_or_create_user(
    line_user_id: str,
    profile: dict | None = None,
    is_friend: bool | None = None,
    tenant_id: UUID | str | None = None,
) -> UUID:
    """取得或建立 Line 用戶，回傳內部 UUID

    由於 line_user_id 有全域唯一約束，一個 Line 用戶只能存在於一個租戶。
    此函數會優先查詢全域用戶，如果已存在則返回現有用戶（並更新 profile），
    只有在完全不存在時才建立新用戶。

    Args:
        line_user_id: Line 用戶 ID
        profile: 用戶資料（displayName, pictureUrl, statusMessage）
        is_friend: 是否為好友（僅在建立新用戶時使用）
        tenant_id: 租戶 ID（僅在建立新用戶時使用）
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 查詢指定租戶是否有此用戶
        # 注意：同一個 Line 用戶可以在不同租戶存在（唯一約束是 tenant_id + line_user_id）
        row = await conn.fetchrow(
            "SELECT id, tenant_id FROM line_users WHERE line_user_id = $1 AND tenant_id = $2",
            line_user_id,
            tid,
        )
        if row:
            # 用戶已存在於此租戶，更新 profile 資訊（如果有）
            if profile:
                await conn.execute(
                    """
                    UPDATE line_users
                    SET display_name = COALESCE($2, display_name),
                        picture_url = COALESCE($3, picture_url),
                        status_message = COALESCE($4, status_message),
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    row["id"],
                    profile.get("displayName"),
                    profile.get("pictureUrl"),
                    profile.get("statusMessage"),
                )
            return row["id"]

        # 用戶在此租戶不存在，建立新記錄
        row = await conn.fetchrow(
            """
            INSERT INTO line_users (line_user_id, display_name, picture_url, status_message, is_friend, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            line_user_id,
            profile.get("displayName") if profile else None,
            profile.get("pictureUrl") if profile else None,
            profile.get("statusMessage") if profile else None,
            is_friend if is_friend is not None else False,  # 預設為非好友
            tid,
        )
        return row["id"]


async def update_user_friend_status(
    line_user_id: str,
    is_friend: bool,
    tenant_id: UUID | str | None = None,
) -> bool:
    """更新用戶的好友狀態

    Args:
        line_user_id: Line 用戶 ID
        is_friend: 是否為好友
        tenant_id: 租戶 ID

    Returns:
        是否更新成功
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_users
            SET is_friend = $2, updated_at = NOW()
            WHERE line_user_id = $1 AND tenant_id = $3
            """,
            line_user_id,
            is_friend,
            tid,
        )
        return result == "UPDATE 1"


async def get_user_profile(
    line_user_id: str,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """從 Line API 取得用戶 profile（個人對話用）

    注意：此 API 只能取得與 Bot 有好友關係的用戶資料。
    群組訊息請使用 get_group_member_profile()。

    Args:
        line_user_id: Line 用戶 ID
        tenant_id: 租戶 ID（用於選擇正確的 access token）
    """
    try:
        api = await get_messaging_api(tenant_id)
        profile = await api.get_profile(line_user_id)
        return {
            "displayName": profile.display_name,
            "pictureUrl": profile.picture_url,
            "statusMessage": profile.status_message,
        }
    except Exception as e:
        logger.warning(f"無法取得用戶 profile: {e}")
        return None


async def get_group_member_profile(
    line_group_id: str,
    line_user_id: str,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """從 Line API 取得群組成員 profile

    此 API 可取得群組內任何成員的資料，不需要好友關係。

    Args:
        line_group_id: Line 群組 ID
        line_user_id: Line 用戶 ID
        tenant_id: 租戶 ID（用於選擇正確的 access token）

    Returns:
        包含 displayName、pictureUrl 的字典，失敗回傳 None
    """
    try:
        api = await get_messaging_api(tenant_id)
        profile = await api.get_group_member_profile(line_group_id, line_user_id)
        return {
            "displayName": profile.display_name,
            "pictureUrl": profile.picture_url,
            # 群組成員 API 不回傳 statusMessage
        }
    except Exception as e:
        logger.warning(f"無法取得群組成員 profile: {e}")
        return None


# ============================================================
# 群組管理
# ============================================================

async def get_or_create_group(
    line_group_id: str,
    profile: dict | None = None,
    tenant_id: UUID | str | None = None,
) -> UUID:
    """取得或建立 Line 群組，回傳內部 UUID

    由於 line_group_id 有全域唯一約束，一個 Line 群組只能存在於一個租戶。
    此函數會優先查詢全域群組，如果已存在則返回現有群組（並更新 profile），
    只有在完全不存在時才建立新群組。

    Args:
        line_group_id: Line 群組 ID
        profile: 群組資料（groupName, pictureUrl, memberCount）
        tenant_id: 租戶 ID（僅在建立新群組時使用）
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 先查詢全域是否有此群組（line_group_id 有全域唯一約束）
        row = await conn.fetchrow(
            "SELECT id, tenant_id FROM line_groups WHERE line_group_id = $1",
            line_group_id,
        )
        if row:
            # 群組已存在，更新 profile 資訊（如果有）
            if profile:
                await conn.execute(
                    """
                    UPDATE line_groups
                    SET name = COALESCE($2, name),
                        picture_url = COALESCE($3, picture_url),
                        member_count = COALESCE($4, member_count),
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    row["id"],
                    profile.get("groupName"),
                    profile.get("pictureUrl"),
                    profile.get("memberCount"),
                )
            return row["id"]

        # 群組不存在，建立新群組
        row = await conn.fetchrow(
            """
            INSERT INTO line_groups (line_group_id, name, picture_url, member_count, tenant_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            line_group_id,
            profile.get("groupName") if profile else None,
            profile.get("pictureUrl") if profile else None,
            profile.get("memberCount") if profile else 0,
            tid,
        )
        return row["id"]


async def get_group_profile(
    line_group_id: str,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """從 Line API 取得群組 profile

    Args:
        line_group_id: Line 群組 ID
        tenant_id: 租戶 ID（用於選擇正確的 access token）
    """
    try:
        api = await get_messaging_api(tenant_id)
        summary = await api.get_group_summary(line_group_id)
        member_count_response = await api.get_group_member_count(line_group_id)
        return {
            "groupName": summary.group_name,
            "pictureUrl": summary.picture_url,
            "memberCount": member_count_response.count,
        }
    except Exception as e:
        logger.warning(f"無法取得群組 profile: {e}")
        return None


async def handle_join_event(
    line_group_id: str,
    tenant_id: UUID | str | None = None,
) -> None:
    """處理加入群組事件（包含重新加入）

    Args:
        line_group_id: Line 群組 ID
        tenant_id: 租戶 ID（新群組會使用此租戶）
    """
    profile = await get_group_profile(line_group_id)
    group_uuid = await get_or_create_group(line_group_id, profile, tenant_id=tenant_id)

    # 確保群組狀態為活躍（處理重新加入的情況）
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE line_groups
            SET is_active = true,
                left_at = NULL,
                joined_at = COALESCE(
                    CASE WHEN is_active = false THEN NOW() ELSE joined_at END,
                    NOW()
                ),
                updated_at = NOW()
            WHERE id = $1
            """,
            group_uuid,
        )
    logger.info(f"Bot 加入群組: {line_group_id}")


async def handle_leave_event(
    line_group_id: str,
    tenant_id: UUID | str | None = None,
) -> None:
    """處理離開群組事件

    Args:
        line_group_id: Line 群組 ID
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE line_groups
            SET is_active = false, left_at = NOW(), updated_at = NOW()
            WHERE line_group_id = $1 AND tenant_id = $2
            """,
            line_group_id,
            tid,
        )
    logger.info(f"Bot 離開群組: {line_group_id}")


async def get_line_group_external_id(
    group_uuid: UUID,
    tenant_id: UUID | str | None = None,
) -> str | None:
    """從內部 UUID 取得 Line 群組的外部 ID

    Args:
        group_uuid: 群組內部 UUID
        tenant_id: 租戶 ID

    Returns:
        Line 群組 ID（外部），或 None（如果找不到）
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT line_group_id FROM line_groups WHERE id = $1 AND tenant_id = $2",
            group_uuid,
            tid,
        )
        return row["line_group_id"] if row else None


# ============================================================
# 訊息儲存
# ============================================================

async def save_message(
    message_id: str,
    line_user_id: str,
    line_group_id: str | None,
    message_type: str,
    content: str | None,
    reply_token: str | None = None,
    is_from_bot: bool = False,
    tenant_id: UUID | str | None = None,
) -> UUID:
    """儲存訊息到資料庫，回傳訊息 UUID

    Args:
        message_id: Line 訊息 ID
        line_user_id: Line 用戶 ID
        line_group_id: Line 群組 ID（群組訊息時使用）
        message_type: 訊息類型（text, image, video, audio, file）
        content: 訊息內容
        reply_token: Line 回覆 token
        is_from_bot: 是否為 Bot 發送的訊息
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)

    # 取得或建立用戶
    # 群組訊息使用 get_group_member_profile（可取得非好友用戶資料）
    # 個人對話使用 get_user_profile（用戶必定與 Bot 有好友關係）
    user_profile = None
    is_friend = None  # 預設不設定，讓 get_or_create_user 決定
    if not is_from_bot:
        if line_group_id:
            user_profile = await get_group_member_profile(line_group_id, line_user_id)
            is_friend = False  # 群組成員預設為非好友
        else:
            user_profile = await get_user_profile(line_user_id)
            is_friend = True  # 個人對話必定是好友
    user_uuid = await get_or_create_user(line_user_id, user_profile, is_friend, tenant_id=tid)

    # 取得或建立群組（如果是群組訊息）
    group_uuid = None
    if line_group_id:
        group_profile = await get_group_profile(line_group_id)
        group_uuid = await get_or_create_group(line_group_id, group_profile, tenant_id=tid)

    # 儲存訊息
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO line_messages (
                message_id, line_user_id, line_group_id,
                message_type, content, reply_token, is_from_bot, tenant_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            message_id,
            user_uuid,
            group_uuid,
            message_type,
            content,
            reply_token,
            is_from_bot,
            tid,
        )
        logger.info(f"儲存訊息: {message_id} (type={message_type})")
        return row["id"]


async def mark_message_ai_processed(message_uuid: UUID) -> None:
    """標記訊息已經過 AI 處理"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE line_messages SET ai_processed = true WHERE id = $1",
            message_uuid,
        )


async def get_or_create_bot_user(tenant_id: UUID | str | None = None) -> UUID:
    """取得或建立 Bot 用戶，回傳用戶 UUID

    由於 line_user_id 有全域唯一約束，Bot 用戶在全系統只會有一個。
    此函數會優先查詢全域 Bot 用戶，如果已存在則返回現有用戶。

    Args:
        tenant_id: 租戶 ID（僅在建立新用戶時使用）
    """
    tid = _get_tenant_id(tenant_id)
    bot_line_id = "BOT_CHINGTECH"

    async with get_connection() as conn:
        # 先查詢全域是否有 Bot 用戶（line_user_id 有全域唯一約束）
        row = await conn.fetchrow(
            "SELECT id FROM line_users WHERE line_user_id = $1",
            bot_line_id,
        )
        if row:
            # 確保 Bot 用戶的 is_friend 為 false 且名稱正確
            await conn.execute(
                """
                UPDATE line_users
                SET is_friend = false, display_name = 'ChingTech AI (Bot)'
                WHERE id = $1
                """,
                row["id"],
            )
            return row["id"]

        # 建立 Bot 用戶（is_friend = false）
        row = await conn.fetchrow(
            """
            INSERT INTO line_users (line_user_id, display_name, is_friend, tenant_id)
            VALUES ($1, $2, false, $3)
            RETURNING id
            """,
            bot_line_id,
            "ChingTech AI (Bot)",
            tid,
        )
        logger.info("已建立 Bot 用戶")
        return row["id"]


async def save_bot_response(
    group_uuid: UUID | None,
    content: str,
    responding_to_line_user_id: str | None = None,
    line_message_id: str | None = None,
    tenant_id: UUID | str | None = None,
) -> UUID:
    """儲存 Bot 回應訊息到資料庫

    Args:
        group_uuid: 群組內部 UUID（個人對話為 None）
        content: 回應內容
        responding_to_line_user_id: 回應的對象用戶 Line ID（個人對話用）
        line_message_id: Line 回傳的訊息 ID（用於回覆觸發）
        tenant_id: 租戶 ID

    Returns:
        訊息 UUID
    """
    import uuid as uuid_module

    tid = _get_tenant_id(tenant_id)

    # 使用 Line 回傳的 message_id，或產生唯一的 ID
    message_id = line_message_id or f"bot_{uuid_module.uuid4().hex[:16]}"

    # 決定使用哪個用戶 ID
    if group_uuid:
        # 群組對話：使用 Bot 用戶 ID
        user_uuid = await get_or_create_bot_user(tenant_id=tid)
    elif responding_to_line_user_id:
        # 個人對話：使用對話對象的用戶 ID（這樣查詢歷史時可以一起取得）
        user_uuid = await get_or_create_user(responding_to_line_user_id, None, tenant_id=tid)
    else:
        # Fallback：使用 Bot 用戶 ID
        user_uuid = await get_or_create_bot_user(tenant_id=tid)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO line_messages (
                message_id, line_user_id, line_group_id,
                message_type, content, is_from_bot, tenant_id
            )
            VALUES ($1, $2, $3, 'text', $4, true, $5)
            RETURNING id
            """,
            message_id,
            user_uuid,
            group_uuid,
            content,
            tid,
        )
        logger.info(f"儲存 Bot 回應: {message_id}")
        return row["id"]


# ============================================================
# 檔案處理
# ============================================================

async def save_file_record(
    message_uuid: UUID,
    file_type: str,
    file_name: str | None = None,
    file_size: int | None = None,
    mime_type: str | None = None,
    nas_path: str | None = None,
    duration: int | None = None,
    tenant_id: UUID | str | None = None,
) -> UUID:
    """儲存檔案記錄，回傳檔案 UUID

    Args:
        message_uuid: 訊息的 UUID
        file_type: 檔案類型（image, video, audio, file）
        file_name: 原始檔案名稱
        file_size: 檔案大小
        mime_type: MIME 類型
        nas_path: NAS 儲存路徑
        duration: 音訊/影片長度（毫秒）
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO line_files (
                message_id, file_type, file_name,
                file_size, mime_type, nas_path, duration, tenant_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            message_uuid,
            file_type,
            file_name,
            file_size,
            mime_type,
            nas_path,
            duration,
            tid,
        )

        # 更新訊息的 file_id
        await conn.execute(
            "UPDATE line_messages SET file_id = $1 WHERE id = $2",
            row["id"],
            message_uuid,
        )

        return row["id"]


async def download_and_save_file(
    message_id: str,
    message_uuid: UUID,
    file_type: str,
    line_group_id: str | None = None,
    line_user_id: str | None = None,
    file_name: str | None = None,
    tenant_id: UUID | str | None = None,
) -> str | None:
    """下載 Line 檔案並儲存到 NAS，回傳 NAS 路徑

    Args:
        message_id: Line 訊息 ID
        message_uuid: 訊息的 UUID
        file_type: 檔案類型（image, video, audio, file）
        line_group_id: Line 群組 ID（群組訊息時使用）
        line_user_id: Line 用戶 ID（個人訊息時使用）
        file_name: 原始檔案名稱（file 類型時使用）
        tenant_id: 租戶 ID（用於選擇正確的 access token）

    Returns:
        NAS 路徑，失敗時回傳 None
    """
    try:
        # 1. 使用 Line API 下載檔案
        content = await download_line_content(message_id, tenant_id)
        if not content:
            logger.error(f"無法下載 Line 檔案: {message_id}")
            return None

        # 2. 決定儲存路徑
        nas_path = generate_nas_path(
            file_type=file_type,
            message_id=message_id,
            line_group_id=line_group_id,
            line_user_id=line_user_id,
            file_name=file_name,
            content=content,
        )

        # 3. 儲存到 NAS（傳遞 tenant_id 以支援租戶隔離）
        success = await save_to_nas(nas_path, content, tenant_id=tenant_id)
        if not success:
            logger.error(f"儲存檔案到 NAS 失敗: {nas_path}")
            return None

        logger.info(f"檔案已儲存到 NAS: {nas_path}")
        return nas_path

    except Exception as e:
        logger.error(f"下載並儲存檔案失敗 {message_id}: {e}")
        return None


async def download_line_content(
    message_id: str,
    tenant_id: UUID | str | None = None,
) -> bytes | None:
    """從 Line API 下載檔案內容

    Args:
        message_id: Line 訊息 ID
        tenant_id: 租戶 ID（用於選擇正確的 access token）

    Returns:
        檔案內容 bytes，失敗時回傳 None
    """
    # 取得正確的 access token
    access_token = settings.line_channel_access_token
    if tenant_id:
        from . import tenant as tenant_service
        credentials = await tenant_service.get_tenant_line_credentials(tenant_id)
        if credentials and credentials.get("access_token"):
            access_token = credentials["access_token"]

    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        # 使用較長的 timeout（影片可能較大）
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.content
            else:
                logger.error(
                    f"Line API 回應錯誤 {response.status_code}: {response.text}"
                )
                return None
    except Exception as e:
        logger.error(f"下載 Line 內容失敗: {e}")
        return None


def generate_nas_path(
    file_type: str,
    message_id: str,
    line_group_id: str | None = None,
    line_user_id: str | None = None,
    file_name: str | None = None,
    content: bytes | None = None,
) -> str:
    """生成 NAS 儲存路徑

    路徑格式：
    - 群組：linebot/groups/{line_group_id}/{file_type}s/{date}/{message_id}.{ext}
    - 個人：linebot/users/{line_user_id}/{file_type}s/{date}/{message_id}.{ext}

    Args:
        file_type: 檔案類型
        message_id: Line 訊息 ID
        line_group_id: Line 群組 ID
        line_user_id: Line 用戶 ID
        file_name: 原始檔案名稱
        content: 檔案內容（用於判斷 MIME 類型）

    Returns:
        NAS 相對路徑
    """
    # 決定目錄前綴（群組或個人）
    if line_group_id:
        prefix = f"groups/{line_group_id}"
    elif line_user_id:
        prefix = f"users/{line_user_id}"
    else:
        prefix = "unknown"

    # 決定副檔名
    if file_name and "." in file_name:
        ext = "." + file_name.rsplit(".", 1)[-1].lower()
    elif content:
        # 嘗試從內容猜測 MIME 類型
        mime_type = guess_mime_type(content)
        ext = MIME_TO_EXTENSION.get(mime_type, FILE_TYPE_EXTENSIONS.get(file_type, ""))
    else:
        ext = FILE_TYPE_EXTENSIONS.get(file_type, "")

    # 日期目錄
    date_str = datetime.now().strftime("%Y-%m-%d")

    # 檔案名稱
    if file_name and file_type == "file":
        # 保留原始檔名（但加上 message_id 前綴避免重複）
        safe_name = file_name.replace("/", "_").replace("\\", "_")
        filename = f"{message_id}_{safe_name}"
    else:
        filename = f"{message_id}{ext}"

    # 子目錄（images, videos, audios, files）
    subdir = f"{file_type}s"

    return f"{prefix}/{subdir}/{date_str}/{filename}"


def guess_mime_type(content: bytes) -> str:
    """從檔案內容猜測 MIME 類型

    Args:
        content: 檔案內容

    Returns:
        MIME 類型字串
    """
    # 檢查 magic bytes
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content[4:8] == b"ftyp":
        # MP4 或 M4A
        ftyp = content[8:12]
        if ftyp in (b"M4A ", b"mp42", b"isom"):
            return "audio/m4a"
        return "video/mp4"

    return "application/octet-stream"


async def save_to_nas(
    relative_path: str,
    content: bytes,
    tenant_id: UUID | str | None = None,
) -> bool:
    """儲存檔案到 NAS（透過掛載路徑）

    Args:
        relative_path: 相對路徑（不含共享資料夾和基本路徑）
        content: 檔案內容
        tenant_id: 租戶 ID，用於租戶隔離

    Returns:
        是否成功
    """
    try:
        # 傳遞 tenant_id 以支援租戶隔離
        tid_str = str(tenant_id) if tenant_id else None
        file_service = create_linebot_file_service(tid_str)
        # write_file 會自動建立目錄
        file_service.write_file(relative_path, content)
        return True
    except LocalFileError as e:
        logger.error(f"儲存到 NAS 失敗 {relative_path}: {e}")
        return False


# ============================================================
# 回覆訊息
# ============================================================

async def reply_text(
    reply_token: str,
    text: str,
    tenant_id: UUID | str | None = None,
) -> str | None:
    """回覆文字訊息

    Args:
        reply_token: Line 回覆 token
        text: 回覆內容
        tenant_id: 租戶 ID（用於選擇正確的 access token）

    Returns:
        Line 訊息 ID，如果失敗則為 None
    """
    try:
        api = await get_messaging_api(tenant_id)
        response = await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )
        logger.info(f"回覆訊息: {text[:50]}...")
        # 取得 Line 回傳的訊息 ID
        if response and response.sent_messages:
            return response.sent_messages[0].id
        return None
    except Exception as e:
        logger.error(f"回覆訊息失敗: {e}")
        return None


# Mention 佔位符常數
MENTION_KEY = "user"
MENTION_PLACEHOLDER = f"{{{MENTION_KEY}}} "  # "{user} "


def create_text_message_with_mention(
    text: str,
    mention_user_id: str | None = None,
) -> TextMessage | TextMessageV2:
    """建立文字訊息，可選擇 mention 特定用戶

    Args:
        text: 訊息文字
        mention_user_id: 要 mention 的 Line 用戶 ID（如 U1234567890abcdef）

    Returns:
        TextMessage 或 TextMessageV2（帶 mention）
    """
    if mention_user_id:
        # 使用 TextMessageV2 + mention
        # {user} 是佔位符，會被替換為 @用戶名稱
        return TextMessageV2(
            text=MENTION_PLACEHOLDER + text,
            substitution={
                MENTION_KEY: MentionSubstitutionObject(
                    mentionee=UserMentionTarget(userId=mention_user_id)
                )
            },
        )
    else:
        # 一般的 TextMessage
        return TextMessage(text=text)


async def reply_messages(
    reply_token: str,
    messages: list[TextMessage | TextMessageV2 | ImageMessage],
    tenant_id: UUID | str | None = None,
) -> list[str]:
    """回覆多則訊息（文字 + 圖片混合）

    Args:
        reply_token: Line 回覆 token
        messages: 訊息列表（TextMessage 或 ImageMessage，最多 5 則）
        tenant_id: 租戶 ID（用於選擇正確的 access token）

    Returns:
        發送成功的訊息 ID 列表
    """
    if not messages:
        return []

    # Line 限制每次最多 5 則訊息
    messages_to_send = messages[:5]

    try:
        api = await get_messaging_api(tenant_id)
        response = await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages_to_send,
            )
        )

        # 記錄發送內容
        msg_types = [type(m).__name__ for m in messages_to_send]
        logger.info(f"回覆多則訊息: {msg_types}")

        if response and response.sent_messages:
            return [m.id for m in response.sent_messages]
        return []
    except Exception as e:
        logger.error(f"回覆多則訊息失敗: {e}")
        raise  # 往上拋出讓呼叫端處理 fallback


def _parse_line_error(error: Exception) -> str:
    """解析 Line API 錯誤訊息"""
    error_str = str(error).lower()

    # 額度相關
    if "limit" in error_str or "quota" in error_str:
        return "已達本月推播上限"
    # 頻率限制
    if "429" in error_str or "too many" in error_str or "rate" in error_str:
        return "發送頻率過高，請稍後再試"
    # 權限問題
    if "403" in error_str or "forbidden" in error_str:
        return "沒有推播權限"
    # 用戶封鎖或不存在
    if "400" in error_str and ("user" in error_str or "not found" in error_str):
        return "用戶已封鎖機器人或不存在"
    # 圖片 URL 問題
    if "url" in error_str or "image" in error_str:
        return "圖片網址無法存取"
    # 其他
    return f"發送失敗：{error}"


async def push_text(
    to: str,
    text: str,
    tenant_id: UUID | str | None = None,
) -> tuple[str | None, str | None]:
    """主動推送文字訊息

    Args:
        to: 目標 ID（Line 用戶 ID 或群組 ID）
        text: 訊息內容
        tenant_id: 租戶 ID（用於選擇正確的 access token）

    Returns:
        (Line 訊息 ID, 錯誤訊息)，成功時錯誤訊息為 None
    """
    try:
        api = await get_messaging_api(tenant_id)
        response = await api.push_message(
            PushMessageRequest(
                to=to,
                messages=[TextMessage(text=text)],
            )
        )
        logger.info(f"推送訊息到 {to}: {text[:50]}...")
        if response and response.sent_messages:
            return response.sent_messages[0].id, None
        return None, "未知錯誤：無回應"
    except Exception as e:
        logger.error(f"推送訊息失敗: {e}")
        return None, _parse_line_error(e)


async def push_image(
    to: str,
    image_url: str,
    preview_url: str | None = None,
    tenant_id: UUID | str | None = None,
) -> tuple[str | None, str | None]:
    """主動推送圖片訊息

    Args:
        to: 目標 ID（Line 用戶 ID 或群組 ID）
        image_url: 圖片 URL（必須是 HTTPS）
        preview_url: 預覽圖 URL（可選，預設使用 image_url）
        tenant_id: 租戶 ID（用於選擇正確的 access token）

    Returns:
        (Line 訊息 ID, 錯誤訊息)，成功時錯誤訊息為 None
    """
    try:
        api = await get_messaging_api(tenant_id)
        response = await api.push_message(
            PushMessageRequest(
                to=to,
                messages=[ImageMessage(
                    original_content_url=image_url,
                    preview_image_url=preview_url or image_url,
                )],
            )
        )
        logger.info(f"推送圖片到 {to}: {image_url}")
        if response and response.sent_messages:
            return response.sent_messages[0].id, None
        return None, "未知錯誤：無回應"
    except Exception as e:
        logger.error(f"推送圖片失敗: {e}")
        return None, _parse_line_error(e)


async def push_messages(
    to: str,
    messages: list[TextMessage | ImageMessage],
    tenant_id: UUID | str | None = None,
) -> tuple[list[str], str | None]:
    """主動推送多則訊息（最多 5 則）

    Line API 支援單次請求發送多則訊息，可減少 API 呼叫次數。
    超過 5 則時會自動分批發送。

    Args:
        to: 目標 ID（Line 用戶 ID 或群組 ID）
        messages: 訊息列表（TextMessage 或 ImageMessage）
        tenant_id: 租戶 ID（用於選擇正確的 access token）

    Returns:
        (Line 訊息 ID 列表, 錯誤訊息)，成功時錯誤訊息為 None
    """
    if not messages:
        return [], None

    MAX_MESSAGES_PER_REQUEST = 5
    sent_message_ids: list[str] = []
    last_error: str | None = None

    try:
        api = await get_messaging_api(tenant_id)

        # 分批發送（每批最多 5 則）
        for i in range(0, len(messages), MAX_MESSAGES_PER_REQUEST):
            batch = messages[i:i + MAX_MESSAGES_PER_REQUEST]

            response = await api.push_message(
                PushMessageRequest(
                    to=to,
                    messages=batch,
                )
            )

            if response and response.sent_messages:
                for msg in response.sent_messages:
                    sent_message_ids.append(msg.id)

            logger.info(f"推送 {len(batch)} 則訊息到 {to}")

        return sent_message_ids, None

    except Exception as e:
        logger.error(f"推送多則訊息失敗: {e}")
        last_error = _parse_line_error(e)
        # 如果部分成功，仍回傳已發送的 ID
        if sent_message_ids:
            return sent_message_ids, f"部分訊息發送失敗: {last_error}"
        return [], last_error


# ============================================================
# AI 觸發判斷
# ============================================================

def should_trigger_ai(
    message_content: str,
    is_group: bool,
    is_reply_to_bot: bool = False,
) -> bool:
    """
    判斷是否應該觸發 AI 處理

    規則：
    - 個人對話：所有訊息都觸發
    - 群組對話：訊息包含 @bot_name 或回覆機器人訊息時觸發
    """
    if not is_group:
        # 個人對話：全部觸發
        return True

    # 群組對話：檢查是否回覆機器人訊息
    if is_reply_to_bot:
        return True

    # 群組對話：檢查是否被 @ 提及
    content_lower = message_content.lower()

    # 檢查配置的所有觸發名稱
    for name in settings.line_bot_trigger_names:
        if f"@{name.lower()}" in content_lower:
            return True

    return False


async def is_bot_message(line_message_id: str) -> bool:
    """
    檢查訊息是否為機器人發送的

    Args:
        line_message_id: Line 訊息 ID

    Returns:
        True 如果是機器人發送的訊息
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT is_from_bot FROM line_messages WHERE message_id = $1",
            line_message_id,
        )
        if row:
            return row["is_from_bot"] is True
        return False


# ============================================================
# 查詢功能
# ============================================================

async def list_groups(
    is_active: bool | None = None,
    project_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: UUID | str | None = None,
) -> tuple[list[dict], int]:
    """列出群組

    Args:
        is_active: 是否活躍過濾
        project_id: 專案 ID 過濾
        limit: 最大數量
        offset: 偏移量
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 建構查詢條件
        conditions = [f"g.tenant_id = ${1}"]
        params = [tid]
        param_idx = 2

        if is_active is not None:
            conditions.append(f"g.is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        if project_id is not None:
            conditions.append(f"g.project_id = ${param_idx}")
            params.append(project_id)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # 查詢總數
        count_query = f"SELECT COUNT(*) FROM line_groups g WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # 查詢列表
        query = f"""
            SELECT g.*, p.name as project_name
            FROM line_groups g
            LEFT JOIN projects p ON g.project_id = p.id
            WHERE {where_clause}
            ORDER BY g.updated_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows], total


async def list_messages(
    line_group_id: UUID | None = None,
    line_user_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: UUID | str | None = None,
) -> tuple[list[dict], int]:
    """列出訊息

    Args:
        line_group_id: 群組 UUID 過濾
        line_user_id: 用戶 UUID 過濾
        limit: 最大數量
        offset: 偏移量
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        conditions = [f"m.tenant_id = ${1}"]
        params = [tid]
        param_idx = 2

        if line_group_id is not None:
            conditions.append(f"m.line_group_id = ${param_idx}")
            params.append(line_group_id)
            param_idx += 1
        else:
            # 如果沒指定群組，預設查個人訊息
            conditions.append("m.line_group_id IS NULL")

        if line_user_id is not None:
            conditions.append(f"m.line_user_id = ${param_idx}")
            params.append(line_user_id)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # 查詢總數
        count_query = f"SELECT COUNT(*) FROM line_messages m WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # 查詢列表（包含用戶資訊）
        query = f"""
            SELECT m.*, u.display_name as user_display_name, u.picture_url as user_picture_url
            FROM line_messages m
            LEFT JOIN line_users u ON m.line_user_id = u.id
            WHERE {where_clause}
            ORDER BY m.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows], total


async def list_users(
    limit: int = 50,
    offset: int = 0,
    tenant_id: UUID | str | None = None,
) -> tuple[list[dict], int]:
    """列出用戶

    Args:
        limit: 最大數量
        offset: 偏移量
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM line_users WHERE tenant_id = $1",
            tid,
        )
        rows = await conn.fetch(
            """
            SELECT * FROM line_users
            WHERE tenant_id = $1
            ORDER BY updated_at DESC
            LIMIT $2 OFFSET $3
            """,
            tid,
            limit,
            offset,
        )
        return [dict(row) for row in rows], total


async def get_group_by_id(
    group_id: UUID,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """取得群組詳情

    Args:
        group_id: 群組 UUID
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT g.*, p.name as project_name
            FROM line_groups g
            LEFT JOIN projects p ON g.project_id = p.id
            WHERE g.id = $1 AND g.tenant_id = $2
            """,
            group_id,
            tid,
        )
        return dict(row) if row else None


async def get_user_by_id(
    user_id: UUID,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """取得用戶詳情

    Args:
        user_id: 用戶 UUID
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM line_users WHERE id = $1 AND tenant_id = $2",
            user_id,
            tid,
        )
        return dict(row) if row else None


async def bind_group_to_project(
    group_id: UUID,
    project_id: UUID,
    tenant_id: UUID | str | None = None,
) -> bool:
    """綁定群組到專案

    Args:
        group_id: 群組 UUID
        project_id: 專案 UUID
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_groups
            SET project_id = $2, updated_at = NOW()
            WHERE id = $1 AND tenant_id = $3
            """,
            group_id,
            project_id,
            tid,
        )
        return result == "UPDATE 1"


async def unbind_group_from_project(
    group_id: UUID,
    tenant_id: UUID | str | None = None,
) -> bool:
    """解除群組與專案的綁定

    Args:
        group_id: 群組 UUID
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_groups
            SET project_id = NULL, updated_at = NOW()
            WHERE id = $1 AND tenant_id = $2
            """,
            group_id,
            tid,
        )
        return result == "UPDATE 1"


async def delete_group(
    group_id: UUID,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """刪除群組及其相關資料

    Args:
        group_id: 群組 UUID
        tenant_id: 租戶 ID

    Returns:
        刪除結果（含訊息數量）或 None（群組不存在）
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 先查詢群組是否存在及訊息數量
        row = await conn.fetchrow(
            """
            SELECT g.id, g.name,
                   (SELECT COUNT(*) FROM line_messages WHERE line_group_id = g.id) as message_count
            FROM line_groups g
            WHERE g.id = $1 AND g.tenant_id = $2
            """,
            group_id,
            tid,
        )

        if not row:
            return None

        group_name = row["name"] or "未命名群組"
        message_count = row["message_count"]

        # 刪除群組（訊息和檔案記錄會級聯刪除）
        await conn.execute(
            "DELETE FROM line_groups WHERE id = $1 AND tenant_id = $2",
            group_id,
            tid,
        )

        return {
            "group_id": str(group_id),
            "group_name": group_name,
            "deleted_messages": message_count,
        }


# ============================================================
# 檔案查詢
# ============================================================


async def list_files(
    line_group_id: UUID | None = None,
    line_user_id: UUID | None = None,
    file_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: UUID | str | None = None,
) -> tuple[list[dict], int]:
    """列出檔案

    Args:
        line_group_id: 群組 UUID 過濾
        line_user_id: 用戶 UUID 過濾
        file_type: 檔案類型過濾（image, video, audio, file）
        limit: 最大數量
        offset: 偏移量
        tenant_id: 租戶 ID

    Returns:
        (檔案列表, 總數)
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        conditions = [f"f.tenant_id = ${1}"]
        params = [tid]
        param_idx = 2

        if line_group_id is not None:
            conditions.append(f"m.line_group_id = ${param_idx}")
            params.append(line_group_id)
            param_idx += 1

        if line_user_id is not None:
            conditions.append(f"m.line_user_id = ${param_idx}")
            params.append(line_user_id)
            param_idx += 1

        if file_type is not None:
            conditions.append(f"f.file_type = ${param_idx}")
            params.append(file_type)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # 查詢總數
        count_query = f"""
            SELECT COUNT(*)
            FROM line_files f
            JOIN line_messages m ON f.message_id = m.id
            WHERE {where_clause}
        """
        total = await conn.fetchval(count_query, *params)

        # 查詢列表（包含用戶和群組資訊）
        query = f"""
            SELECT f.*,
                   m.line_group_id,
                   m.line_user_id,
                   u.display_name as user_display_name,
                   g.name as group_name
            FROM line_files f
            JOIN line_messages m ON f.message_id = m.id
            LEFT JOIN line_users u ON m.line_user_id = u.id
            LEFT JOIN line_groups g ON m.line_group_id = g.id
            WHERE {where_clause}
            ORDER BY f.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows], total


async def get_file_by_id(
    file_id: UUID,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """取得單一檔案詳情

    Args:
        file_id: 檔案 UUID
        tenant_id: 租戶 ID

    Returns:
        檔案詳情（含關聯資訊）
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT f.*,
                   m.line_group_id,
                   m.line_user_id,
                   u.display_name as user_display_name,
                   g.name as group_name,
                   g.line_group_id as source_group_id
            FROM line_files f
            JOIN line_messages m ON f.message_id = m.id
            LEFT JOIN line_users u ON m.line_user_id = u.id
            LEFT JOIN line_groups g ON m.line_group_id = g.id
            WHERE f.id = $1 AND f.tenant_id = $2
            """,
            file_id,
            tid,
        )
        return dict(row) if row else None


async def read_file_from_nas(
    nas_path: str,
    tenant_id: UUID | str | None = None,
) -> bytes | None:
    """從 NAS 讀取檔案（透過掛載路徑）

    支援租戶隔離路徑與舊版路徑的向後相容：
    1. 若有 tenant_id，先嘗試租戶專屬路徑
    2. 若租戶路徑不存在，自動 fallback 到舊版路徑（如 AI 生成圖片）

    Args:
        nas_path: 相對於 linebot files 根目錄的路徑
        tenant_id: 租戶 ID，用於租戶隔離

    Returns:
        檔案內容 bytes，失敗回傳 None
    """
    tid_str = str(tenant_id) if tenant_id else None

    # 1. 若有 tenant_id，先嘗試租戶專屬路徑
    if tid_str:
        try:
            file_service = create_linebot_file_service(tid_str)
            content = file_service.read_file(nas_path)
            return content
        except LocalFileError:
            # 租戶路徑不存在，嘗試 fallback 到舊版路徑
            pass

    # 2. Fallback：使用舊版路徑（無租戶隔離）
    try:
        file_service = create_linebot_file_service(None)
        content = file_service.read_file(nas_path)
        return content
    except LocalFileError as e:
        logger.error(f"讀取 NAS 檔案失敗 {nas_path}: {e}")
        return None


async def delete_file(
    file_id: UUID,
    tenant_id: UUID | str | None = None,
) -> bool:
    """刪除檔案（從 NAS 和資料庫）

    Args:
        file_id: 檔案 UUID
        tenant_id: 租戶 ID

    Returns:
        是否成功刪除
    """
    tid = _get_tenant_id(tenant_id)

    # 取得檔案資訊
    file_info = await get_file_by_id(file_id, tenant_id=tid)
    if not file_info:
        logger.warning(f"找不到檔案: {file_id}")
        return False

    nas_path = file_info.get("nas_path")

    # 從 NAS 刪除檔案
    if nas_path:
        try:
            # 傳遞 tenant_id 以支援租戶隔離
            file_service = create_linebot_file_service(str(tid))
            file_service.delete_file(nas_path)
            logger.info(f"已從 NAS 刪除檔案: {nas_path}")
        except LocalFileError as e:
            # 如果 NAS 刪除失敗，記錄錯誤但繼續刪除資料庫記錄
            logger.error(f"從 NAS 刪除檔案失敗 {nas_path}: {e}")

    # 從資料庫刪除記錄
    async with get_connection() as conn:
        # 先取得 message_id
        message_id = file_info.get("message_id")

        # 刪除檔案記錄
        await conn.execute(
            "DELETE FROM line_files WHERE id = $1 AND tenant_id = $2",
            file_id,
            tid,
        )
        logger.info(f"已從資料庫刪除檔案記錄: {file_id}")

        # 更新訊息的 file_id 為 NULL
        if message_id:
            await conn.execute(
                "UPDATE line_messages SET file_id = NULL WHERE id = $1",
                message_id,
            )

    return True


# ============================================================
# 用戶綁定服務
# ============================================================


async def generate_binding_code(
    user_id: int,
    tenant_id: UUID | str | None = None,
) -> tuple[str, datetime]:
    """
    產生 6 位數字綁定驗證碼

    Args:
        user_id: CTOS 用戶 ID
        tenant_id: 租戶 ID

    Returns:
        (驗證碼, 過期時間)
    """
    tid = _get_tenant_id(tenant_id)
    # 產生 6 位數字驗證碼
    code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    async with get_connection() as conn:
        # 清除該用戶之前未使用的驗證碼
        await conn.execute(
            """
            DELETE FROM line_binding_codes
            WHERE user_id = $1 AND used_at IS NULL AND tenant_id = $2
            """,
            user_id,
            tid,
        )

        # 建立新驗證碼
        await conn.execute(
            """
            INSERT INTO line_binding_codes (user_id, code, expires_at, tenant_id)
            VALUES ($1, $2, $3, $4)
            """,
            user_id,
            code,
            expires_at,
            tid,
        )

    logger.info(f"已產生綁定驗證碼: user_id={user_id}")
    return code, expires_at


async def verify_binding_code(
    line_user_uuid: UUID,
    code: str,
    tenant_id: UUID | str | None = None,
) -> tuple[bool, str]:
    """
    驗證綁定驗證碼並完成綁定

    支援跨租戶綁定：當用戶在共用 Bot 模式下首次綁定時，
    Line 用戶記錄可能在預設租戶，但驗證碼在目標租戶。
    此函數會自動處理這種情況。

    Args:
        line_user_uuid: Line 用戶內部 UUID
        code: 驗證碼
        tenant_id: 租戶 ID（可能是預設租戶）

    Returns:
        (是否成功, 訊息)
    """
    current_tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 先用 code 查詢驗證碼（不限租戶），找到目標租戶
        code_row = await conn.fetchrow(
            """
            SELECT id, user_id, tenant_id
            FROM line_binding_codes
            WHERE code = $1
              AND used_at IS NULL
              AND expires_at > NOW()
            """,
            code,
        )

        if not code_row:
            return False, "驗證碼無效或已過期"

        code_id = code_row["id"]
        ctos_user_id = code_row["user_id"]
        target_tid = code_row["tenant_id"]  # 驗證碼所屬的租戶（目標租戶）

        # 取得 Line 用戶的 line_user_id
        line_user_row = await conn.fetchrow(
            "SELECT line_user_id, display_name FROM line_users WHERE id = $1",
            line_user_uuid,
        )
        if not line_user_row:
            return False, "找不到 Line 用戶記錄"

        line_user_id = line_user_row["line_user_id"]
        display_name = line_user_row["display_name"]

        # 檢查目標租戶是否已有此 Line 用戶的綁定記錄
        target_line_user = await conn.fetchrow(
            """
            SELECT id, user_id FROM line_users
            WHERE line_user_id = $1 AND tenant_id = $2
            """,
            line_user_id,
            target_tid,
        )

        if target_line_user:
            # 目標租戶已有此 Line 用戶記錄
            if target_line_user["user_id"]:
                return False, "此 Line 帳號在目標租戶已綁定其他 CTOS 帳號"
            target_line_user_uuid = target_line_user["id"]
        else:
            # 目標租戶沒有此 Line 用戶記錄，建立新記錄
            # 允許同一個 Line 用戶在不同租戶各有獨立的綁定
            target_line_user_uuid = await conn.fetchval(
                """
                INSERT INTO line_users (line_user_id, display_name, tenant_id)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                line_user_id,
                display_name,
                target_tid,
            )
            logger.info(f"已在目標租戶 {target_tid} 建立 Line 用戶記錄: {target_line_user_uuid}")

        # 檢查該 CTOS 用戶是否已綁定其他 Line 帳號
        existing_line = await conn.fetchrow(
            """
            SELECT id FROM line_users
            WHERE user_id = $1 AND tenant_id = $2
            """,
            ctos_user_id,
            target_tid,
        )
        if existing_line:
            return False, "此 CTOS 帳號已綁定其他 Line 帳號"

        # 執行綁定（在目標租戶）
        await conn.execute(
            """
            UPDATE line_users
            SET user_id = $2, updated_at = NOW()
            WHERE id = $1 AND tenant_id = $3
            """,
            target_line_user_uuid,
            ctos_user_id,
            target_tid,
        )

        # 標記驗證碼已使用
        await conn.execute(
            """
            UPDATE line_binding_codes
            SET used_at = NOW(), used_by_line_user_id = $2
            WHERE id = $1
            """,
            code_id,
            target_line_user_uuid,
        )

        logger.info(
            f"綁定成功: line_user={target_line_user_uuid}, ctos_user={ctos_user_id}, "
            f"tenant={target_tid}"
        )
        return True, "綁定成功！您現在可以使用 Line Bot 了。"


async def unbind_line_user(
    user_id: int,
    tenant_id: UUID | str | None = None,
) -> bool:
    """
    解除 CTOS 用戶的 Line 綁定

    Args:
        user_id: CTOS 用戶 ID
        tenant_id: 租戶 ID

    Returns:
        是否成功解除綁定
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_users
            SET user_id = NULL, updated_at = NOW()
            WHERE user_id = $1 AND tenant_id = $2
            """,
            user_id,
            tid,
        )
        if result == "UPDATE 1":
            logger.info(f"已解除綁定: ctos_user={user_id}")
            return True
        return False


async def get_binding_status(
    user_id: int,
    tenant_id: UUID | str | None = None,
) -> dict:
    """
    取得 CTOS 用戶的 Line 綁定狀態

    Args:
        user_id: CTOS 用戶 ID
        tenant_id: 租戶 ID

    Returns:
        綁定狀態資訊
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT lu.display_name, lu.picture_url, bc.used_at as bound_at
            FROM line_users lu
            LEFT JOIN line_binding_codes bc ON bc.used_by_line_user_id = lu.id
            WHERE lu.user_id = $1 AND lu.tenant_id = $2
            ORDER BY bc.used_at DESC NULLS LAST
            LIMIT 1
            """,
            user_id,
            tid,
        )

        if row:
            return {
                "is_bound": True,
                "line_display_name": row["display_name"],
                "line_picture_url": row["picture_url"],
                "bound_at": row["bound_at"],
            }
        else:
            return {
                "is_bound": False,
                "line_display_name": None,
                "line_picture_url": None,
                "bound_at": None,
            }


async def is_binding_code_format(content: str) -> bool:
    """
    檢查內容是否為驗證碼格式（6 位數字）

    Args:
        content: 訊息內容

    Returns:
        是否為驗證碼格式
    """
    return content.isdigit() and len(content) == 6


# ============================================================
# 存取控制
# ============================================================


async def check_line_access(
    line_user_uuid: UUID,
    line_group_uuid: UUID | None = None,
    tenant_id: UUID | str | None = None,
) -> tuple[bool, str | None]:
    """
    檢查 Line 用戶是否有權限使用 Bot

    規則：
    1. Line 用戶必須綁定 CTOS 帳號
    2. 如果是群組訊息，群組必須設為 allow_ai_response = true

    Args:
        line_user_uuid: Line 用戶內部 UUID
        line_group_uuid: Line 群組內部 UUID（個人對話為 None）
        tenant_id: 租戶 ID

    Returns:
        (是否有權限, 拒絕原因)
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 檢查用戶綁定
        user_row = await conn.fetchrow(
            "SELECT user_id FROM line_users WHERE id = $1 AND tenant_id = $2",
            line_user_uuid,
            tid,
        )

        if not user_row or not user_row["user_id"]:
            return False, "user_not_bound"

        # 如果是群組，檢查群組設定
        if line_group_uuid:
            group_row = await conn.fetchrow(
                "SELECT allow_ai_response FROM line_groups WHERE id = $1 AND tenant_id = $2",
                line_group_uuid,
                tid,
            )
            if not group_row or not group_row["allow_ai_response"]:
                return False, "group_not_allowed"

        return True, None


async def update_group_settings(
    group_id: UUID,
    allow_ai_response: bool,
    tenant_id: UUID | str | None = None,
) -> bool:
    """
    更新群組設定

    Args:
        group_id: 群組 UUID
        allow_ai_response: 是否允許 AI 回應
        tenant_id: 租戶 ID

    Returns:
        是否成功更新
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_groups
            SET allow_ai_response = $2, updated_at = NOW()
            WHERE id = $1 AND tenant_id = $3
            """,
            group_id,
            allow_ai_response,
            tid,
        )
        return result == "UPDATE 1"


async def update_group_tenant(
    group_id: UUID,
    new_tenant_id: UUID,
    current_tenant_id: UUID | str | None = None,
) -> bool:
    """
    更新群組的租戶

    將群組從一個租戶移動到另一個租戶。
    此操作需要管理員權限，且會影響群組內所有訊息的可見性。

    Args:
        group_id: 群組 UUID
        new_tenant_id: 新的租戶 ID
        current_tenant_id: 當前租戶 ID（用於驗證權限）

    Returns:
        是否成功更新
    """
    tid = _get_tenant_id(current_tenant_id)
    async with get_connection() as conn:
        # 確認群組存在且屬於當前租戶
        existing = await conn.fetchrow(
            "SELECT id FROM line_groups WHERE id = $1 AND tenant_id = $2",
            group_id,
            tid,
        )
        if not existing:
            return False

        # 更新群組的租戶
        result = await conn.execute(
            """
            UPDATE line_groups
            SET tenant_id = $2, updated_at = NOW()
            WHERE id = $1 AND tenant_id = $3
            """,
            group_id,
            new_tenant_id,
            tid,
        )
        return result == "UPDATE 1"


async def bind_group_to_tenant_by_code(
    line_group_id: str,
    tenant_code: str,
) -> tuple[bool, str, UUID | None]:
    """
    透過租戶代碼綁定群組到租戶（共用 Bot 模式）

    當使用共用 Bot 時，用戶需要在群組中發送 `/綁定 公司代碼` 指令
    來將群組綁定到特定租戶。

    Args:
        line_group_id: Line 群組 ID
        tenant_code: 租戶代碼（如 ching-tech）

    Returns:
        (是否成功, 回覆訊息, 新租戶ID)
    """
    async with get_connection() as conn:
        # 查詢租戶
        tenant_row = await conn.fetchrow(
            """
            SELECT id, name, code, status
            FROM tenants
            WHERE LOWER(code) = LOWER($1)
            """,
            tenant_code.strip(),
        )

        if not tenant_row:
            return False, f"找不到代碼為「{tenant_code}」的租戶，請確認代碼是否正確。", None

        if tenant_row["status"] != "active":
            return False, f"租戶「{tenant_row['name']}」目前未啟用，無法綁定。", None

        new_tenant_id = tenant_row["id"]
        tenant_name = tenant_row["name"]

        # 檢查群組是否已存在
        group_row = await conn.fetchrow(
            "SELECT id, tenant_id, name FROM line_groups WHERE line_group_id = $1",
            line_group_id,
        )

        if group_row:
            current_tenant_id = group_row["tenant_id"]

            # 檢查是否已綁定到相同租戶
            if current_tenant_id == new_tenant_id:
                return False, f"此群組已綁定到「{tenant_name}」。", None

            # 更新群組的租戶
            await conn.execute(
                """
                UPDATE line_groups
                SET tenant_id = $2, updated_at = NOW()
                WHERE id = $1
                """,
                group_row["id"],
                new_tenant_id,
            )

            # 同時更新相關訊息和檔案的租戶
            await conn.execute(
                "UPDATE line_messages SET tenant_id = $2 WHERE line_group_id = $1",
                group_row["id"],
                new_tenant_id,
            )
            await conn.execute(
                """
                UPDATE line_files SET tenant_id = $2
                WHERE message_id IN (SELECT id FROM line_messages WHERE line_group_id = $1)
                """,
                group_row["id"],
                new_tenant_id,
            )

            logger.info(f"群組 {line_group_id} 從租戶 {current_tenant_id} 轉移到 {new_tenant_id}")
            return True, f"✅ 已將此群組綁定到「{tenant_name}」", new_tenant_id
        else:
            # 群組不存在，建立新群組並綁定到指定租戶
            # 此情況通常不會發生，因為收到 /綁定 指令時群組應已存在
            logger.warning(f"群組 {line_group_id} 不存在，無法綁定")
            return False, "群組記錄不存在，請先發送任意訊息後再嘗試綁定。", None


def is_bind_tenant_command(text: str) -> tuple[bool, str | None]:
    """
    檢查是否為綁定租戶指令

    支援格式：
    - /綁定 公司代碼
    - /bind 公司代碼

    Args:
        text: 訊息文字

    Returns:
        (是否為綁定指令, 租戶代碼)
    """
    if not text:
        return False, None

    text = text.strip()

    # 支援 /綁定 和 /bind 指令
    for prefix in ["/綁定 ", "/綁定", "/bind ", "/bind"]:
        if text.lower().startswith(prefix.lower()):
            code = text[len(prefix):].strip()
            if code:
                return True, code
            return True, None

    return False, None


async def list_users_with_binding(
    limit: int = 50,
    offset: int = 0,
    tenant_id: UUID | str | None = None,
) -> tuple[list[dict], int]:
    """列出用戶（包含 CTOS 綁定資訊）

    Args:
        limit: 最大數量
        offset: 偏移量
        tenant_id: 租戶 ID
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM line_users WHERE tenant_id = $1",
            tid,
        )
        rows = await conn.fetch(
            """
            SELECT lu.*, u.username as bound_username, u.display_name as bound_display_name
            FROM line_users lu
            LEFT JOIN users u ON lu.user_id = u.id
            WHERE lu.tenant_id = $1
            ORDER BY lu.updated_at DESC
            LIMIT $2 OFFSET $3
            """,
            tid,
            limit,
            offset,
        )
        return [dict(row) for row in rows], total


# ============================================================
# 對話管理
# ============================================================


async def reset_conversation(
    line_user_id: str,
    tenant_id: UUID | str | None = None,
) -> bool:
    """重置用戶的對話歷史

    設定 conversation_reset_at 為當前時間，
    之後查詢對話歷史時會忽略這個時間之前的訊息。

    Args:
        line_user_id: Line 用戶 ID
        tenant_id: 租戶 ID

    Returns:
        是否成功
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_users
            SET conversation_reset_at = NOW()
            WHERE line_user_id = $1 AND tenant_id = $2
            """,
            line_user_id,
            tid,
        )
        success = result == "UPDATE 1"
        if success:
            logger.info(f"已重置對話歷史: {line_user_id}")
        return success


def is_reset_command(content: str) -> bool:
    """檢查訊息是否為重置對話指令

    Args:
        content: 訊息內容

    Returns:
        是否為重置指令
    """
    reset_commands = [
        "/新對話",
        "/新对话",
        "/reset",
        "/清除對話",
        "/清除对话",
        "/忘記",
        "/忘记",
    ]
    return content.strip().lower() in [cmd.lower() for cmd in reset_commands]


# ============================================================
# 檔案暫存服務
# ============================================================

# 暫存目錄
TEMP_IMAGE_DIR = "/tmp/linebot-images"
TEMP_FILE_DIR = "/tmp/linebot-files"

# 可讀取的檔案副檔名（AI 可透過 Read 工具讀取）
READABLE_FILE_EXTENSIONS = {
    # 純文字格式
    ".txt", ".md", ".json", ".csv", ".log",
    ".xml", ".yaml", ".yml",
    # Office 文件（透過 document_reader 解析）
    ".docx", ".xlsx", ".pptx",
    # PDF 文件（透過 document_reader 解析）
    ".pdf",
}

# 舊版 Office 格式（提示轉檔）
LEGACY_OFFICE_EXTENSIONS = {".doc", ".xls", ".ppt"}

# 需要文件解析的格式（透過 document_reader 處理）
DOCUMENT_EXTENSIONS = {".docx", ".xlsx", ".pptx", ".pdf"}

# 最大可讀取檔案大小（5MB）
MAX_READABLE_FILE_SIZE = 5 * 1024 * 1024


def is_readable_file(filename: str) -> bool:
    """判斷檔案是否為可讀取類型

    Args:
        filename: 檔案名稱

    Returns:
        是否可讀取
    """
    if not filename:
        return False
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in READABLE_FILE_EXTENSIONS


def is_legacy_office_file(filename: str) -> bool:
    """判斷檔案是否為舊版 Office 格式

    Args:
        filename: 檔案名稱

    Returns:
        是否為舊版格式（.doc, .xls, .ppt）
    """
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    return ext in LEGACY_OFFICE_EXTENSIONS


def is_document_file(filename: str) -> bool:
    """判斷檔案是否需要文件解析

    Args:
        filename: 檔案名稱

    Returns:
        是否為需要解析的文件格式（.docx, .xlsx, .pptx, .pdf）
    """
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    return ext in DOCUMENT_EXTENSIONS


def get_temp_image_path(line_message_id: str) -> str:
    """取得圖片暫存路徑

    Args:
        line_message_id: Line 訊息 ID

    Returns:
        暫存檔案路徑
    """
    return f"{TEMP_IMAGE_DIR}/{line_message_id}.jpg"


async def ensure_temp_image(
    line_message_id: str,
    nas_path: str,
    tenant_id: UUID | str | None = None,
) -> str | None:
    """確保圖片暫存檔存在

    如果暫存檔不存在，從 NAS 讀取並寫入暫存。

    Args:
        line_message_id: Line 訊息 ID
        nas_path: NAS 上的檔案路徑
        tenant_id: 租戶 ID，用於多租戶 NAS 隔離

    Returns:
        暫存檔案路徑，失敗回傳 None
    """
    import os

    # 確保暫存目錄存在
    os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)

    temp_path = get_temp_image_path(line_message_id)

    # 如果暫存檔已存在，直接回傳
    if os.path.exists(temp_path):
        return temp_path

    # 從 NAS 讀取圖片（傳遞 tenant_id 支援多租戶）
    content = await read_file_from_nas(nas_path, tenant_id=tenant_id)
    if content is None:
        logger.warning(f"無法從 NAS 讀取圖片: {nas_path} (tenant_id={tenant_id})")
        return None

    # 寫入暫存檔
    try:
        with open(temp_path, "wb") as f:
            f.write(content)
        logger.debug(f"已建立圖片暫存: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"寫入暫存檔失敗: {e}")
        return None


async def get_image_info_by_line_message_id(
    line_message_id: str,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """透過 Line 訊息 ID 取得圖片資訊

    Args:
        line_message_id: Line 訊息 ID
        tenant_id: 租戶 ID

    Returns:
        包含 nas_path 等資訊的字典，找不到回傳 None
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT f.nas_path, f.file_type, m.id as message_uuid
            FROM line_files f
            JOIN line_messages m ON f.message_id = m.id
            WHERE m.message_id = $1
              AND f.file_type = 'image'
              AND f.tenant_id = $2
            """,
            line_message_id,
            tid,
        )
        return dict(row) if row else None


# ============================================================
# 檔案暫存服務（非圖片）
# ============================================================


def get_temp_file_path(line_message_id: str, filename: str) -> str:
    """取得檔案暫存路徑

    Args:
        line_message_id: Line 訊息 ID
        filename: 原始檔案名稱

    Returns:
        暫存檔案路徑
    """
    # 移除不安全的字元
    safe_filename = filename.replace("/", "_").replace("\\", "_")
    return f"{TEMP_FILE_DIR}/{line_message_id}_{safe_filename}"


async def ensure_temp_file(
    line_message_id: str,
    nas_path: str,
    filename: str,
    file_size: int | None = None,
    tenant_id: UUID | str | None = None,
) -> str | None:
    """確保檔案暫存檔存在

    如果暫存檔不存在，從 NAS 讀取並寫入暫存。
    對於 Office 文件和 PDF，會先解析成純文字再存入 .txt 暫存檔。

    Args:
        line_message_id: Line 訊息 ID
        nas_path: NAS 上的檔案路徑
        filename: 原始檔案名稱
        file_size: 檔案大小（用於檢查是否超過限制）
        tenant_id: 租戶 ID，用於多租戶 NAS 隔離

    Returns:
        暫存檔案路徑，失敗或不符合條件回傳 None
    """
    import os
    import tempfile

    # 檢查是否為可讀取類型
    if not is_readable_file(filename):
        logger.debug(f"檔案類型不支援讀取: {filename}")
        return None

    # 對於需要解析的文件格式，使用 document_reader 的大小限制
    needs_parsing = is_document_file(filename)

    # 檢查檔案大小（文件解析有自己的大小限制，這裡先做基本檢查）
    if not needs_parsing and file_size is not None and file_size > MAX_READABLE_FILE_SIZE:
        logger.debug(f"檔案過大，跳過暫存: {filename} ({file_size} bytes)")
        return None

    # 確保暫存目錄存在
    os.makedirs(TEMP_FILE_DIR, exist_ok=True)

    # 判斷是否為 PDF（需要同時保留原始檔和文字版）
    ext = os.path.splitext(filename)[1].lower()
    is_pdf = ext == ".pdf"

    # 對於需要解析的文件，暫存檔使用 .txt 副檔名
    if needs_parsing:
        base_name = os.path.splitext(filename)[0]
        temp_path = f"{TEMP_FILE_DIR}/{line_message_id}_{base_name}.txt"
        # PDF 同時需要原始檔副本（供 convert_pdf_to_images 使用）
        if is_pdf:
            pdf_temp_path = f"{TEMP_FILE_DIR}/{line_message_id}_{filename}"
    else:
        temp_path = get_temp_file_path(line_message_id, filename)

    # 如果暫存檔已存在，直接回傳
    # 對於 PDF，回傳特殊格式包含兩個路徑
    if is_pdf:
        if os.path.exists(pdf_temp_path) and os.path.exists(temp_path):
            # 回傳 "PDF:xxx.pdf|TXT:xxx.txt" 格式
            return f"PDF:{pdf_temp_path}|TXT:{temp_path}"
    elif os.path.exists(temp_path):
        return temp_path

    # 從 NAS 讀取檔案（傳遞 tenant_id 支援多租戶）
    content = await read_file_from_nas(nas_path, tenant_id=tenant_id)
    if content is None:
        logger.warning(f"無法從 NAS 讀取檔案: {nas_path} (tenant_id={tenant_id})")
        return None

    # 如果需要解析文件
    if needs_parsing:
        try:
            # 將二進位內容寫入臨時檔案供 document_reader 解析
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # 解析文件
                result = document_reader.extract_text(tmp_path)
                text_content = result.text

                # 如果有錯誤訊息（部分成功），附加說明
                if result.error:
                    text_content = f"[注意：{result.error}]\n\n{text_content}"

                # 寫入純文字暫存檔
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(text_content)

                logger.debug(f"已建立文件暫存（已解析）: {temp_path}")

                # PDF 同時保存原始檔副本（供 convert_pdf_to_images 使用）
                if is_pdf:
                    with open(pdf_temp_path, "wb") as f:
                        f.write(content)
                    logger.debug(f"已建立 PDF 原始檔暫存: {pdf_temp_path}")
                    # 回傳特殊格式包含兩個路徑
                    return f"PDF:{pdf_temp_path}|TXT:{temp_path}"

                return temp_path

            except document_reader.FileTooLargeError as e:
                logger.debug(f"文件過大: {filename} - {e}")
                return None
            except document_reader.PasswordProtectedError as e:
                logger.debug(f"文件有密碼保護: {filename}")
                # 寫入錯誤訊息到暫存檔，讓 AI 知道
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(f"[錯誤] 此文件有密碼保護，無法讀取。")
                # PDF 也保存原始檔（即使有密碼保護，仍可能需要轉圖片）
                if is_pdf:
                    with open(pdf_temp_path, "wb") as f:
                        f.write(content)
                    return f"PDF:{pdf_temp_path}|TXT:{temp_path}"
                return temp_path
            except document_reader.DocumentReadError as e:
                logger.warning(f"文件解析失敗: {filename} - {e}")
                # PDF 解析失敗（如純圖片 PDF）仍保存原始檔供轉圖片使用
                if is_pdf:
                    with open(pdf_temp_path, "wb") as f:
                        f.write(content)
                    logger.debug(f"PDF 解析失敗但已保存原始檔: {pdf_temp_path}")
                    # 純圖片 PDF 沒有文字版，只回傳 PDF 路徑
                    return f"PDF:{pdf_temp_path}|TXT:"
                return None
            finally:
                # 清理臨時檔案
                if 'tmp_path' in locals() and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError as unlink_error:
                        logger.warning(f"無法清理臨時檔案 {tmp_path}: {unlink_error}")

        except Exception as e:
            logger.error(f"文件處理失敗: {filename} - {e}")
            return None
    else:
        # 純文字格式：直接寫入
        # 再次檢查實際檔案大小
        if len(content) > MAX_READABLE_FILE_SIZE:
            logger.debug(f"檔案實際大小超過限制: {filename} ({len(content)} bytes)")
            return None

        # 寫入暫存檔
        try:
            with open(temp_path, "wb") as f:
                f.write(content)
            logger.debug(f"已建立檔案暫存: {temp_path}")
            return temp_path
        except Exception as e:
            logger.error(f"寫入暫存檔失敗: {e}")
            return None


async def get_file_info_by_line_message_id(
    line_message_id: str,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """透過 Line 訊息 ID 取得檔案資訊（非圖片）

    Args:
        line_message_id: Line 訊息 ID
        tenant_id: 租戶 ID

    Returns:
        包含 nas_path, file_name, file_size 等資訊的字典，找不到回傳 None
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT f.nas_path, f.file_type, f.file_name, f.file_size,
                   m.id as message_uuid
            FROM line_files f
            JOIN line_messages m ON f.message_id = m.id
            WHERE m.message_id = $1
              AND f.file_type = 'file'
              AND f.tenant_id = $2
            """,
            line_message_id,
            tid,
        )
        return dict(row) if row else None


async def get_message_content_by_line_message_id(line_message_id: str) -> dict | None:
    """根據 Line message_id 取得訊息內容

    Args:
        line_message_id: Line 訊息 ID

    Returns:
        dict with content, message_type, display_name, is_from_bot or None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT m.content, m.message_type, m.is_from_bot,
                   u.display_name
            FROM line_messages m
            JOIN line_users u ON m.line_user_id = u.id
            WHERE m.message_id = $1
            """,
            line_message_id,
        )
        return dict(row) if row else None


# ============================================================
# 記憶管理服務
# ============================================================


async def list_group_memories(line_group_id: UUID) -> tuple[list[dict], int]:
    """取得群組記憶列表

    Args:
        line_group_id: 群組內部 UUID

    Returns:
        (記憶列表, 總數)
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT m.*, u.display_name as created_by_name
            FROM line_group_memories m
            LEFT JOIN line_users u ON m.created_by = u.id
            WHERE m.line_group_id = $1
            ORDER BY m.created_at DESC
            """,
            line_group_id,
        )
        return [dict(row) for row in rows], len(rows)


async def list_user_memories(line_user_id: UUID) -> tuple[list[dict], int]:
    """取得個人記憶列表

    Args:
        line_user_id: 用戶內部 UUID

    Returns:
        (記憶列表, 總數)
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM line_user_memories
            WHERE line_user_id = $1
            ORDER BY created_at DESC
            """,
            line_user_id,
        )
        return [dict(row) for row in rows], len(rows)


async def create_group_memory(
    line_group_id: UUID,
    title: str,
    content: str,
    created_by: UUID | None = None,
) -> dict:
    """建立群組記憶

    Args:
        line_group_id: 群組內部 UUID
        title: 記憶標題
        content: 記憶內容
        created_by: 建立者（Line 用戶 UUID）

    Returns:
        建立的記憶資料
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO line_group_memories (line_group_id, title, content, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            line_group_id,
            title,
            content,
            created_by,
        )
        result = dict(row)

        # 取得建立者名稱
        if created_by:
            user_row = await conn.fetchrow(
                "SELECT display_name FROM line_users WHERE id = $1",
                created_by,
            )
            if user_row:
                result["created_by_name"] = user_row["display_name"]

        logger.info(f"已建立群組記憶: group={line_group_id}, title={title}")
        return result


async def create_user_memory(
    line_user_id: UUID,
    title: str,
    content: str,
) -> dict:
    """建立個人記憶

    Args:
        line_user_id: 用戶內部 UUID
        title: 記憶標題
        content: 記憶內容

    Returns:
        建立的記憶資料
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO line_user_memories (line_user_id, title, content)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            line_user_id,
            title,
            content,
        )
        logger.info(f"已建立個人記憶: user={line_user_id}, title={title}")
        return dict(row)


async def update_memory(
    memory_id: UUID,
    title: str | None = None,
    content: str | None = None,
    is_active: bool | None = None,
) -> dict | None:
    """更新記憶（群組或個人）

    會先嘗試在 line_group_memories 找，找不到再找 line_user_memories。

    Args:
        memory_id: 記憶 UUID
        title: 新標題（可選）
        content: 新內容（可選）
        is_active: 新啟用狀態（可選）

    Returns:
        更新後的記憶資料，找不到回傳 None
    """
    async with get_connection() as conn:
        # 先嘗試更新群組記憶
        update_fields = []
        params = [memory_id]
        param_idx = 2

        if title is not None:
            update_fields.append(f"title = ${param_idx}")
            params.append(title)
            param_idx += 1
        if content is not None:
            update_fields.append(f"content = ${param_idx}")
            params.append(content)
            param_idx += 1
        if is_active is not None:
            update_fields.append(f"is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        if not update_fields:
            # 沒有要更新的欄位，直接查詢回傳
            row = await conn.fetchrow(
                """
                SELECT m.*, u.display_name as created_by_name
                FROM line_group_memories m
                LEFT JOIN line_users u ON m.created_by = u.id
                WHERE m.id = $1
                """,
                memory_id,
            )
            if row:
                return dict(row)
            row = await conn.fetchrow(
                "SELECT * FROM line_user_memories WHERE id = $1",
                memory_id,
            )
            return dict(row) if row else None

        update_fields.append("updated_at = NOW()")
        set_clause = ", ".join(update_fields)

        # 嘗試更新群組記憶
        row = await conn.fetchrow(
            f"""
            UPDATE line_group_memories
            SET {set_clause}
            WHERE id = $1
            RETURNING *
            """,
            *params,
        )

        if row:
            result = dict(row)
            # 取得建立者名稱
            if result.get("created_by"):
                user_row = await conn.fetchrow(
                    "SELECT display_name FROM line_users WHERE id = $1",
                    result["created_by"],
                )
                if user_row:
                    result["created_by_name"] = user_row["display_name"]
            logger.info(f"已更新群組記憶: {memory_id}")
            return result

        # 嘗試更新個人記憶
        row = await conn.fetchrow(
            f"""
            UPDATE line_user_memories
            SET {set_clause}
            WHERE id = $1
            RETURNING *
            """,
            *params,
        )

        if row:
            logger.info(f"已更新個人記憶: {memory_id}")
            return dict(row)

        return None


async def delete_memory(memory_id: UUID) -> bool:
    """刪除記憶（群組或個人）

    會先嘗試在 line_group_memories 刪除，找不到再找 line_user_memories。

    Args:
        memory_id: 記憶 UUID

    Returns:
        是否成功刪除
    """
    async with get_connection() as conn:
        # 先嘗試刪除群組記憶
        result = await conn.execute(
            "DELETE FROM line_group_memories WHERE id = $1",
            memory_id,
        )
        if result == "DELETE 1":
            logger.info(f"已刪除群組記憶: {memory_id}")
            return True

        # 嘗試刪除個人記憶
        result = await conn.execute(
            "DELETE FROM line_user_memories WHERE id = $1",
            memory_id,
        )
        if result == "DELETE 1":
            logger.info(f"已刪除個人記憶: {memory_id}")
            return True

        return False


async def get_line_user_by_ctos_user(ctos_user_id: int) -> dict | None:
    """透過 CTOS 用戶 ID 取得對應的 Line 用戶

    Args:
        ctos_user_id: CTOS 用戶 ID

    Returns:
        Line 用戶資料，找不到回傳 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM line_users WHERE user_id = $1",
            ctos_user_id,
        )
        return dict(row) if row else None


async def get_active_group_memories(line_group_id: UUID) -> list[dict]:
    """取得群組的所有啟用記憶

    Args:
        line_group_id: 群組內部 UUID

    Returns:
        啟用的記憶列表
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT content
            FROM line_group_memories
            WHERE line_group_id = $1 AND is_active = true
            ORDER BY created_at ASC
            """,
            line_group_id,
        )
        return [dict(row) for row in rows]


async def get_active_user_memories(line_user_id: UUID) -> list[dict]:
    """取得用戶的所有啟用記憶

    Args:
        line_user_id: 用戶內部 UUID

    Returns:
        啟用的記憶列表
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT content
            FROM line_user_memories
            WHERE line_user_id = $1 AND is_active = true
            ORDER BY created_at ASC
            """,
            line_user_id,
        )
        return [dict(row) for row in rows]
