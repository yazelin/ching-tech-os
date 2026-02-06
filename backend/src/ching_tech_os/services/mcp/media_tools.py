"""媒體處理相關 MCP 工具

包含：download_web_image, convert_pdf_to_images
"""

import uuid as uuid_module
from datetime import datetime
from pathlib import Path as FilePath

from .server import mcp, logger, ensure_db_connection, check_mcp_tool_permission, TAIPEI_TZ
from ...database import get_connection


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
