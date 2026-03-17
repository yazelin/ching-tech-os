## ADDED Requirements

### Requirement: web_tools 模組載入

MCP server SHALL 在 `__init__.py` 中無條件載入 `web_tools` 模組，與 `voice_tools` 相同模式。載入失敗時 SHALL 記錄 debug log 但不影響其他工具。

#### Scenario: 正常載入

- **WHEN** MCP server 啟動
- **THEN** `web_tools` 模組 MUST 被載入，`browse_webpage` 工具可用

#### Scenario: 載入失敗（如 playwright 未安裝）

- **WHEN** MCP server 啟動且 `web_tools` import 失敗
- **THEN** 系統記錄 debug log，其他 MCP 工具不受影響

### Requirement: Agent prompt 包含 browse_webpage 使用指引

Bot agent 的 `BASE_TOOLS_PROMPT` SHALL 包含 `browse_webpage` 工具說明，指引 AI：
- 一般網頁優先使用 WebFetch
- 當 WebFetch 回傳空白或 SPA 空殼時，改用 `browse_webpage`
- 用戶明確要求「用瀏覽器開」時直接使用

#### Scenario: AI 選擇正確工具

- **WHEN** AI 收到包含 SPA 網站 URL 的訊息且 WebFetch 失敗
- **THEN** prompt 指引 MUST 足夠清楚讓 AI 選擇使用 `browse_webpage`
