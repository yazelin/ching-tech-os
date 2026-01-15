"""Files API 輔助函數測試

測試 /api/files 模組的輔助函數：
- _validate_zone() - zone 驗證
- _check_path_traversal() - 路徑穿越檢查
- _get_file_path() - 檔案路徑計算
- _get_mime_type() - MIME 類型判斷
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from fastapi import HTTPException

from ching_tech_os.api.files import (
    _validate_zone,
    _check_path_traversal,
    _get_file_path,
    _get_mime_type,
)
from ching_tech_os.services.path_manager import StorageZone


# ============================================================
# _validate_zone() 測試
# ============================================================

class TestValidateZone:
    """zone 驗證測試"""

    def test_valid_ctos_zone(self):
        """ctos zone 應通過驗證"""
        result = _validate_zone("ctos")
        assert result == StorageZone.CTOS

    def test_valid_shared_zone(self):
        """shared zone 應通過驗證"""
        result = _validate_zone("shared")
        assert result == StorageZone.SHARED

    def test_valid_temp_zone(self):
        """temp zone 應通過驗證"""
        result = _validate_zone("temp")
        assert result == StorageZone.TEMP

    def test_valid_local_zone(self):
        """local zone 應通過驗證"""
        result = _validate_zone("local")
        assert result == StorageZone.LOCAL

    def test_invalid_zone_raises_400(self):
        """無效的 zone 應拋出 400 錯誤"""
        with pytest.raises(HTTPException) as exc_info:
            _validate_zone("invalid")
        assert exc_info.value.status_code == 400
        assert "無效的儲存區域" in exc_info.value.detail

    def test_uppercase_zone_fails(self):
        """大寫 zone 應失敗（區分大小寫）"""
        with pytest.raises(HTTPException) as exc_info:
            _validate_zone("CTOS")
        assert exc_info.value.status_code == 400


# ============================================================
# _check_path_traversal() 測試
# ============================================================

class TestCheckPathTraversal:
    """路徑穿越檢查測試"""

    def test_normal_path_passes(self):
        """正常路徑應通過"""
        # 不應拋出異常
        _check_path_traversal("path/to/file.txt")
        _check_path_traversal("亦達光學/文件/report.pdf")

    def test_double_dot_blocked(self):
        """.. 應被阻擋"""
        with pytest.raises(HTTPException) as exc_info:
            _check_path_traversal("../etc/passwd")
        assert exc_info.value.status_code == 400
        assert "無效的路徑" in exc_info.value.detail

    def test_middle_double_dot_blocked(self):
        """路徑中間的 .. 應被阻擋"""
        with pytest.raises(HTTPException) as exc_info:
            _check_path_traversal("path/../../../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_encoded_double_dot_blocked(self):
        """編碼的 .. 也應被阻擋"""
        with pytest.raises(HTTPException) as exc_info:
            _check_path_traversal("path/..%2F..%2Fetc/passwd")
        # 這個可能不會被擋到，因為我們只檢查字面 ..
        # 但 URL 解碼後會有 ..


# ============================================================
# _get_file_path() 測試
# ============================================================

class TestGetFilePath:
    """檔案路徑計算測試"""

    def test_ctos_path(self):
        """CTOS zone 路徑計算"""
        result = _get_file_path(StorageZone.CTOS, "linebot/files/test.jpg")
        assert str(result) == "/mnt/nas/ctos/linebot/files/test.jpg"

    def test_shared_path(self):
        """SHARED zone 路徑計算"""
        result = _get_file_path(StorageZone.SHARED, "亦達光學/doc.pdf")
        assert str(result) == "/mnt/nas/projects/亦達光學/doc.pdf"

    def test_temp_path(self):
        """TEMP zone 路徑計算"""
        result = _get_file_path(StorageZone.TEMP, "converted/page.png")
        assert str(result) == "/tmp/ctos/converted/page.png"


# ============================================================
# _get_mime_type() 測試
# ============================================================

class TestGetMimeType:
    """MIME 類型判斷測試"""

    def test_pdf_mime_type(self):
        """PDF 檔案 MIME 類型"""
        result = _get_mime_type("document.pdf")
        assert result == "application/pdf"

    def test_jpg_mime_type(self):
        """JPG 圖片 MIME 類型"""
        result = _get_mime_type("photo.jpg")
        assert result == "image/jpeg"

    def test_png_mime_type(self):
        """PNG 圖片 MIME 類型"""
        result = _get_mime_type("image.png")
        assert result == "image/png"

    def test_txt_mime_type(self):
        """文字檔 MIME 類型"""
        result = _get_mime_type("readme.txt")
        assert result == "text/plain"

    def test_unknown_mime_type(self):
        """未知類型應回傳 octet-stream"""
        result = _get_mime_type("file.xyz123")
        assert result == "application/octet-stream"

    def test_chinese_filename(self):
        """中文檔名應正確判斷"""
        result = _get_mime_type("報告書.pdf")
        assert result == "application/pdf"

