"""Line Bot 服務

處理：
- Webhook 簽章驗證
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
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from linebot.v3 import WebhookParser
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    ReplyMessageRequest,
    TextMessage,
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
from .smb import SMBService

logger = logging.getLogger("linebot")


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
# Line Bot 客戶端
# ============================================================

def get_line_config() -> Configuration:
    """取得 Line API 設定"""
    return Configuration(access_token=settings.line_channel_access_token)


def get_webhook_parser() -> WebhookParser:
    """取得 Webhook 解析器"""
    return WebhookParser(settings.line_channel_secret)


async def get_messaging_api() -> AsyncMessagingApi:
    """取得 Messaging API 客戶端"""
    config = get_line_config()
    api_client = AsyncApiClient(config)
    return AsyncMessagingApi(api_client)


# ============================================================
# Webhook 簽章驗證
# ============================================================

def verify_signature(body: bytes, signature: str) -> bool:
    """驗證 Line Webhook 簽章"""
    if not settings.line_channel_secret:
        logger.warning("Line channel secret 未設定")
        return False

    hash_value = hmac.new(
        settings.line_channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(hash_value).decode("utf-8")

    return hmac.compare_digest(signature, expected_signature)


# ============================================================
# 用戶管理
# ============================================================

async def get_or_create_user(line_user_id: str, profile: dict | None = None) -> UUID:
    """取得或建立 Line 用戶，回傳內部 UUID"""
    async with get_connection() as conn:
        # 查詢現有用戶
        row = await conn.fetchrow(
            "SELECT id FROM line_users WHERE line_user_id = $1",
            line_user_id,
        )
        if row:
            # 更新用戶資訊（如果有 profile）
            if profile:
                await conn.execute(
                    """
                    UPDATE line_users
                    SET display_name = COALESCE($2, display_name),
                        picture_url = COALESCE($3, picture_url),
                        status_message = COALESCE($4, status_message),
                        updated_at = NOW()
                    WHERE line_user_id = $1
                    """,
                    line_user_id,
                    profile.get("displayName"),
                    profile.get("pictureUrl"),
                    profile.get("statusMessage"),
                )
            return row["id"]

        # 建立新用戶
        row = await conn.fetchrow(
            """
            INSERT INTO line_users (line_user_id, display_name, picture_url, status_message)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            line_user_id,
            profile.get("displayName") if profile else None,
            profile.get("pictureUrl") if profile else None,
            profile.get("statusMessage") if profile else None,
        )
        return row["id"]


async def get_user_profile(line_user_id: str) -> dict | None:
    """從 Line API 取得用戶 profile"""
    try:
        api = await get_messaging_api()
        profile = await api.get_profile(line_user_id)
        return {
            "displayName": profile.display_name,
            "pictureUrl": profile.picture_url,
            "statusMessage": profile.status_message,
        }
    except Exception as e:
        logger.warning(f"無法取得用戶 profile: {e}")
        return None


# ============================================================
# 群組管理
# ============================================================

