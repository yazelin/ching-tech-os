"""平台無關的媒體處理

提供暫存管理、NAS 存取等通用媒體處理功能。
目前從 linebot.py 中提取可共用的部分。
"""

import hashlib
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger("bot.media")

# 暫存目錄（各平台共用）
TEMP_IMAGE_DIR = "/tmp/bot-images"
TEMP_FILE_DIR = "/tmp/bot-files"

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
    """判斷檔案是否為可讀取類型"""
    if not filename:
        return False
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in READABLE_FILE_EXTENSIONS


def is_legacy_office_file(filename: str) -> bool:
    """判斷檔案是否為舊版 Office 格式"""
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    return ext in LEGACY_OFFICE_EXTENSIONS


def is_document_file(filename: str) -> bool:
    """判斷檔案是否需要文件解析"""
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    return ext in DOCUMENT_EXTENSIONS


def parse_pdf_temp_path(temp_path: str) -> tuple[str, str]:
    """解析 PDF 特殊格式路徑

    PDF 上傳時會同時保留原始檔和文字版，格式為 "PDF:xxx.pdf|TXT:xxx.txt"

    Returns:
        (pdf_path, txt_path) 元組
    """
    if not temp_path.startswith("PDF:"):
        return (temp_path, "")

    parts = temp_path.split("|")
    pdf_path = parts[0].replace("PDF:", "")
    txt_path = parts[1].replace("TXT:", "") if len(parts) > 1 else ""
    return (pdf_path, txt_path)


def ensure_temp_dir(directory: str) -> None:
    """確保暫存目錄存在"""
    os.makedirs(directory, exist_ok=True)


# === 網路圖片 URL 提取與下載 ===

# 下載圖片暫存目錄
DOWNLOADED_IMAGE_DIR = "/tmp/bot-downloaded-images"

# 圖片 URL 正則（匹配常見圖片副檔名）
_IMAGE_URL_PATTERN = re.compile(
    r'https?://[^\s\n\[\]()<>"\']+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s\n\[\]()<>"\']*)?',
    re.IGNORECASE,
)


def extract_image_urls(text: str) -> list[str]:
    """從文字中提取圖片 URL（去重）"""
    urls = _IMAGE_URL_PATTERN.findall(text)
    seen = set()
    unique = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


async def download_image_from_url(url: str) -> str | None:
    """下載圖片 URL 到暫存目錄，回傳本地路徑

    Returns:
        本地檔案路徑，或下載失敗時回傳 None
    """
    import httpx

    os.makedirs(DOWNLOADED_IMAGE_DIR, exist_ok=True)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"下載圖片失敗 HTTP {resp.status_code}: {url}")
                return None

            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                logger.warning(f"非圖片內容 {content_type}: {url}")
                return None

            # 從 URL 推斷副檔名
            ext = ".jpg"
            for e in [".png", ".gif", ".webp", ".jpeg"]:
                if e in url.lower():
                    ext = e
                    break

            filename = hashlib.md5(url.encode()).hexdigest()[:12] + ext
            file_path = os.path.join(DOWNLOADED_IMAGE_DIR, filename)

            with open(file_path, "wb") as f:
                f.write(resp.content)

            logger.info(f"下載網路圖片: {url} -> {file_path}")
            return file_path

    except Exception as e:
        logger.warning(f"下載圖片異常: {url}: {e}")
        return None
