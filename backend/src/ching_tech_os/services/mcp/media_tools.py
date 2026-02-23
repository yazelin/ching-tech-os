"""媒體處理相關 MCP 工具

包含：download_web_image, download_web_file, convert_pdf_to_images
"""

import hashlib
import os
import uuid as uuid_module
from datetime import datetime
from pathlib import Path as FilePath
from urllib.parse import unquote, urlparse

import httpx

from .server import mcp, logger, ensure_db_connection, check_mcp_tool_permission, TAIPEI_TZ
from ...database import get_connection

# download_web_file 允許的 MIME type 前綴與副檔名白名單
_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip",
    "application/x-zip-compressed",
    "text/plain",
    "text/csv",
    "text/markdown",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

_MIME_TO_EXT: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "text/markdown": ".md",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

# 50 MB 下載上限
_MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024


@mcp.tool()
async def download_web_image(
    url: str,
    ctos_user_id: int | None = None,
) -> str:
    """
    下載網路圖片並準備為回覆訊息。用於將網路上找到的參考圖片傳送給用戶。

    使用時機：當用戶要求尋找參考圖片、範例圖、示意圖等，透過 WebSearch/WebFetch 找到圖片 URL 後，
    使用此工具下載圖片並傳送給用戶。可多次呼叫以傳送多張圖片（建議不超過 4 張）。

    Args:
        url: 圖片的完整 URL（支援 jpg、jpeg、png、gif、webp 格式）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）

    Returns:
        包含檔案訊息標記的字串，系統會自動在回覆中顯示圖片
    """
    import json
    from ..bot.media import download_image_from_url

    local_path = await download_image_from_url(url)
    if not local_path:
        return f"❌ 無法下載圖片：{url}"

    import os
    file_name = os.path.basename(local_path)
    file_info = {
        "type": "image",
        "url": local_path,
        "original_url": url,
        "name": file_name,
    }
    marker = f"[FILE_MESSAGE:{json.dumps(file_info, ensure_ascii=False)}]"
    return f"已下載圖片 {file_name}\n{marker}"


def _extract_filename_from_url(url: str) -> str:
    """從 URL 路徑提取檔案名稱（不含查詢參數）。"""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    basename = os.path.basename(path)
    # 移除查詢參數殘留
    if "?" in basename:
        basename = basename.split("?")[0]
    return basename


