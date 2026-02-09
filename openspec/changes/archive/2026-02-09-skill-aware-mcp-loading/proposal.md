## Why

目前每次 AI 呼叫都會啟動全部 4 個 MCP server（ching-tech-os、nanobanana、erpnext、printer），即使用戶只需要其中 1-2 個。這造成不必要的啟動開銷和資源浪費。SkillManager 已有 `get_required_mcp_servers()` 方法可依權限回傳所需的 server，但從未被使用。

同時，前端 AI logs 的 Tools 欄位會列出所有 allowed_tools（80+ 個），其中絕大多數未被使用，導致介面雜亂、資訊密度低，難以快速辨識 AI 實際使用了哪些工具。

## What Changes

### 後端：MCP Server 按需載入
- `call_claude()` 改為只啟動用戶權限所需的 MCP server（透過 SkillManager 的 `get_required_mcp_servers()`）
- `.mcp.json` 的複製邏輯改為只寫入需要的 server 設定
- 新增 `mcp_servers` 參數傳遞鏈（handler → call_claude）

### 前端：AI Log Tools 顯示優化
- Tools 欄位預設只顯示「實際使用的工具」（used_tools）
- allowed_tools 改為可展開的次要資訊
- 詳情面板新增 Allowed Tools 區塊，顯示完整白名單

## Capabilities

### New Capabilities

_無新 capability_

### Modified Capabilities

- `bot-platform`: AI 呼叫時 MCP server 由全部載入改為依用戶權限按需載入
- `ai-management`: 前端 AI logs 的 Tools 顯示邏輯改為預設只顯示 used tools

## Impact

- **後端程式碼**：`claude_agent.py`（MCP server 過濾）、`bot_telegram/handler.py`、`linebot_ai.py`（傳遞 app_permissions 或 mcp server 名稱）
- **前端程式碼**：`frontend/js/ai-log.js`（renderToolsBadges 邏輯）、`frontend/css/ai-log.css`（樣式調整）
- **效能影響**：減少每次 AI 呼叫啟動的 MCP server 數量（最佳情況從 4 個降至 1 個），降低啟動延遲和記憶體使用
- **風險**：MCP server 過濾邏輯錯誤可能導致工具不可用，需確保 fallback 機制健全
