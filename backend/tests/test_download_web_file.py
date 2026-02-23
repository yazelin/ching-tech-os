"""download_web_file MCP 工具單元測試。"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ching_tech_os.services.mcp import media_tools as _media_mod
from ching_tech_os.services.mcp.media_tools import (
    _ALLOWED_CONTENT_TYPES,
    _MAX_DOWNLOAD_SIZE,
    _extract_filename_from_url,
    download_web_file,
)


# ============================================================
# _extract_filename_from_url 測試
# ============================================================

class TestExtractFilenameFromUrl:
    """從 URL 提取檔案名稱。"""

    def test_simple_url(self):
        assert _extract_filename_from_url("https://example.com/docs/report.pdf") == "report.pdf"

    def test_url_with_query_params(self):
        assert _extract_filename_from_url("https://example.com/file.pdf?token=abc") == "file.pdf"

    def test_url_with_encoded_chinese(self):
        url = "https://example.com/%E4%B8%89%E8%8F%B1%E6%89%8B%E5%86%8A.pdf"
        assert _extract_filename_from_url(url) == "三菱手冊.pdf"

    def test_url_no_filename(self):
        assert _extract_filename_from_url("https://example.com/") == ""

    def test_url_with_fragment(self):
        # urlparse 會分離 fragment，所以 #page=5 不會出現在 path 裡
        result = _extract_filename_from_url("https://example.com/doc.pdf#page=5")
        assert result == "doc.pdf"


# ============================================================
# download_web_file 整合測試
# ============================================================

def _mock_permission(allowed=True):
    """回傳共用的 permission mock patches。"""
    tool_result = (allowed, "" if allowed else "權限不足")
    return (
        patch("ching_tech_os.services.mcp.media_tools.ensure_db_connection", new_callable=AsyncMock),
        patch("ching_tech_os.services.mcp.media_tools.check_mcp_tool_permission", new_callable=AsyncMock, return_value=tool_result),
    )


class MockStreamResponse:
    """模擬 httpx streaming response。"""

    def __init__(self, status_code=200, content_type="application/pdf", content=b"%PDF-1.4 test", headers=None):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        if headers:
            self.headers.update(headers)
        self._content = content

    async def aiter_bytes(self, chunk_size=65536):
        yield self._content

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockAsyncClient:
    """模擬 httpx.AsyncClient。"""

    def __init__(self, response: MockStreamResponse):
        self._response = response

    def stream(self, method, url, **kwargs):
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _setup_patches(tmp_path, mock_response, with_path_manager=True):
    """建立完整的 patch 列表。"""
    mock_client = MockAsyncClient(mock_response)

    # 建立 mock httpx 模組，只替換 media_tools 中的引用
    mock_httpx = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_client
    mock_httpx.Timeout = httpx.Timeout  # 保留真正的 Timeout 類別
    mock_httpx.TimeoutException = httpx.TimeoutException
    mock_httpx.RequestError = httpx.RequestError

    # mock settings：patch 底層欄位讓 linebot_local_path property 回傳 tmp_path
    # linebot_local_path = f"{ctos_mount_path}/{line_files_nas_path}"
    from ching_tech_os.config import settings as _settings
    patches = [
        *_mock_permission(),
        patch.object(_media_mod, "httpx", mock_httpx),
        patch.object(_settings, "ctos_mount_path", str(tmp_path)),
        patch.object(_settings, "line_files_nas_path", ""),
    ]

    if with_path_manager:
        mock_pm = MagicMock()
        mock_pm.to_storage.side_effect = lambda p: f"ctos://linebot/files/{os.path.basename(p)}"
        patches.append(
            patch("ching_tech_os.services.path_manager.path_manager", mock_pm),
        )

    return patches


@pytest.mark.asyncio
async def test_download_success(tmp_path):
    """正常下載 PDF 檔案。"""
    resp = MockStreamResponse(content_type="application/pdf", content=b"%PDF-1.4 test content")
    patches = _setup_patches(tmp_path, resp)

    ctx_managers = [p.__enter__() if hasattr(p, '__enter__') else p for p in patches]
    # 使用 contextmanager stack
    import contextlib
    async with contextlib.AsyncExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = await download_web_file(url="https://example.com/report.pdf", ctos_user_id=1)

    assert "✅ 已下載檔案" in result
    assert "report.pdf" in result
    assert "ctos://" in result


@pytest.mark.asyncio
async def test_download_with_custom_filename(tmp_path):
    """指定自訂檔案名稱。"""
    resp = MockStreamResponse(content_type="application/pdf", content=b"%PDF-1.4 test")
    patches = _setup_patches(tmp_path, resp)

    import contextlib
    async with contextlib.AsyncExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = await download_web_file(
            url="https://example.com/some-file",
            filename="自訂名稱.pdf",
            ctos_user_id=1,
        )

    assert "✅ 已下載檔案" in result
    assert "自訂名稱.pdf" in result


@pytest.mark.asyncio
async def test_download_unsupported_content_type(tmp_path):
    """不支援的 Content-Type。"""
    resp = MockStreamResponse(content_type="application/x-executable", content=b"\x7fELF")
    patches = _setup_patches(tmp_path, resp, with_path_manager=False)

    import contextlib
    async with contextlib.AsyncExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = await download_web_file(url="https://example.com/malware.exe", ctos_user_id=1)

    assert "不支援的檔案類型" in result


@pytest.mark.asyncio
async def test_download_http_error(tmp_path):
    """HTTP 404 錯誤。"""
    resp = MockStreamResponse(status_code=404)
    patches = _setup_patches(tmp_path, resp, with_path_manager=False)

    import contextlib
    async with contextlib.AsyncExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = await download_web_file(url="https://example.com/missing.pdf", ctos_user_id=1)

    assert "下載失敗" in result
    assert "404" in result


@pytest.mark.asyncio
async def test_download_permission_denied():
    """權限不足。"""
    p1, p2 = _mock_permission(allowed=False)
    with p1, p2:
        result = await download_web_file(url="https://example.com/report.pdf", ctos_user_id=1)

    assert "權限不足" in result


@pytest.mark.asyncio
async def test_download_file_too_large(tmp_path):
    """檔案過大中斷下載。"""
    large_content = b"x" * (_MAX_DOWNLOAD_SIZE + 1)
    resp = MockStreamResponse(content_type="application/pdf", content=large_content)
    patches = _setup_patches(tmp_path, resp, with_path_manager=False)

    import contextlib
    async with contextlib.AsyncExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = await download_web_file(url="https://example.com/huge.pdf", ctos_user_id=1)

    assert "檔案過大" in result


@pytest.mark.asyncio
async def test_download_content_disposition_filename(tmp_path):
    """從 Content-Disposition 取得檔案名稱。"""
    resp = MockStreamResponse(
        content_type="application/pdf",
        content=b"%PDF-1.4 test",
        headers={"content-disposition": 'attachment; filename="手冊.pdf"'},
    )
    patches = _setup_patches(tmp_path, resp)

    import contextlib
    async with contextlib.AsyncExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = await download_web_file(url="https://example.com/download?id=123", ctos_user_id=1)

    assert "手冊.pdf" in result


@pytest.mark.asyncio
async def test_download_docx(tmp_path):
    """下載 Word 文件。"""
    resp = MockStreamResponse(
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content=b"PK\x03\x04 docx content",
    )
    patches = _setup_patches(tmp_path, resp)

    import contextlib
    async with contextlib.AsyncExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = await download_web_file(url="https://example.com/spec.docx", ctos_user_id=1)

    assert "✅ 已下載檔案" in result
    assert "spec.docx" in result


@pytest.mark.asyncio
async def test_download_adds_extension_from_mime(tmp_path):
    """URL 無副檔名時，從 MIME type 推斷。"""
    resp = MockStreamResponse(
        content_type="application/pdf",
        content=b"%PDF-1.4 test",
    )
    patches = _setup_patches(tmp_path, resp)

    import contextlib
    async with contextlib.AsyncExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = await download_web_file(url="https://example.com/download", ctos_user_id=1)

    assert "✅ 已下載檔案" in result
    assert ".pdf" in result
