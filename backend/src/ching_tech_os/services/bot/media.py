"""平台無關的媒體處理

提供暫存管理、NAS 存取等通用媒體處理功能。
目前從 linebot.py 中提取可共用的部分。
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger("bot.media")

# 暫存目錄（各平台共用）
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
