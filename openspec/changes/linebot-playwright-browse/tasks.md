## 1. 建立 web_tools MCP 工具模組

- [x] 1.1 建立 `backend/src/ching_tech_os/services/mcp/web_tools.py`，實作 `browse_webpage` 工具：URL 驗證（僅 HTTPS）、Playwright Chromium headless 啟動、頁面導航（networkidle + fallback）、accessibility snapshot 擷取、snapshot tree 轉可讀文字、max_length 截斷、browser 生命週期管理（finally 確保關閉）、錯誤處理（超時/Chromium 不可用/空白頁面）
- [x] 1.2 在 `backend/src/ching_tech_os/services/mcp/__init__.py` 加入 `web_tools` 無條件載入（與 voice_tools 同模式），import 失敗時記錄 debug log

## 2. Agent Prompt 整合

- [x] 2.1 在 `backend/src/ching_tech_os/services/bot/agents.py` 的 `BASE_TOOLS_PROMPT` 加入 `browse_webpage` 工具說明，包含使用時機指引（WebFetch 失敗時 fallback、用戶明確要求時使用）

## 3. 驗證

- [x] 3.1 手動測試：透過 MCP CLI 呼叫 `browse_webpage` 擷取 SPA 網站（如 https://ai-go.app/），確認回傳 accessibility snapshot 格式且內容完整
- [x] 3.2 手動測試：驗證 HTTPS 限制、超時處理、max_length 截斷、Chromium 不可用時的錯誤訊息
- [ ] 3.3 透過 LineBot 對話測試：請 AI 瀏覽一個 SPA 網站，確認 AI 能正確選用 `browse_webpage` 並回傳內容