async def get_or_create_group(line_group_id: str, profile: dict | None = None) -> UUID:
    """取得或建立 Line 群組，回傳內部 UUID"""
    async with get_connection() as conn:
        # 查詢現有群組
        row = await conn.fetchrow(
            "SELECT id FROM line_groups WHERE line_group_id = $1",
            line_group_id,
        )
        if row:
            # 更新群組資訊（如果有 profile）
            if profile:
                await conn.execute(
                    """
                    UPDATE line_groups
                    SET name = COALESCE($2, name),
                        picture_url = COALESCE($3, picture_url),
                        member_count = COALESCE($4, member_count),
                        updated_at = NOW()
                    WHERE line_group_id = $1
                    """,
                    line_group_id,
                    profile.get("groupName"),
                    profile.get("pictureUrl"),
                    profile.get("memberCount"),
                )
            return row["id"]

        # 建立新群組
        row = await conn.fetchrow(
            """
            INSERT INTO line_groups (line_group_id, name, picture_url, member_count)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            line_group_id,
            profile.get("groupName") if profile else None,
            profile.get("pictureUrl") if profile else None,
            profile.get("memberCount") if profile else 0,
        )
        return row["id"]


async def get_group_profile(line_group_id: str) -> dict | None:
    """從 Line API 取得群組 profile"""
    try:
        api = await get_messaging_api()
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


async def handle_join_event(line_group_id: str) -> None:
    """處理加入群組事件（包含重新加入）"""
    profile = await get_group_profile(line_group_id)
    group_uuid = await get_or_create_group(line_group_id, profile)

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


async def handle_leave_event(line_group_id: str) -> None:
    """處理離開群組事件"""
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE line_groups
            SET is_active = false, left_at = NOW(), updated_at = NOW()
            WHERE line_group_id = $1
            """,
            line_group_id,
        )
    logger.info(f"Bot 離開群組: {line_group_id}")


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
) -> UUID:
    """儲存訊息到資料庫，回傳訊息 UUID"""
    # 取得或建立用戶
    user_profile = await get_user_profile(line_user_id) if not is_from_bot else None
    user_uuid = await get_or_create_user(line_user_id, user_profile)

    # 取得或建立群組（如果是群組訊息）
    group_uuid = None
    if line_group_id:
        group_profile = await get_group_profile(line_group_id)
        group_uuid = await get_or_create_group(line_group_id, group_profile)

    # 儲存訊息
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO line_messages (
                message_id, line_user_id, line_group_id,
                message_type, content, reply_token, is_from_bot
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            message_id,
            user_uuid,
            group_uuid,
            message_type,
            content,
            reply_token,
            is_from_bot,
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


async def get_or_create_bot_user() -> UUID:
    """取得或建立 Bot 用戶，回傳用戶 UUID"""
    bot_line_id = "BOT_CHINGTECH"

    async with get_connection() as conn:
        # 查詢現有 Bot 用戶
        row = await conn.fetchrow(
            "SELECT id FROM line_users WHERE line_user_id = $1",
            bot_line_id,
        )
        if row:
            return row["id"]

        # 建立 Bot 用戶
        row = await conn.fetchrow(
            """
            INSERT INTO line_users (line_user_id, display_name)
            VALUES ($1, $2)
            RETURNING id
            """,
            bot_line_id,
            "ChingTech AI",
        )
        logger.info("已建立 Bot 用戶")
        return row["id"]


async def save_bot_response(
    group_uuid: UUID | None,
    content: str,
    responding_to_line_user_id: str | None = None,
) -> UUID:
    """儲存 Bot 回應訊息到資料庫

    Args:
        group_uuid: 群組內部 UUID（個人對話為 None）
        content: 回應內容
        responding_to_line_user_id: 回應的對象用戶 Line ID（個人對話用）

    Returns:
        訊息 UUID
    """
    import uuid as uuid_module

    # 產生唯一的 message_id（Bot 回應沒有 Line message_id）
    message_id = f"bot_{uuid_module.uuid4().hex[:16]}"

    # 決定使用哪個用戶 ID
    if group_uuid:
        # 群組對話：使用 Bot 用戶 ID
        user_uuid = await get_or_create_bot_user()
    elif responding_to_line_user_id:
        # 個人對話：使用對話對象的用戶 ID（這樣查詢歷史時可以一起取得）
        user_uuid = await get_or_create_user(responding_to_line_user_id, None)
    else:
        # Fallback：使用 Bot 用戶 ID
        user_uuid = await get_or_create_bot_user()

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO line_messages (
                message_id, line_user_id, line_group_id,
                message_type, content, is_from_bot
            )
            VALUES ($1, $2, $3, 'text', $4, true)
            RETURNING id
            """,
            message_id,
            user_uuid,
            group_uuid,
            content,
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
) -> UUID:
    """儲存檔案記錄，回傳檔案 UUID"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO line_files (
                message_id, file_type, file_name,
                file_size, mime_type, nas_path, duration
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            message_uuid,
            file_type,
            file_name,
            file_size,
            mime_type,
            nas_path,
            duration,
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
) -> str | None:
    """下載 Line 檔案並儲存到 NAS，回傳 NAS 路徑

    Args:
        message_id: Line 訊息 ID
        message_uuid: 訊息的 UUID
        file_type: 檔案類型（image, video, audio, file）
        line_group_id: Line 群組 ID（群組訊息時使用）
        line_user_id: Line 用戶 ID（個人訊息時使用）
        file_name: 原始檔案名稱（file 類型時使用）

    Returns:
        NAS 路徑，失敗時回傳 None
    """
    try:
        # 1. 使用 Line API 下載檔案
        content = await download_line_content(message_id)
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

        # 3. 儲存到 NAS
        success = await save_to_nas(nas_path, content)
        if not success:
            logger.error(f"儲存檔案到 NAS 失敗: {nas_path}")
            return None

        logger.info(f"檔案已儲存到 NAS: {nas_path}")
        return nas_path

    except Exception as e:
        logger.error(f"下載並儲存檔案失敗 {message_id}: {e}")
        return None


