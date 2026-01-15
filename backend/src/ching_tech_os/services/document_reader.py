"""
Document Reader Service

提供文件內容讀取功能，支援 Word、Excel、PowerPoint、PDF 等文件格式的文字提取。
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation


# 支援的副檔名
SUPPORTED_EXTENSIONS = {".docx", ".xlsx", ".pptx", ".pdf"}

# 舊版格式（提示轉檔）
LEGACY_EXTENSIONS = {".doc", ".xls", ".ppt"}

# 檔案大小限制（bytes）
MAX_FILE_SIZE = {
    ".pdf": 10 * 1024 * 1024,   # 10 MB
    ".docx": 10 * 1024 * 1024,  # 10 MB
    ".xlsx": 5 * 1024 * 1024,   # 5 MB
    ".pptx": 10 * 1024 * 1024,  # 10 MB
}

# 最大輸出字元數
MAX_OUTPUT_CHARS = 100000


class DocumentReadError(Exception):
    """文件讀取錯誤"""
    pass


class PasswordProtectedError(DocumentReadError):
    """文件有密碼保護"""
    pass


class CorruptedFileError(DocumentReadError):
    """文件損壞"""
    pass


class UnsupportedFormatError(DocumentReadError):
    """不支援的格式"""
    pass


class FileTooLargeError(DocumentReadError):
    """檔案過大"""
    pass


@dataclass
class DocumentContent:
    """文件解析結果"""
    text: str                      # 提取的純文字內容
    format: str                    # 原始格式 (docx, xlsx, pptx, pdf)
    page_count: Optional[int]      # 頁數（PDF）或工作表數（Excel）
    metadata: dict                 # 額外資訊（標題、作者等）
    truncated: bool                # 是否因大小限制而截斷
    error: Optional[str]           # 解析錯誤訊息（部分成功時）


def get_supported_extensions() -> set[str]:
    """取得支援的副檔名"""
    return SUPPORTED_EXTENSIONS.copy()


def is_supported(file_path: str) -> bool:
    """檢查檔案是否支援"""
    ext = Path(file_path).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS


def is_legacy_format(file_path: str) -> bool:
    """檢查是否為舊版格式"""
    ext = Path(file_path).suffix.lower()
    return ext in LEGACY_EXTENSIONS


def extract_text(file_path: str) -> DocumentContent:
    """
    提取文件的文字內容

    Args:
        file_path: 檔案路徑

    Returns:
        DocumentContent 包含提取的文字和元資料

    Raises:
        FileNotFoundError: 檔案不存在
        UnsupportedFormatError: 不支援的格式
        FileTooLargeError: 檔案過大
        PasswordProtectedError: 文件有密碼保護
        CorruptedFileError: 文件損壞
    """
    path = Path(file_path)

    # 檢查檔案存在
    if not path.exists():
        raise FileNotFoundError(f"檔案不存在: {file_path}")

    ext = path.suffix.lower()

    # 檢查舊版格式
    if ext in LEGACY_EXTENSIONS:
        raise UnsupportedFormatError(
            f"不支援舊版格式 {ext}，請轉存為新版格式 "
            f"(.docx/.xlsx/.pptx)"
        )

    # 檢查支援的格式
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"不支援的檔案格式: {ext}。"
            f"支援的格式: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    # 檢查檔案大小
    file_size = path.stat().st_size
    max_size = MAX_FILE_SIZE.get(ext, 10 * 1024 * 1024)
    if file_size > max_size:
        raise FileTooLargeError(
            f"檔案過大 ({file_size / 1024 / 1024:.1f} MB)，"
            f"請使用小於 {max_size / 1024 / 1024:.0f} MB 的檔案"
        )

    # 根據格式選擇解析器
    extractors = {
        ".docx": _extract_docx,
        ".xlsx": _extract_xlsx,
        ".pptx": _extract_pptx,
        ".pdf": _extract_pdf,
    }

    extractor = extractors[ext]
    return extractor(file_path)


def _extract_docx(file_path: str) -> DocumentContent:
    """解析 Word 文件"""
    try:
        doc = Document(file_path)
    except Exception as e:
        error_msg = str(e).lower()
        if "password" in error_msg or "encrypted" in error_msg:
            raise PasswordProtectedError("此文件有密碼保護，無法讀取")
        raise CorruptedFileError(f"無法解析 Word 文件: {e}")

    paragraphs = []

    # 提取段落
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text)

    # 提取表格
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells)
            if row_text.strip():
                paragraphs.append(row_text)

    text = "\n".join(paragraphs)

    # 提取元資料
    metadata = {}
    core_props = doc.core_properties
    if core_props.title:
        metadata["title"] = core_props.title
    if core_props.author:
        metadata["author"] = core_props.author

    # 檢查是否需要截斷
    truncated = False
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + f"\n\n[內容已截斷，原文共 {len(text)} 字元]"
        truncated = True

    return DocumentContent(
        text=text,
        format="docx",
        page_count=None,
        metadata=metadata,
        truncated=truncated,
        error=None
    )


def _extract_xlsx(file_path: str) -> DocumentContent:
    """解析 Excel 試算表"""
    try:
        wb = load_workbook(file_path, data_only=True, read_only=True)
    except Exception as e:
        error_msg = str(e).lower()
        if "password" in error_msg or "encrypted" in error_msg:
            raise PasswordProtectedError("此文件有密碼保護，無法讀取")
        raise CorruptedFileError(f"無法解析 Excel 檔案: {e}")

    result = []
    sheet_count = len(wb.sheetnames)

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        result.append(f"=== 工作表: {sheet_name} ===")

        row_count = 0
        for row in sheet.iter_rows(values_only=True):
            # 過濾完全空白的行
            if any(cell is not None for cell in row):
                row_text = " | ".join(
                    str(cell) if cell is not None else ""
                    for cell in row
                )
                result.append(row_text)
                row_count += 1

        if row_count == 0:
            result.append("（空白工作表）")

        result.append("")  # 工作表間空行

    wb.close()

    text = "\n".join(result)

    # 檢查是否需要截斷
    truncated = False
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + f"\n\n[內容已截斷，原文共 {len(text)} 字元]"
        truncated = True

    return DocumentContent(
        text=text,
        format="xlsx",
        page_count=sheet_count,
        metadata={"sheet_names": wb.sheetnames},
        truncated=truncated,
        error=None
    )


def _extract_pptx(file_path: str) -> DocumentContent:
    """解析 PowerPoint 簡報"""
    try:
        prs = Presentation(file_path)
    except Exception as e:
        error_msg = str(e).lower()
        if "password" in error_msg or "encrypted" in error_msg:
            raise PasswordProtectedError("此文件有密碼保護，無法讀取")
        raise CorruptedFileError(f"無法解析 PowerPoint 檔案: {e}")

    result = []
    slide_count = len(prs.slides)

    for i, slide in enumerate(prs.slides, 1):
        result.append(f"=== 投影片 {i} ===")

        slide_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_text.append(shape.text)

        if slide_text:
            result.extend(slide_text)
        else:
            result.append("（無文字內容）")

        result.append("")  # 投影片間空行

    text = "\n".join(result)

    # 檢查是否需要截斷
    truncated = False
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + f"\n\n[內容已截斷，原文共 {len(text)} 字元]"
        truncated = True

    return DocumentContent(
        text=text,
        format="pptx",
        page_count=slide_count,
        metadata={},
        truncated=truncated,
        error=None
    )


def _extract_pdf(file_path: str) -> DocumentContent:
    """解析 PDF 文件"""
    try:
        with fitz.open(file_path) as doc:
            # 檢查是否需要密碼
            if doc.needs_pass:
                raise PasswordProtectedError("此文件有密碼保護，無法讀取")

            result = []
            page_count = len(doc)
            has_text = False

            for page in doc:
                text = page.get_text()
                if text.strip():
                    result.append(text)
                    has_text = True

            # 檢查是否為純圖片 PDF
            if not has_text:
                return DocumentContent(
                    text="此 PDF 為掃描圖片，沒有可提取的文字。建議截圖後上傳讓 AI 讀取。",
                    format="pdf",
                    page_count=page_count,
                    metadata={"is_scanned": True},
                    truncated=False,
                    error="純圖片 PDF，無文字層"
                )

            text = "\n".join(result)

            # 檢查是否需要截斷
            truncated = False
            if len(text) > MAX_OUTPUT_CHARS:
                text = text[:MAX_OUTPUT_CHARS] + f"\n\n[內容已截斷，原文共 {len(text)} 字元]"
                truncated = True

            return DocumentContent(
                text=text,
                format="pdf",
                page_count=page_count,
                metadata={},
                truncated=truncated,
                error=None
            )
    except PasswordProtectedError:
        raise
    except Exception as e:
        raise CorruptedFileError(f"無法解析 PDF 檔案: {e}")