@mcp.tool()
async def download_web_file(
    url: str,
    filename: str = "",
    ctos_user_id: int | None = None,
) -> str:
    """
    下載網路上的文件檔案（PDF、Word、Excel、PowerPoint、圖片等）到 CTOS 暫存區。

    使用時機：當用戶提供一個文件 URL 並要求下載或歸檔時，先用此工具下載檔案，
    再使用 archive_to_library 歸檔到圖書館。

    支援格式：PDF、DOC/DOCX、XLS/XLSX、PPT/PPTX、ZIP、TXT、CSV、MD、JPG/PNG/GIF/WebP
    檔案大小上限：50 MB

    Args:
        url: 檔案的完整 URL
        filename: 指定儲存的檔案名稱（可選，留空則自動從 URL 推斷）
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）

    Returns:
        下載成功：ctos:// 路徑（可直接傳給 archive_to_library 的 source_path）
        下載失敗：錯誤訊息
    """
    await ensure_db_connection()

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("download_web_file", ctos_user_id)
    if not allowed:
        return f"❌ {error_msg}"

    from ...config import settings

    # 建立下載目錄：ctos://linebot/files/web-downloads/{date}/{uuid8}/
    today = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")
    unique_id = str(uuid_module.uuid4())[:8]
    download_dir = FilePath(settings.linebot_local_path) / "web-downloads" / today / unique_id
    download_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=5.0, pool=5.0),
        ) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    return f"❌ 下載失敗：HTTP {resp.status_code}（{url}）"

                # 檢查 Content-Type
                content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type not in _ALLOWED_CONTENT_TYPES:
                    return (
                        f"❌ 不支援的檔案類型：{content_type}\n"
                        f"支援的類型：PDF、DOC/DOCX、XLS/XLSX、PPT/PPTX、ZIP、TXT、CSV、圖片"
                    )

                # 決定檔案名稱
                if not filename:
                    # 嘗試從 Content-Disposition 取得
                    cd = resp.headers.get("content-disposition", "")
                    if "filename=" in cd:
                        # 解析 filename="xxx" 或 filename=xxx
                        for part in cd.split(";"):
                            part = part.strip()
                            if part.startswith("filename="):
                                filename = part[len("filename="):].strip('"').strip("'")
                                break

                if not filename:
                    # 從 URL 推斷
                    filename = _extract_filename_from_url(url)

                if not filename:
                    # 最後手段：用 hash + MIME 推斷副檔名
                    ext = _MIME_TO_EXT.get(content_type, "")
                    filename = hashlib.md5(url.encode()).hexdigest()[:12] + ext

                # 確保有正確副檔名
                _, ext = os.path.splitext(filename)
                if not ext:
                    mime_ext = _MIME_TO_EXT.get(content_type, "")
                    if mime_ext:
                        filename += mime_ext

                file_path = download_dir / filename

                # 串流下載，邊下邊寫邊檢查大小
                size = 0
                with open(file_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        size += len(chunk)
                        if size > _MAX_DOWNLOAD_SIZE:
                            f.close()
                            file_path.unlink(missing_ok=True)
                            return f"❌ 檔案過大（超過 {_MAX_DOWNLOAD_SIZE // 1024 // 1024} MB）"
                        f.write(chunk)

        # 建構 ctos:// 路徑
        # linebot_local_path = {ctos_mount_path}/{line_files_nas_path}
        # 實際路徑：{ctos_mount_path}/linebot/files/web-downloads/...
        # ctos:// 路徑：ctos://linebot/files/web-downloads/...
        from ..path_manager import path_manager
        ctos_path = path_manager.to_storage(str(file_path))

        size_kb = size / 1024
        if size_kb >= 1024:
            size_str = f"{size_kb / 1024:.1f} MB"
        else:
            size_str = f"{size_kb:.0f} KB"

        logger.info(f"下載網路檔案: {url} -> {file_path} ({size_str})")
        return (
            f"✅ 已下載檔案：{filename}（{size_str}）\n"
            f"暫存路徑：{ctos_path}\n"
            f"可使用 archive_to_library 將此檔案歸檔到圖書館。"
        )

    except httpx.TimeoutException:
        return f"❌ 下載逾時（URL: {url}）"
    except httpx.RequestError as e:
        logger.warning(f"下載檔案網路錯誤: {url}: {e}")
        return f"❌ 網路錯誤：{e}"
    except Exception as e:
        logger.error(f"下載檔案異常: {url}: {e}")
        return f"❌ 下載失敗：{e}"


@mcp.tool()
async def convert_pdf_to_images(
    pdf_path: str,
    pages: str = "all",
    output_format: str = "png",
    dpi: int = 150,
    max_pages: int = 20,
    ctos_user_id: int | None = None,
) -> str:
    """
    將 PDF 轉換為圖片

    Args:
        pdf_path: PDF 檔案路徑（NAS 路徑或暫存路徑）
        pages: 要轉換的頁面，預設 "all"
            - "0"：只查詢頁數，不轉換
            - "1"：只轉換第 1 頁
            - "1-3"：轉換第 1 到 3 頁
            - "1,3,5"：轉換第 1、3、5 頁
            - "all"：轉換全部頁面
        output_format: 輸出格式，可選 "png"（預設）或 "jpg"
        dpi: 解析度，預設 150，範圍 72-600
        max_pages: 最大頁數限制，預設 20
        ctos_user_id: CTOS 用戶 ID（從對話識別取得，用於權限檢查）
    """
    await ensure_db_connection()

    import json

    # 權限檢查
    allowed, error_msg = await check_mcp_tool_permission("convert_pdf_to_images", ctos_user_id)
    if not allowed:
        return json.dumps({
            "success": False,
            "error": error_msg
        }, ensure_ascii=False)

    from ...config import settings
    from ..document_reader import (
        CorruptedFileError,
        PasswordProtectedError,
        UnsupportedFormatError,
        convert_pdf_to_images as do_convert,
    )

    # 驗證參數
    if output_format not in ("png", "jpg"):
        return json.dumps({
            "success": False,
            "error": f"不支援的輸出格式: {output_format}，請使用 png 或 jpg"
        }, ensure_ascii=False)

    if not 72 <= dpi <= 600:
        return json.dumps({
            "success": False,
            "error": f"DPI 必須在 72-600 之間，目前為 {dpi}"
        }, ensure_ascii=False)

    # 使用 PathManager 解析路徑
    # 支援：nas://..., ctos://..., shared://..., temp://..., /專案A/..., groups/... 等格式
    from ..path_manager import path_manager, StorageZone

    try:
        parsed = path_manager.parse(pdf_path)
    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)

    # 安全檢查：只允許 CTOS、SHARED、TEMP 區域
    if parsed.zone not in (StorageZone.CTOS, StorageZone.SHARED, StorageZone.TEMP):
        return json.dumps({
            "success": False,
            "error": f"不允許存取 {parsed.zone.value}:// 區域的檔案"
        }, ensure_ascii=False)

    # 取得實際檔案系統路徑
    actual_path = path_manager.to_filesystem(pdf_path)

    # 檢查檔案存在
    if not FilePath(actual_path).exists():
        return json.dumps({
            "success": False,
            "error": f"PDF 檔案不存在: {pdf_path}"
        }, ensure_ascii=False)

    try:
        # 建立輸出目錄
        today = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")
        unique_id = str(uuid_module.uuid4())[:8]
        output_dir = f"{settings.linebot_local_path}/pdf-converted/{today}/{unique_id}"

        # 執行轉換
        result = do_convert(
            file_path=actual_path,
            output_dir=output_dir,
            pages=pages,
            dpi=dpi,
            output_format=output_format,
            max_pages=max_pages,
        )

        return json.dumps({
            "success": result.success,
            "total_pages": result.total_pages,
            "converted_pages": result.converted_pages,
            "images": result.images,
            "message": result.message,
        }, ensure_ascii=False)

    except FileNotFoundError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except PasswordProtectedError:
        return json.dumps({
            "success": False,
            "error": "此 PDF 有密碼保護，無法轉換"
        }, ensure_ascii=False)
    except UnsupportedFormatError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except CorruptedFileError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except ValueError as e:
        # 頁碼格式錯誤
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"PDF 轉換失敗: {e}")
        return json.dumps({
            "success": False,
            "error": f"轉換失敗: {str(e)}"
        }, ensure_ascii=False)