async def download_line_content(message_id: str) -> bytes | None:
    """從 Line API 下載檔案內容

    Args:
        message_id: Line 訊息 ID

    Returns:
        檔案內容 bytes，失敗時回傳 None
    """
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {settings.line_channel_access_token}"}

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


async def save_to_nas(relative_path: str, content: bytes) -> bool:
    """儲存檔案到 NAS

    Args:
        relative_path: 相對路徑（不含共享資料夾和基本路徑）
        content: 檔案內容

    Returns:
        是否成功
    """
    # 完整路徑：{base_path}/{relative_path}
    full_path = f"{settings.line_files_nas_path}/{relative_path}"

    try:
        with SMBService(
            host=settings.knowledge_nas_host,
            username=settings.knowledge_nas_user,
            password=settings.knowledge_nas_password,
        ) as smb:
            # 確保目錄存在（建立父目錄）
            await ensure_nas_directory(smb, full_path)

            # 寫入檔案
            smb.write_file(
                share_name=settings.knowledge_nas_share,
                path=full_path,
                data=content,
            )
            return True

    except Exception as e:
        logger.error(f"儲存到 NAS 失敗 {full_path}: {e}")
        return False


async def ensure_nas_directory(smb: SMBService, file_path: str) -> None:
    """確保 NAS 目錄存在

    Args:
        smb: SMB 服務實例
        file_path: 檔案完整路徑
    """
    # 取得目錄路徑
    dir_path = "/".join(file_path.split("/")[:-1])
    if not dir_path:
        return

    # 逐層建立目錄
    parts = dir_path.split("/")
    current_path = ""

    for part in parts:
        if not part:
            continue
        current_path = f"{current_path}/{part}" if current_path else part

        try:
            smb.create_directory(
                share_name=settings.knowledge_nas_share,
                path=current_path,
            )
        except Exception:
            # 目錄可能已存在，忽略錯誤
            pass


# ============================================================
# 回覆訊息
# ============================================================

async def reply_text(reply_token: str, text: str) -> None:
    """回覆文字訊息"""
    try:
        api = await get_messaging_api()
        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )
        logger.info(f"回覆訊息: {text[:50]}...")
    except Exception as e:
        logger.error(f"回覆訊息失敗: {e}")


# ============================================================
# AI 觸發判斷
# ============================================================

def should_trigger_ai(message_content: str, is_group: bool) -> bool:
    """
    判斷是否應該觸發 AI 處理

    規則：
    - 個人對話：所有訊息都觸發
    - 群組對話：訊息包含 @bot_name 時觸發（支援多個名稱）
    """
    if not is_group:
        # 個人對話：全部觸發
        return True

    # 群組對話：檢查是否被 @ 提及
    content_lower = message_content.lower()

    # 檢查配置的所有觸發名稱
    for name in settings.line_bot_trigger_names:
        if f"@{name.lower()}" in content_lower:
            return True

    return False


# ============================================================
# 查詢功能
# ============================================================

