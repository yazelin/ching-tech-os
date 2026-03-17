"""網頁瀏覽相關 MCP 工具

包含：browse_webpage（使用 Playwright 擷取 JS 渲染後的網頁內容）
"""

from urllib.parse import urlparse

from .server import mcp, logger


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
