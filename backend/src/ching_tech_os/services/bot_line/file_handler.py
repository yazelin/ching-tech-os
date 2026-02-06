"""Line Bot 檔案處理"""

import logging
from datetime import datetime
from uuid import UUID

import httpx

from ...config import settings
from ...database import get_connection
from ..local_file import LocalFileService, LocalFileError, create_linebot_file_service
from .. import document_reader
from .constants import FILE_TYPE_EXTENSIONS, MIME_TO_EXTENSION

# 暫存目錄與檔案判斷函式（從 bot.media 匯入）
from ..bot.media import (
    TEMP_IMAGE_DIR,
    TEMP_FILE_DIR,
    READABLE_FILE_EXTENSIONS,
    LEGACY_OFFICE_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    MAX_READABLE_FILE_SIZE,
    is_readable_file,
    is_legacy_office_file,
    is_document_file,
)

logger = logging.getLogger("linebot")


async def save_file_record(
    message_uuid: UUID,
    file_type: str,
    file_name: str | None = None,
    file_size: int | None = None,
    mime_type: str | None = None,
    nas_path: str | None = None,
    duration: int | None = None,
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
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO bot_files (
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
            "UPDATE bot_messages SET file_id = $1 WHERE id = $2",
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
    access_token = settings.line_channel_access_token
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
) -> bool:
    """儲存檔案到 NAS（透過掛載路徑）

    Args:
        relative_path: 相對路徑（不含共享資料夾和基本路徑）
        content: 檔案內容

    Returns:
        是否成功
    """
    try:
        file_service = create_linebot_file_service()
        # write_file 會自動建立目錄
        file_service.write_file(relative_path, content)
        return True
    except LocalFileError as e:
        logger.error(f"儲存到 NAS 失敗 {relative_path}: {e}")
        return False


async def read_file_from_nas(
    nas_path: str,
) -> bytes | None:
    """從 NAS 讀取檔案（透過掛載路徑）

    Args:
        nas_path: 相對於 linebot files 根目錄的路徑

    Returns:
        檔案內容 bytes，失敗回傳 None
    """
    try:
        file_service = create_linebot_file_service()
        content = file_service.read_file(nas_path)
        return content
    except LocalFileError as e:
        logger.error(f"讀取 NAS 檔案失敗 {nas_path}: {e}")
        return None


async def delete_file(
    file_id: UUID,
) -> bool:
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
        try:
            file_service = create_linebot_file_service()
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
            "DELETE FROM bot_files WHERE id = $1",
            file_id,
        )
        logger.info(f"已從資料庫刪除檔案記錄: {file_id}")

        # 更新訊息的 file_id 為 NULL
        if message_id:
            await conn.execute(
                "UPDATE bot_messages SET file_id = NULL WHERE id = $1",
                message_id,
            )

    return True


async def list_files(
    line_group_id: UUID | None = None,
    line_user_id: UUID | None = None,
    file_type: str | None = None,
    platform_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """列出檔案

    Args:
        line_group_id: 群組 UUID 過濾
        line_user_id: 用戶 UUID 過濾
        file_type: 檔案類型過濾（image, video, audio, file）
        platform_type: 平台類型過濾（line, telegram）
        limit: 最大數量
        offset: 偏移量

    Returns:
        (檔案列表, 總數)
    """
    async with get_connection() as conn:
        conditions: list[str] = []
        params: list = []
        param_idx = 1

        if line_group_id is not None:
            conditions.append(f"m.bot_group_id = ${param_idx}")
            params.append(line_group_id)
            param_idx += 1

        if line_user_id is not None:
            conditions.append(f"m.bot_user_id = ${param_idx}")
            params.append(line_user_id)
            param_idx += 1

        if file_type is not None:
            conditions.append(f"f.file_type = ${param_idx}")
            params.append(file_type)
            param_idx += 1

        if platform_type is not None:
            conditions.append(f"m.platform_type = ${param_idx}")
            params.append(platform_type)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 查詢總數
        count_query = f"""
            SELECT COUNT(*)
            FROM bot_files f
            JOIN bot_messages m ON f.message_id = m.id
            WHERE {where_clause}
        """
        total = await conn.fetchval(count_query, *params)

        # 查詢列表（包含用戶和群組資訊）
        query = f"""
            SELECT f.*,
                   m.bot_group_id,
                   m.bot_user_id,
                   u.display_name as user_display_name,
                   g.name as group_name
            FROM bot_files f
            JOIN bot_messages m ON f.message_id = m.id
            LEFT JOIN bot_users u ON m.bot_user_id = u.id
            LEFT JOIN bot_groups g ON m.bot_group_id = g.id
            WHERE {where_clause}
            ORDER BY f.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows], total


async def get_file_by_id(
    file_id: UUID,
) -> dict | None:
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
                   m.bot_group_id,
                   m.bot_user_id,
                   u.display_name as user_display_name,
                   g.name as group_name,
                   g.platform_group_id as source_group_id
            FROM bot_files f
            JOIN bot_messages m ON f.message_id = m.id
            LEFT JOIN bot_users u ON m.bot_user_id = u.id
            LEFT JOIN bot_groups g ON m.bot_group_id = g.id
            WHERE f.id = $1
            """,
            file_id,
        )
        return dict(row) if row else None


# ============================================================
# 圖片暫存服務
# ============================================================


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
) -> str | None:
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


async def get_image_info_by_line_message_id(
    line_message_id: str,
) -> dict | None:
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
            FROM bot_files f
            JOIN bot_messages m ON f.message_id = m.id
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
    對於 Office 文件和 PDF，會先解析成純文字再存入 .txt 暫存檔。

    Args:
        line_message_id: Line 訊息 ID
        nas_path: NAS 上的檔案路徑
        filename: 原始檔案名稱
        file_size: 檔案大小（用於檢查是否超過限制）

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

    # 從 NAS 讀取檔案
    content = await read_file_from_nas(nas_path)
    if content is None:
        logger.warning(f"無法從 NAS 讀取檔案: {nas_path}")
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
) -> dict | None:
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
            FROM bot_files f
            JOIN bot_messages m ON f.message_id = m.id
            WHERE m.message_id = $1
              AND f.file_type = 'file'
            """,
            line_message_id,
        )
        return dict(row) if row else None