async def list_groups(
    is_active: bool | None = None,
    project_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """列出群組"""
    async with get_connection() as conn:
        # 建構查詢條件
        conditions = []
        params = []
        param_idx = 1

        if is_active is not None:
            conditions.append(f"g.is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        if project_id is not None:
            conditions.append(f"g.project_id = ${param_idx}")
            params.append(project_id)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

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
) -> tuple[list[dict], int]:
    """列出訊息"""
    async with get_connection() as conn:
        conditions = []
        params = []
        param_idx = 1

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

        where_clause = " AND ".join(conditions) if conditions else "1=1"

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


async def list_users(limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    """列出用戶"""
    async with get_connection() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM line_users")
        rows = await conn.fetch(
            """
            SELECT * FROM line_users
            ORDER BY updated_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [dict(row) for row in rows], total


async def get_group_by_id(group_id: UUID) -> dict | None:
    """取得群組詳情"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT g.*, p.name as project_name
            FROM line_groups g
            LEFT JOIN projects p ON g.project_id = p.id
            WHERE g.id = $1
            """,
            group_id,
        )
        return dict(row) if row else None


async def get_user_by_id(user_id: UUID) -> dict | None:
    """取得用戶詳情"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM line_users WHERE id = $1",
            user_id,
        )
        return dict(row) if row else None


async def bind_group_to_project(group_id: UUID, project_id: UUID) -> bool:
    """綁定群組到專案"""
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_groups
            SET project_id = $2, updated_at = NOW()
            WHERE id = $1
            """,
            group_id,
            project_id,
        )
        return result == "UPDATE 1"


async def unbind_group_from_project(group_id: UUID) -> bool:
    """解除群組與專案的綁定"""
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_groups
            SET project_id = NULL, updated_at = NOW()
            WHERE id = $1
            """,
            group_id,
        )
        return result == "UPDATE 1"


# ============================================================
# 檔案查詢
# ============================================================


async def list_files(
    line_group_id: UUID | None = None,
    line_user_id: UUID | None = None,
    file_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """列出檔案

    Args:
        line_group_id: 群組 UUID 過濾
        line_user_id: 用戶 UUID 過濾
        file_type: 檔案類型過濾（image, video, audio, file）
        limit: 最大數量
        offset: 偏移量

    Returns:
        (檔案列表, 總數)
    """
    async with get_connection() as conn:
        conditions = []
        params = []
        param_idx = 1

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

        where_clause = " AND ".join(conditions) if conditions else "1=1"

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


async def get_file_by_id(file_id: UUID) -> dict | None:
    """取得單一檔案詳情

    Args:
        file_id: 檔案 UUID

    Returns:
        檔案詳情（含關聯資訊）
    """
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
            WHERE f.id = $1
            """,
            file_id,
        )
        return dict(row) if row else None


async def read_file_from_nas(nas_path: str) -> bytes | None:
    """從 NAS 讀取檔案

    Args:
        nas_path: 相對於 linebot files 根目錄的路徑

    Returns:
        檔案內容 bytes，失敗回傳 None
    """
    full_path = f"{settings.line_files_nas_path}/{nas_path}"

    try:
        with SMBService(
            host=settings.knowledge_nas_host,
            username=settings.knowledge_nas_user,
            password=settings.knowledge_nas_password,
        ) as smb:
            content = smb.read_file(
                share_name=settings.knowledge_nas_share,
                path=full_path,
            )
            return content

    except Exception as e:
        logger.error(f"讀取 NAS 檔案失敗 {full_path}: {e}")
        return None


async def delete_file(file_id: UUID) -> bool:
    """刪除檔案（從 NAS 和資料庫）

    Args:
        file_id: 檔案 UUID

    Returns:
        是否成功刪除
    """
    # 取得檔案資訊
    file_info = await get_file_by_id(file_id)
    if not file_info:
        logger.warning(f"找不到檔案: {file_id}")
        return False

    nas_path = file_info.get("nas_path")

    # 從 NAS 刪除檔案
    if nas_path:
        full_path = f"{settings.line_files_nas_path}/{nas_path}"
        try:
            with SMBService(
                host=settings.knowledge_nas_host,
                username=settings.knowledge_nas_user,
                password=settings.knowledge_nas_password,
            ) as smb:
                smb.delete_item(
                    share_name=settings.knowledge_nas_share,
                    path=full_path,
                )
                logger.info(f"已從 NAS 刪除檔案: {full_path}")
        except Exception as e:
            # 如果 NAS 刪除失敗，記錄錯誤但繼續刪除資料庫記錄
            logger.error(f"從 NAS 刪除檔案失敗 {full_path}: {e}")

    # 從資料庫刪除記錄
    async with get_connection() as conn:
        # 先取得 message_id
        message_id = file_info.get("message_id")

        # 刪除檔案記錄
        await conn.execute(
            "DELETE FROM line_files WHERE id = $1",
            file_id,
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


async def generate_binding_code(user_id: int) -> tuple[str, datetime]:
    """
    產生 6 位數字綁定驗證碼

    Args:
        user_id: CTOS 用戶 ID

    Returns:
        (驗證碼, 過期時間)
    """
    # 產生 6 位數字驗證碼
    code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    async with get_connection() as conn:
        # 清除該用戶之前未使用的驗證碼
        await conn.execute(
            """
            DELETE FROM line_binding_codes
            WHERE user_id = $1 AND used_at IS NULL
            """,
            user_id,
        )

        # 建立新驗證碼
        await conn.execute(
            """
            INSERT INTO line_binding_codes (user_id, code, expires_at)
            VALUES ($1, $2, $3)
            """,
            user_id,
            code,
            expires_at,
        )

    logger.info(f"已產生綁定驗證碼: user_id={user_id}")
    return code, expires_at


async def verify_binding_code(line_user_uuid: UUID, code: str) -> tuple[bool, str]:
    """
    驗證綁定驗證碼並完成綁定

    Args:
        line_user_uuid: Line 用戶內部 UUID
        code: 驗證碼

    Returns:
        (是否成功, 訊息)
    """
    async with get_connection() as conn:
        # 查詢有效的驗證碼
        row = await conn.fetchrow(
            """
            SELECT id, user_id
            FROM line_binding_codes
            WHERE code = $1
              AND used_at IS NULL
              AND expires_at > NOW()
            """,
            code,
        )

        if not row:
            return False, "驗證碼無效或已過期"

        code_id = row["id"]
        ctos_user_id = row["user_id"]

        # 檢查該 Line 用戶是否已綁定其他帳號
        existing = await conn.fetchrow(
            """
            SELECT user_id FROM line_users
            WHERE id = $1 AND user_id IS NOT NULL
            """,
            line_user_uuid,
        )
        if existing and existing["user_id"]:
            return False, "此 Line 帳號已綁定其他 CTOS 帳號"

        # 檢查該 CTOS 用戶是否已綁定其他 Line 帳號
        existing_line = await conn.fetchrow(
            """
            SELECT id FROM line_users
            WHERE user_id = $1
            """,
            ctos_user_id,
        )
        if existing_line:
            return False, "此 CTOS 帳號已綁定其他 Line 帳號"

        # 執行綁定
        await conn.execute(
            """
            UPDATE line_users
            SET user_id = $2, updated_at = NOW()
            WHERE id = $1
            """,
            line_user_uuid,
            ctos_user_id,
        )

        # 標記驗證碼已使用
        await conn.execute(
            """
            UPDATE line_binding_codes
            SET used_at = NOW(), used_by_line_user_id = $2
            WHERE id = $1
            """,
            code_id,
            line_user_uuid,
        )

        logger.info(f"綁定成功: line_user={line_user_uuid}, ctos_user={ctos_user_id}")
        return True, "綁定成功！您現在可以使用 Line Bot 了。"


async def unbind_line_user(user_id: int) -> bool:
    """
    解除 CTOS 用戶的 Line 綁定

    Args:
        user_id: CTOS 用戶 ID

    Returns:
        是否成功解除綁定
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_users
            SET user_id = NULL, updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
        )
        if result == "UPDATE 1":
            logger.info(f"已解除綁定: ctos_user={user_id}")
            return True
        return False


async def get_binding_status(user_id: int) -> dict:
    """
    取得 CTOS 用戶的 Line 綁定狀態

    Args:
        user_id: CTOS 用戶 ID

    Returns:
        綁定狀態資訊
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT lu.display_name, lu.picture_url, lu.updated_at
            FROM line_users lu
            WHERE lu.user_id = $1
            """,
            user_id,
        )

        if row:
            return {
                "is_bound": True,
                "line_display_name": row["display_name"],
                "line_picture_url": row["picture_url"],
                "bound_at": row["updated_at"],
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
) -> tuple[bool, str | None]:
    """
    檢查 Line 用戶是否有權限使用 Bot

    規則：
    1. Line 用戶必須綁定 CTOS 帳號
    2. 如果是群組訊息，群組必須設為 allow_ai_response = true

    Args:
        line_user_uuid: Line 用戶內部 UUID
        line_group_uuid: Line 群組內部 UUID（個人對話為 None）

    Returns:
        (是否有權限, 拒絕原因)
    """
    async with get_connection() as conn:
        # 檢查用戶綁定
        user_row = await conn.fetchrow(
            "SELECT user_id FROM line_users WHERE id = $1",
            line_user_uuid,
        )

        if not user_row or not user_row["user_id"]:
            return False, "user_not_bound"

        # 如果是群組，檢查群組設定
        if line_group_uuid:
            group_row = await conn.fetchrow(
                "SELECT allow_ai_response FROM line_groups WHERE id = $1",
                line_group_uuid,
            )
            if not group_row or not group_row["allow_ai_response"]:
                return False, "group_not_allowed"

        return True, None


