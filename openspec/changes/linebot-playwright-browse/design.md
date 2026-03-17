## Context

LineBot 的 AI agent 透過 Claude CLI 內建 WebFetch 工具擷取網頁，但 SPA 網站（Next.js、React 等）只回傳空殼 HTML。現有 MCP 工具中 `media_tools.py` 提供 `download_web_image` / `download_web_file`，但這些是下載檔案用途，不做內容解析。

MCP 工具架構：`services/mcp/` 下各模組用 `@mcp.tool()` 裝飾器註冊，`__init__.py` 負責載入，工具自動暴露給 claude-code-acp。Bot agent prompt 在 `bot/agents.py` 中定義，指引 AI 選用哪些工具。

## Goals / Non-Goals

**Goals:**
- 提供 `browse_webpage` MCP 工具，能擷取 JS 渲染後的網頁內容
- 回傳 accessibility snapshot 格式，保留語意結構
- 支援 `max_length` 參數控制回傳內容長度
- 整合到現有 MCP 工具體系，所有 bot 用戶皆可使用

**Non-Goals:**
- 不支援頁面互動（點擊、表單填寫、多步驟導航）
- 不做 WebFetch 的自動 fallback — AI 自行判斷何時使用
- 不常駐瀏覽器 — 每次呼叫新開新關
- 不支援截圖或 PDF 輸出
- 不處理需要登入的網頁

## Decisions

### 1. 使用 Playwright Python async API 直接操作 Chromium

**選擇**：在 MCP 工具內直接呼叫 `playwright.async_api`

**替代方案**：
- CDP 直連 snap chromium — 底層操作複雜，需自建 accessibility tree 解析（~300 行 vs ~100 行）
- 掛載 Playwright MCP Server — 會暴露全部工具（click/fill/type），權限控制困難

**理由**：`playwright` 已在 pyproject.toml 依賴中，async API 與現有 asyncio MCP 工具一致，accessibility snapshot 一行就能取得。

### 2. Accessibility snapshot 作為回傳格式

**選擇**：`page.accessibility.snapshot()` → 遞迴轉換為可讀文字

**轉換規則**：
- `heading` → `## 標題`（依 level）
- `link` → `[文字](url)`
- `list` / `listitem` → `- 項目`
- 其餘節點 → 取 `name` 純文字

**替代方案**：
- 純 `innerText` — 丟失結構資訊
- HTML to Markdown — 需額外轉換器，且 SPA 的 DOM 結構常有大量無意義 wrapper

**理由**：Accessibility snapshot 原生就是語意化的樹狀結構，轉換簡單且資訊密度高，與 Playwright MCP 的 `browser_snapshot` 體驗一致。

### 3. 頁面等待策略：networkidle + fallback

**選擇**：先用 `wait_until="networkidle"`，若超時則 fallback 到 `"domcontentloaded"` 加額外等待 3 秒

**理由**：`networkidle` 對多數 SPA 有效（等到沒有新的 network request），但部分網站有持續性 polling 導致永遠不 idle。Fallback 策略確保不會卡死。

### 4. 瀏覽器啟動參數

```python
browser = await p.chromium.launch(
    headless=True,
    args=["--no-sandbox", "--disable-dev-shm-usage"]
)
```

- `--no-sandbox`：因部署環境（Ubuntu 24.04）AppArmor 限制 unprivileged user namespaces
- `--disable-dev-shm-usage`：避免 Docker 環境 /dev/shm 不足

### 5. 無條件載入，不綁定模組權限

**選擇**：在 `__init__.py` 中與 `voice_tools` 同樣方式無條件載入

**理由**：所有 bot 用戶皆可使用，不需要 app_permissions 控管。MCP server 是獨立進程，不依賴特定模組。

## Risks / Trade-offs

**[Chromium 未安裝]** → 工具內 try/except 捕捉 `playwright._impl._errors.Error`，回傳清楚的錯誤訊息而非 crash。部署文件記錄 `playwright install chromium` 步驟。

**[記憶體消耗]** → 每次開關瀏覽器約消耗 100-200MB，但因為是單次使用立即釋放，不會累積。同時併發呼叫的情況下可能短暫佔用較多記憶體，但 MCP 工具本身是序列執行的，風險低。

**[惡意 URL]** → 限制只允許 HTTPS URL，設定 timeout 上限防止卡住。不支援 `file://`、`javascript:` 等 scheme。

**[內容過大]** → `max_length` 參數截斷，預設 8,000 字。截斷時附加提示告知使用者內容已被截斷。

**[AppArmor 限制]** → 已知需要 `sysctl kernel.apparmor_restrict_unprivileged_userns=0` 或使用 `--no-sandbox`。選擇 `--no-sandbox` 作為預設，因為 MCP server 執行環境是受控的。
