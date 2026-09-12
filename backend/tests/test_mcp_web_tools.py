"""測試 mcp/web_tools.py 的 browse_webpage"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ching_tech_os.services.mcp.web_tools import browse_webpage


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch: pytest.MonkeyPatch):
    """預設把主機名稱解析成公開位址，測試不吃真實 DNS。

    SSRF 防護（issue #210 review）會真的呼叫 `socket.getaddrinfo`；
    沒有這個 fixture，這份檔案在離線環境會整批紅。需要驗擋下來的情境時，
    個別測試再 monkeypatch 一次（後設的贏）。
    """
    import socket as _socket

    from ching_tech_os.services.mcp import web_tools

    def _fake_getaddrinfo(host, port, **_kwargs):
        return [
            (_socket.AF_INET, _socket.SOCK_STREAM, _socket.IPPROTO_TCP, "", ("93.184.216.34", port)),
        ]

    monkeypatch.setattr(web_tools.socket, "getaddrinfo", _fake_getaddrinfo)


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


# ============================================================
# SSRF 防護（issue #210 review）
# ============================================================

# `browse_webpage` 登記在 TOOLS_INTENTIONALLY_OPEN，理由是「只讀公開網頁」。
# 只檢查 scheme 是 https 的話這個理由不成立：未綁定者可以叫 bot 去讀內網頁面。


@pytest.mark.parametrize(
    "url, resolved",
    [
        ("https://a.example.com/x", "127.0.0.1"),          # loopback
        ("https://b.example.com/x", "10.1.2.3"),           # private 10/8
        ("https://c.example.com/x", "172.16.0.5"),         # private 172.16/12
        ("https://d.example.com/x", "192.168.11.11"),      # private 192.168/16
        ("https://e.example.com/x", "169.254.169.254"),    # link-local（雲端 metadata）
        ("https://f.example.com/x", "100.64.0.1"),         # CGNAT 100.64/10
        ("https://g.example.com/x", "::1"),                # IPv6 loopback
        ("https://h.example.com/x", "fd00::1"),            # IPv6 unique-local
        ("https://i.example.com/x", "::ffff:192.168.0.1"),  # IPv4-mapped IPv6
    ],
)
def test_check_public_http_target_blocks_resolved_private_addresses(
    monkeypatch: pytest.MonkeyPatch, url: str, resolved: str
) -> None:
    """DNS 解析到內部位址一律拒絕（每個網段一條）。"""
    import socket as _socket

    from ching_tech_os.services.mcp import web_tools

    def _fake_getaddrinfo(host, port, **_kwargs):
        family = _socket.AF_INET6 if ":" in resolved else _socket.AF_INET
        return [(family, _socket.SOCK_STREAM, _socket.IPPROTO_TCP, "", (resolved, port))]

    monkeypatch.setattr(web_tools.socket, "getaddrinfo", _fake_getaddrinfo)

    result = web_tools.check_public_http_target(url)
    assert result is not None
    assert result.startswith("❌")
    assert "內部網路位址" in result


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/x",
        "https://10.1.2.3/x",
        "https://192.168.11.11/x",
        "https://169.254.169.254/x",
        "https://100.64.0.1/x",
        "https://[::1]/x",
        "https://[fd00::1]/x",
    ],
)
def test_check_public_http_target_blocks_ip_literals(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    """IP 字面值不查 DNS，直接判斷（順便確認真的沒去解析）。"""
    from ching_tech_os.services.mcp import web_tools

    def _explode(*_a, **_k):
        raise AssertionError("IP 字面值不該去查 DNS")

    monkeypatch.setattr(web_tools.socket, "getaddrinfo", _explode)

    result = web_tools.check_public_http_target(url)
    assert result is not None
    assert "內部網路位址" in result


@pytest.mark.parametrize(
    "url",
    [
        "https://intranet/x",
        "https://nas.local/x",
        "https://wiki.internal/x",
        "https://printer.lan/x",
    ],
)
def test_check_public_http_target_blocks_internal_hostnames(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    """沒有點的主機名稱與內網後綴，連查都不用查。"""
    from ching_tech_os.services.mcp import web_tools

    def _explode(*_a, **_k):
        raise AssertionError("內網主機名稱不該去查 DNS")

    monkeypatch.setattr(web_tools.socket, "getaddrinfo", _explode)

    result = web_tools.check_public_http_target(url)
    assert result is not None
    assert "內部主機名稱" in result


def test_check_public_http_target_allows_public_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正向對照：解析到公開位址就放行。"""
    import socket as _socket

    from ching_tech_os.services.mcp import web_tools

    def _fake_getaddrinfo(host, port, **_kwargs):
        return [
            (_socket.AF_INET, _socket.SOCK_STREAM, _socket.IPPROTO_TCP, "", ("93.184.216.34", port)),
        ]

    monkeypatch.setattr(web_tools.socket, "getaddrinfo", _fake_getaddrinfo)

    assert web_tools.check_public_http_target("https://example.com/x") is None


def test_check_public_http_target_rejects_mixed_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一個名字同時回公開與內網位址（DNS rebinding 的常見形狀）一律拒絕。"""
    import socket as _socket

    from ching_tech_os.services.mcp import web_tools

    def _fake_getaddrinfo(host, port, **_kwargs):
        return [
            (_socket.AF_INET, _socket.SOCK_STREAM, _socket.IPPROTO_TCP, "", ("93.184.216.34", port)),
            (_socket.AF_INET, _socket.SOCK_STREAM, _socket.IPPROTO_TCP, "", ("192.168.0.9", port)),
        ]

    monkeypatch.setattr(web_tools.socket, "getaddrinfo", _fake_getaddrinfo)

    result = web_tools.check_public_http_target("https://example.com/x")
    assert result is not None
    assert "內部網路位址" in result


def test_check_public_http_target_reports_unresolvable_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """解析失敗回錯誤字串，不丟例外。"""
    import socket as _socket

    from ching_tech_os.services.mcp import web_tools

    def _fail(*_a, **_k):
        raise _socket.gaierror("nope")

    monkeypatch.setattr(web_tools.socket, "getaddrinfo", _fail)

    result = web_tools.check_public_http_target("https://example.com/x")
    assert result is not None
    assert "無法解析主機名稱" in result


@pytest.mark.asyncio
async def test_browse_webpage_refuses_internal_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """工具本體要走這道檢查，而且在啟動瀏覽器之前就擋下來。"""
    from ching_tech_os.services.mcp import web_tools

    def _explode(*_a, **_k):
        raise AssertionError("內網位址不該啟動瀏覽器")

    monkeypatch.setattr(web_tools, "async_playwright", _explode, raising=False)

    result = await web_tools.browse_webpage("https://192.168.11.11/admin")
    assert result.startswith("❌")
    assert "內部網路位址" in result
