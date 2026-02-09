## 1. 後端：MCP Server 按需載入

- [x] 1.1 修改 `_build_mcp_servers()`：新增 `required_servers: set[str] | None` 參數，只回傳名稱在集合中的 server
- [x] 1.2 確保 `ching-tech-os` 永遠被包含在 required_servers 中（保底邏輯）
- [x] 1.3 修改 `call_claude()`：新增 `required_mcp_servers` 可選參數，傳給 `_build_mcp_servers()`
- [x] 1.4 在 `bot/agents.py` 新增 `get_mcp_servers_for_user()` 函式，呼叫 SkillManager 的 `get_required_mcp_servers()`，含 fallback
- [x] 1.5 修改 Telegram handler：取得 required_mcp_servers 並傳給 `call_claude()`
- [x] 1.6 修改 Line bot handler：同上
- [x] 1.7 重啟服務，驗證 MCP server 按需載入正常（發 Telegram 測試，檢查日誌）

## 2. 前端：AI Log Tools 顯示優化

- [x] 2.1 修改 `renderToolsBadges()`：預設只顯示 used_tools
- [x] 2.2 新增 `+N` 展開按鈕：點擊展開顯示完整 allowed_tools，再點收合
- [x] 2.3 調整 CSS 樣式：展開按鈕樣式、展開後未使用工具的淡色樣式
- [x] 2.4 確保手機版卡片的 tools 顯示也一致
- [x] 2.5 驗證前端顯示效果（在 AI Log 應用中查看）
