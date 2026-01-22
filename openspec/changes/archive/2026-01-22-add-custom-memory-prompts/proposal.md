# Change: 新增 Line Bot 自訂記憶 Prompt 功能

## Why
目前 Line Bot 的對話提示是統一的系統設定，無法針對特定群組或個人對話進行客製化。使用者希望能在對話中讓 AI 記住特定的偏好或規則（如「列出專案進度時，客戶新增的項目要特別標註 ⭐客戶新增」），這些記憶需要持久保存，並在後續對話中自動套用。

## What Changes
- 新增 `line_group_memories` 資料表，儲存群組專屬的自訂記憶 prompt
- 新增 `line_user_memories` 資料表，儲存個人對話專屬的自訂記憶 prompt
- 修改 `build_system_prompt()` 函式，在組合 prompt 時自動加入對應的記憶內容
- 新增 MCP 工具讓 AI 可以在對話中新增、修改、刪除記憶
- 新增 CTOS 前端 App 管理介面，讓使用者可以 CRUD 這些記憶

## Impact
- Affected specs: line-bot, ai-management, mcp-tools
- Affected code:
  - `backend/migrations/versions/` - 新增資料表 migration
  - `backend/src/ching_tech_os/services/linebot_ai.py` - 修改 build_system_prompt()
  - `backend/src/ching_tech_os/services/mcp_server.py` - 新增 MCP 工具
  - `backend/src/ching_tech_os/api/` - 新增 API 路由
  - `frontend/js/` - 新增管理 App
