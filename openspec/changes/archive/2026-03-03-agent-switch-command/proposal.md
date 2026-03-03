## Why

目前 Bot 的 Agent 選擇完全由 `is_group` 決定（群組用 `linebot-group`、個人用 `linebot-personal`），無法在對話中切換使用不同的 Agent。這在實務上有兩個痛點：

1. **客戶試用**：為杰膚美等客戶設計的衛教 Agent，在正式部署前無法讓客戶在擎添的群組中體驗實際效果
2. **Prompt 調校**：開發者需要反覆測試不同 Agent 的 prompt 和工具組合，目前只能透過 AI 管理介面修改後再重新發訊息，無法快速切換比較

新增 `/agent` 斜線指令，讓已綁定的用戶可以在個人或群組對話中切換當前使用的 Agent，不需要修改任何設定或重新部署。

## What Changes

- 新增 `/agent` 斜線指令，支援列出可用 Agent 和切換
  - `/agent` — 顯示當前 Agent 和可切換的清單
  - `/agent <name>` — 切換到指定 Agent
  - `/agent reset` — 恢復為預設 Agent
- `bot_users` 表新增 `active_agent_id` 欄位，記錄用戶的 Agent 偏好
- `bot_groups` 表新增 `active_agent_id` 欄位，記錄群組的 Agent 偏好
- 修改 Agent 路由邏輯，優先使用用戶/群組的偏好 Agent
- `ai_agents` 表的 `settings` JSONB 新增 `user_selectable` 旗標，標記可供切換的 Agent

## Capabilities

### New Capabilities
- `agent-switch-command`: `/agent` 斜線指令的註冊、解析、執行邏輯，以及 Agent 偏好的持久化和路由覆蓋機制

### Modified Capabilities
- `bot-slash-commands`: 新增 `/agent` 指令到指令清單與 `/help` 輸出
- `line-bot`: Agent 路由邏輯需支援偏好覆蓋（`get_linebot_agent()` 修改）

## Impact

- **資料庫**：需新增 Alembic migration，為 `bot_users` 和 `bot_groups` 加欄位，並為現有 Agent 設定 `user_selectable` 旗標
- **後端**：
  - `services/bot/commands.py` — 新增指令註冊
  - `services/bot/command_handlers.py` — 新增 `/agent` handler
  - `services/linebot_agents.py` — `get_linebot_agent()` 加入偏好覆蓋邏輯
  - `services/linebot_ai.py` — 傳遞 bot_user_id/group_id 到 Agent 選擇
  - `services/bot_telegram/handler.py` — 同步修改 Telegram 的 Agent 路由
  - `services/ai_manager.py` — 新增查詢可選 Agent 清單的方法
- **前端**：無影響（指令透過聊天介面操作）
- **API**：無新增 REST API（透過 Bot 指令互動）
