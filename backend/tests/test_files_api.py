"""Files API 輔助函數測試

測試 /api/files 模組的輔助函數：
- _validate_zone() - zone 驗證
- _check_path_traversal() - 路徑穿越檢查
- _get_file_path() - 檔案路徑計算
- _get_mime_type() - MIME 類型判斷
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from pathlib import Path
from fastapi import HTTPException

from ching_tech_os.api.files import (
    _validate_zone,
    _check_path_traversal,
    _get_file_path,
    _get_mime_type,
    _get_nas_smb_service,
    _read_nas_file,
    _read_local_file,
    _read_file_content,
    download_file,
    read_file,
)
from ching_tech_os.models.auth import SessionData
from ching_tech_os.services.path_manager import StorageZone
from ching_tech_os.services.smb import (
    SMBError,
    SMBConnectionError,
    SMBFileNotFoundError,
    SMBPermissionError,
)


def _make_session(password: str = "pw") -> SessionData:
    now = datetime.now()
    return SessionData(
        username="tester",
        password=password,
        nas_host="10.0.0.1",
        user_id=1,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role="admin",
        app_permissions={},
    )


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

    def test_nas_zone_raises_value_error(self):
        """NAS zone 不支援本地路徑轉換"""
        with pytest.raises(ValueError):
            _get_file_path(StorageZone.NAS, "public/a.txt")


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


# ============================================================
# _get_nas_smb_service() 測試
# ============================================================

class TestGetNasSmbService:
    """NAS SMB 服務取得測試"""

    def test_use_nas_token_connection(self):
        conn = type("Conn", (), {})()
        conn.host = "10.0.0.9"
        conn.get_smb_service = lambda: "svc-by-token"

        with patch(
            "ching_tech_os.api.files.nas_connection_manager.get_connection",
            return_value=conn,
        ):
            smb, host = _get_nas_smb_service("token-123", _make_session())

        assert smb == "svc-by-token"
        assert host == "10.0.0.9"

    def test_expired_token_raises_401(self):
        with patch(
            "ching_tech_os.api.files.nas_connection_manager.get_connection",
            return_value=None,
        ):
            with pytest.raises(HTTPException) as exc_info:
                _get_nas_smb_service("expired", _make_session())

        assert exc_info.value.status_code == 401
        assert exc_info.value.headers == {"X-NAS-Token-Expired": "true"}

    def test_fallback_to_session_password(self):
        with patch(
            "ching_tech_os.api.files.create_smb_service",
            return_value="svc-by-session",
        ) as mock_create:
            smb, host = _get_nas_smb_service(None, _make_session(password="secret"))

        assert smb == "svc-by-session"
        assert host == "10.0.0.1"
        mock_create.assert_called_once_with(
            username="tester",
            password="secret",
            host="10.0.0.1",
        )

    def test_no_token_and_no_password_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            _get_nas_smb_service(None, _make_session(password=""))
        assert exc_info.value.status_code == 401


class _FakeSMB:
    def __init__(self, data: bytes | None = None, error: Exception | None = None):
        self._data = data
        self._error = error

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def read_file(self, _share: str, _path: str) -> bytes:
        if self._error:
            raise self._error
        return self._data or b""


# ============================================================
# _read_nas_file() 測試
# ============================================================

class TestReadNasFile:
    """NAS 讀檔測試"""

    @pytest.mark.asyncio
    async def test_path_validation(self):
        with pytest.raises(HTTPException) as exc1:
            await _read_nas_file("", _make_session(), "tok")
        assert exc1.value.status_code == 400

        with pytest.raises(HTTPException) as exc2:
            await _read_nas_file("public", _make_session(), "tok")
        assert exc2.value.status_code == 400

    @pytest.mark.asyncio
    async def test_read_success(self):
        async def _run(fn):
            return fn()

        with patch(
            "ching_tech_os.api.files._get_nas_smb_service",
            return_value=(_FakeSMB(data=b"hello"), "host"),
        ), patch("ching_tech_os.api.files.run_in_smb_pool", side_effect=_run):
            content = await _read_nas_file("public/folder/a.txt", _make_session(), "tok")

        assert content == b"hello"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("error", "status_code"),
        [
            (SMBConnectionError(), 503),
            (SMBFileNotFoundError(), 404),
            (SMBPermissionError(), 403),
            (SMBError("boom"), 500),
        ],
    )
    async def test_read_error_mapping(self, error, status_code):
        async def _run(fn):
            return fn()

        with patch(
            "ching_tech_os.api.files._get_nas_smb_service",
            return_value=(_FakeSMB(error=error), "host"),
        ), patch("ching_tech_os.api.files.run_in_smb_pool", side_effect=_run):
            with pytest.raises(HTTPException) as exc_info:
                await _read_nas_file("public/folder/a.txt", _make_session(), "tok")

        assert exc_info.value.status_code == status_code


# ============================================================
# _read_local_file() / _read_file_content() 測試
# ============================================================

class TestReadLocalFile:
    """本地讀檔測試"""

    def test_not_exists_raises_404(self, tmp_path):
        with pytest.raises(HTTPException) as exc_info:
            _read_local_file(tmp_path / "missing.txt")
        assert exc_info.value.status_code == 404

    def test_directory_raises_400(self, tmp_path):
        folder = tmp_path / "folder"
        folder.mkdir()
        with pytest.raises(HTTPException) as exc_info:
            _read_local_file(folder)
        assert exc_info.value.status_code == 400

    def test_permission_error_raises_403(self, tmp_path):
        file_path = tmp_path / "a.txt"
        file_path.write_text("hello", encoding="utf-8")
        with patch.object(Path, "read_bytes", side_effect=PermissionError):
            with pytest.raises(HTTPException) as exc_info:
                _read_local_file(file_path)
        assert exc_info.value.status_code == 403

    def test_unknown_error_raises_500(self, tmp_path):
        file_path = tmp_path / "a.txt"
        file_path.write_text("hello", encoding="utf-8")
        with patch.object(Path, "read_bytes", side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as exc_info:
                _read_local_file(file_path)
        assert exc_info.value.status_code == 500


class TestReadFileContent:
    """統一讀檔入口測試"""

    @pytest.mark.asyncio
    async def test_empty_path_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            await _read_file_content("local", "", _make_session())
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_nas_zone(self):
        with patch(
            "ching_tech_os.api.files._read_nas_file",
            AsyncMock(return_value=b"nas-content"),
        ):
            content, filename, mime = await _read_file_content(
                "nas",
                "public/path/file.txt",
                _make_session(),
                "token-1",
            )
        assert content == b"nas-content"
        assert filename == "file.txt"
        assert mime == "text/plain"

    @pytest.mark.asyncio
    async def test_local_zone(self):
        with patch(
            "ching_tech_os.api.files._get_file_path",
            return_value=Path("/tmp/a.pdf"),
        ), patch(
            "ching_tech_os.api.files._read_local_file",
            return_value=b"pdf-content",
        ):
            content, filename, mime = await _read_file_content(
                "local",
                "docs/a.pdf",
                _make_session(),
            )
        assert content == b"pdf-content"
        assert filename == "a.pdf"
        assert mime == "application/pdf"


# ============================================================
# endpoint 函式測試
# ============================================================

class TestFilesEndpoints:
    """read/download endpoint 函式測試"""

    @pytest.mark.asyncio
    async def test_download_file_uses_header_token(self):
        session = _make_session()
        with patch(
            "ching_tech_os.api.files._read_file_content",
            AsyncMock(return_value=(b"x", "中文 檔案.txt", "text/plain")),
        ) as mock_read:
            resp = await download_file(
                zone="local",
                path="docs/a.txt",
                x_nas_token="header-token",
                nas_token="query-token",
                session=session,
            )

        mock_read.assert_awaited_once_with("local", "docs/a.txt", session, "header-token")
        assert resp.media_type == "text/plain"
        assert "Content-Disposition" in resp.headers
        assert "attachment; filename*=UTF-8''" in resp.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_read_file_uses_query_token_when_no_header(self):
        session = _make_session()
        with patch(
            "ching_tech_os.api.files._read_file_content",
            AsyncMock(return_value=(b"img", "a.png", "image/png")),
        ) as mock_read:
            resp = await read_file(
                zone="nas",
                path="public/a.png",
                x_nas_token=None,
                nas_token="query-token",
                session=session,
            )

        mock_read.assert_awaited_once_with("nas", "public/a.png", session, "query-token")
        assert resp.media_type == "image/png"
        assert resp.body == b"img"
