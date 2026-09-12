"""網頁瀏覽相關 MCP 工具

包含：browse_webpage（使用 Playwright 擷取 JS 渲染後的網頁內容）
"""

import ipaddress
import socket
from urllib.parse import urlparse

from .server import mcp, logger


# 主機名稱只在內網有意義的後綴（mDNS／企業內網慣例）
_INTERNAL_HOST_SUFFIXES = (".local", ".internal", ".lan", ".intranet", ".home.arpa")


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """這個位址是不是公開網際網路位址。

    `ipaddress` 的 `is_global` 已經涵蓋 loopback／private（10/8、172.16/12、
    192.168/16）／link-local（169.254/16、fe80::/10）／unique-local（fc00::/7）
    ／保留位址，但 CGNAT（100.64/10）在部分 Python 版本仍被算成 global，
    所以額外擋一次；IPv4-mapped IPv6（::ffff:10.0.0.1）也拆出來用 v4 規則判。
    """
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return False

    if isinstance(ip, ipaddress.IPv4Address):
        # CGNAT：ISP 的共享位址段，不是公開可定址的目標
        if ip in ipaddress.ip_network("100.64.0.0/10"):
            return False
    else:
        if ip.is_site_local:
            return False

    return True


def check_public_http_target(url: str) -> str | None:
    """SSRF 防護：只放行解析結果全部是公開位址的 HTTPS 目標（issue #210 review）。

    `browse_webpage` 登記在 `permissions.TOOLS_INTENTIONALLY_OPEN`（未綁定者也能
    呼叫），理由是「只讀公開網頁」。原本只檢查 scheme 是 https 而且 netloc 非空，
    未綁定者因此可以叫 bot 去打 `https://192.168.11.11/...`、`https://localhost:8088/...`
    這類內網位址，把內網頁面內容讀回對話裡——那就不是只讀公開網頁了。

    規則（任何一條不過就拒絕）：
    - 主機名稱沒有點（`https://intranet/`）或是內網後綴（`.local`／`.internal`
      ／`.lan`／`.intranet`／`.home.arpa`）
    - 主機是 IP 字面值且不是公開位址
    - DNS 解析出來的位址**任何一個**不是公開位址（擋 DNS rebinding 的一半：
      同一個名字同時回公開與內網位址時一律拒絕）

    Returns:
        None 表示放行；否則回傳要顯示給使用者的錯誤字串（不丟例外）
    """
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return "❌ 無效的 URL"

    host = host.rstrip(".")
    lowered = host.lower()

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        if not _is_public_ip(literal):
            return f"❌ 不允許存取內部網路位址：{host}"
        return None

    if "." not in lowered or lowered.endswith(_INTERNAL_HOST_SUFFIXES):
        return f"❌ 不允許存取內部主機名稱：{host}"

    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return f"❌ 無法解析主機名稱：{host}"

    addresses = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue

    if not addresses:
        return f"❌ 無法解析主機名稱：{host}"

    for address in addresses:
        if not _is_public_ip(address):
            return f"❌ 不允許存取內部網路位址：{host} → {address}"

    return None


@mcp.tool()
async def browse_webpage(
    url: str,
    max_length: int = 8000,
    timeout: int = 30000,
    ctos_user_id: int | None = None,
) -> str:
    """用瀏覽器開啟網頁並擷取完整渲染後的內容。

    適合 JavaScript 渲染的 SPA 網站（如 React、Next.js）。
    一般靜態網頁請優先使用 WebFetch。

    Args:
        url: 目標網頁 URL（必須 HTTPS）
        max_length: 回傳內容最大字數，預設 8000
        timeout: 頁面載入超時毫秒數，預設 30000
        ctos_user_id: CTOS 用戶 ID
    """
    # URL 驗證：僅允許 HTTPS
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return f"❌ 僅支援 HTTPS URL，收到的 scheme 為：{parsed.scheme or '（空）'}"

    if not parsed.netloc:
        return "❌ 無效的 URL"

    # SSRF 防護：這支工具對未綁定者開放，不能拿來讀內網頁面
    target_error = check_public_http_target(url)
    if target_error:
        return target_error

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "❌ playwright 套件未安裝，無法使用瀏覽器功能"

    pw = None
    browser = None
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page(viewport={"width": 1280, "height": 720})

        # 頁面導航：先嘗試 networkidle，失敗則 fallback
        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout)
        except Exception:
            # fallback：domcontentloaded + 額外等待
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                await page.wait_for_timeout(3000)
            except Exception as e:
                return f"❌ 頁面載入超時：{e}"

        # 取得頁面標題
        title = await page.title() or "（無標題）"

        # 取得 accessibility snapshot（aria_snapshot 回傳 YAML 格式）
        text = await page.locator("body").aria_snapshot()
        if not text or not text.strip():
            return "❌ 頁面無可讀內容"

        # 截斷處理
        truncated = False
        if len(text) > max_length:
            text = text[:max_length]
            truncated = True

        # 組合結果
        result = f"📄 {title}\n\n{text}"
        if truncated:
            result += f"\n\n⚠️ 內容已截斷（超過 {max_length} 字上限）"

        return result

    except Exception as e:
        error_msg = str(e)
        if "Executable doesn't exist" in error_msg or "Failed to launch" in error_msg:
            return "❌ 瀏覽器啟動失敗，請確認已安裝 Chromium（playwright install chromium）"
        logger.error("browse_webpage 錯誤: %s", e)
        return f"❌ 擷取網頁失敗：{e}"

    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if pw:
            try:
                await pw.stop()
            except Exception:
                pass