async def update_group_settings(group_id: UUID, allow_ai_response: bool) -> bool:
    """
    更新群組設定

    Args:
        group_id: 群組 UUID
        allow_ai_response: 是否允許 AI 回應

    Returns:
        是否成功更新
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_groups
            SET allow_ai_response = $2, updated_at = NOW()
            WHERE id = $1
            """,
            group_id,
            allow_ai_response,
        )
        return result == "UPDATE 1"


async def list_users_with_binding(
    limit: int = 50, offset: int = 0
) -> tuple[list[dict], int]:
    """列出用戶（包含 CTOS 綁定資訊）"""
    async with get_connection() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM line_users")
        rows = await conn.fetch(
            """
            SELECT lu.*, u.username as bound_username, u.display_name as bound_display_name
            FROM line_users lu
            LEFT JOIN users u ON lu.user_id = u.id
            ORDER BY lu.updated_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [dict(row) for row in rows], total


# ============================================================
# 對話管理
# ============================================================


async def reset_conversation(line_user_id: str) -> bool:
    """重置用戶的對話歷史

    設定 conversation_reset_at 為當前時間，
    之後查詢對話歷史時會忽略這個時間之前的訊息。

    Args:
        line_user_id: Line 用戶 ID

    Returns:
        是否成功
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE line_users
            SET conversation_reset_at = NOW()
            WHERE line_user_id = $1
            """,
            line_user_id,
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
    ".txt", ".md", ".json", ".csv", ".log",
    ".xml", ".yaml", ".yml", ".pdf",
}

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


def get_temp_image_path(line_message_id: str) -> str:
    """取得圖片暫存路徑

    Args:
        line_message_id: Line 訊息 ID

    Returns:
        暫存檔案路徑
    """
    return f"{TEMP_IMAGE_DIR}/{line_message_id}.jpg"


async def ensure_temp_image(line_message_id: str, nas_path: str) -> str | None:
    """確保圖片暫存檔存在

    如果暫存檔不存在，從 NAS 讀取並寫入暫存。

    Args:
        line_message_id: Line 訊息 ID
        nas_path: NAS 上的檔案路徑

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

    # 從 NAS 讀取圖片
    content = await read_file_from_nas(nas_path)
    if content is None:
        logger.warning(f"無法從 NAS 讀取圖片: {nas_path}")
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


async def get_image_info_by_line_message_id(line_message_id: str) -> dict | None:
    """透過 Line 訊息 ID 取得圖片資訊

    Args:
        line_message_id: Line 訊息 ID

    Returns:
        包含 nas_path 等資訊的字典，找不到回傳 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT f.nas_path, f.file_type, m.id as message_uuid
            FROM line_files f
            JOIN line_messages m ON f.message_id = m.id
            WHERE m.message_id = $1
              AND f.file_type = 'image'
            """,
            line_message_id,
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
) -> str | None:
    """確保檔案暫存檔存在

    如果暫存檔不存在，從 NAS 讀取並寫入暫存。

    Args:
        line_message_id: Line 訊息 ID
        nas_path: NAS 上的檔案路徑
        filename: 原始檔案名稱
        file_size: 檔案大小（用於檢查是否超過限制）

    Returns:
        暫存檔案路徑，失敗或不符合條件回傳 None
    """
    import os

    # 檢查是否為可讀取類型
    if not is_readable_file(filename):
        logger.debug(f"檔案類型不支援讀取: {filename}")
        return None

    # 檢查檔案大小
    if file_size is not None and file_size > MAX_READABLE_FILE_SIZE:
        logger.debug(f"檔案過大，跳過暫存: {filename} ({file_size} bytes)")
        return None

    # 確保暫存目錄存在
    os.makedirs(TEMP_FILE_DIR, exist_ok=True)

    temp_path = get_temp_file_path(line_message_id, filename)

    # 如果暫存檔已存在，直接回傳
    if os.path.exists(temp_path):
        return temp_path

    # 從 NAS 讀取檔案
    content = await read_file_from_nas(nas_path)
    if content is None:
        logger.warning(f"無法從 NAS 讀取檔案: {nas_path}")
        return None

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


async def get_file_info_by_line_message_id(line_message_id: str) -> dict | None:
    """透過 Line 訊息 ID 取得檔案資訊（非圖片）

    Args:
        line_message_id: Line 訊息 ID

    Returns:
        包含 nas_path, file_name, file_size 等資訊的字典，找不到回傳 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT f.nas_path, f.file_type, f.file_name, f.file_size,
                   m.id as message_uuid
            FROM line_files f
            JOIN line_messages m ON f.message_id = m.id
            WHERE m.message_id = $1
              AND f.file_type = 'file'
            """,
            line_message_id,
        )
        return dict(row) if row else None
