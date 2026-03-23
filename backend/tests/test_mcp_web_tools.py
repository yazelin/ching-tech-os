"""測試 mcp/web_tools.py 的 browse_webpage"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ching_tech_os.services.mcp.web_tools import browse_webpage


def _make_pw_mock(mock_browser=None, launch_error=None):
    """建立 playwright mock 鏈"""
    if launch_error:
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(side_effect=launch_error)
        mock_pw_instance.stop = AsyncMock()
    else:
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.stop = AsyncMock()

    mock_pw_ctx = AsyncMock()
    mock_pw_ctx.start = AsyncMock(return_value=mock_pw_instance)
    return mock_pw_ctx


def _make_page_mock(title="測試頁面", content="頁面內容", goto_side_effect=None):
    """建立 page mock"""
    mock_page = AsyncMock()
    if goto_side_effect:
        mock_page.goto = goto_side_effect
    else:
        mock_page.goto = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.title = AsyncMock(return_value=title)
    mock_locator = AsyncMock()
    mock_locator.aria_snapshot = AsyncMock(return_value=content)
    mock_page.locator = MagicMock(return_value=mock_locator)

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser.close = AsyncMock()
    return mock_browser, mock_page


PW_PATCH = "playwright.async_api.async_playwright"


class TestBrowseWebpage:
    @pytest.mark.asyncio
    async def test_non_https_url(self):
        """非 HTTPS URL 回傳錯誤"""
        result = await browse_webpage(url="http://example.com")
        assert "僅支援 HTTPS" in result

    @pytest.mark.asyncio
    async def test_empty_scheme(self):
        """無 scheme 的 URL"""
        result = await browse_webpage(url="not-a-url")
        assert "僅支援 HTTPS" in result or "無效的 URL" in result

    @pytest.mark.asyncio
    async def test_no_netloc(self):
        """無 netloc"""
        result = await browse_webpage(url="https://")
        assert "無效的 URL" in result

    @pytest.mark.asyncio
    async def test_browser_launch_failure(self):
        """瀏覽器啟動失敗"""
        mock_pw = _make_pw_mock(
            launch_error=Exception("Executable doesn't exist at /usr/bin/chromium")
        )
        with patch(PW_PATCH, return_value=mock_pw):
            result = await browse_webpage(url="https://example.com")
            assert "瀏覽器啟動失敗" in result

    @pytest.mark.asyncio
    async def test_successful_browse(self):
        """正常瀏覽成功"""
        mock_browser, _ = _make_page_mock(title="測試頁面", content="頁面內容文字")
        mock_pw = _make_pw_mock(mock_browser=mock_browser)
        with patch(PW_PATCH, return_value=mock_pw):
            result = await browse_webpage(url="https://example.com")
            assert "測試頁面" in result
            assert "頁面內容文字" in result

    @pytest.mark.asyncio
    async def test_content_truncated(self):
        """內容超過 max_length 被截斷"""
        mock_browser, _ = _make_page_mock(title="長頁面", content="A" * 500)
        mock_pw = _make_pw_mock(mock_browser=mock_browser)
        with patch(PW_PATCH, return_value=mock_pw):
            result = await browse_webpage(url="https://example.com", max_length=100)
            assert "截斷" in result

    @pytest.mark.asyncio
    async def test_networkidle_fallback(self):
        """networkidle 失敗但 domcontentloaded 成功"""
        call_count = 0

        async def _goto(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("wait_until") == "networkidle":
                raise Exception("timeout")

        mock_browser, mock_page = _make_page_mock(
            title="Fallback 頁面", content="fallback 內容"
        )
        mock_page.goto = _goto
        mock_pw = _make_pw_mock(mock_browser=mock_browser)
        with patch(PW_PATCH, return_value=mock_pw):
            result = await browse_webpage(url="https://example.com")
            assert "Fallback 頁面" in result
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_complete_timeout(self):
        """頁面載入完全超時"""

        async def _goto(url, **kwargs):
            raise Exception("page load timeout")

        mock_browser, mock_page = _make_page_mock()
        mock_page.goto = _goto
        mock_pw = _make_pw_mock(mock_browser=mock_browser)
        with patch(PW_PATCH, return_value=mock_pw):
            result = await browse_webpage(url="https://example.com")
            assert "超時" in result

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """頁面無可讀內容"""
        mock_browser, _ = _make_page_mock(title="空頁面", content="")
        mock_pw = _make_pw_mock(mock_browser=mock_browser)
        with patch(PW_PATCH, return_value=mock_pw):
            result = await browse_webpage(url="https://example.com")
            assert "無可讀內容" in result

    @pytest.mark.asyncio
    async def test_generic_error(self):
        """其他異常"""
        mock_pw = _make_pw_mock(launch_error=Exception("some random error"))
        with patch(PW_PATCH, return_value=mock_pw):
            result = await browse_webpage(url="https://example.com")
            assert "擷取網頁失敗" in result
