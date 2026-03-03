# agent-switch-command Specification

## Purpose
提供管理員在 Line/Telegram Bot 對話中切換 AI Agent 的能力，支援個人與群組對話層級的偏好持久化。

## Requirements

### Requirement: /agent 斜線指令
系統 SHALL 提供 `/agent` 斜線指令，讓管理員在個人或群組對話中切換當前使用的 AI Agent。

#### Scenario: 無參數顯示目前狀態與清單
- **WHEN** 管理員發送 `/agent`（無參數）
- **THEN** 系統 SHALL 回覆目前使用的 Agent 名稱和 display_name
- **AND** 若使用預設 Agent，標註「（預設）」
- **AND** 列出所有可切換的 Agent（`settings.user_selectable = true` 的 Agent）
- **AND** 每個 Agent 帶有序號，格式為 `{序號}. {name} — {display_name}`
- **AND** 序號從 1 開始，按 Agent name 字母排序

#### Scenario: 用名稱切換 Agent
- **WHEN** 管理員發送 `/agent <name>`
- **AND** `<name>` 對應一個存在且 `settings.user_selectable = true` 的 Agent
- **THEN** 系統 SHALL 將該對話的 Agent 偏好設為指定的 Agent
- **AND** 回覆「已切換到 {display_name}」

#### Scenario: 用編號切換 Agent
- **WHEN** 管理員發送 `/agent <number>`
- **AND** `<number>` 為正整數且對應清單中的序號
- **THEN** 系統 SHALL 將該對話的 Agent 偏好設為該序號對應的 Agent
- **AND** 回覆「已切換到 {display_name}」

#### Scenario: 編號超出範圍
- **WHEN** 管理員發送 `/agent <number>`
- **AND** `<number>` 為正整數但超出可切換清單的範圍
- **THEN** 系統 SHALL 回覆「編號 {number} 超出範圍，請用 /agent 查看可用清單」

#### Scenario: 切換不存在的 Agent
- **WHEN** 管理員發送 `/agent <name>`
- **AND** `<name>` 不是數字
- **AND** `<name>` 不對應任何存在的 Agent
- **THEN** 系統 SHALL 回覆「找不到 Agent: {name}，請用 /agent 查看可用清單」

#### Scenario: 切換不可選的 Agent
- **WHEN** 管理員發送 `/agent <name>`
- **AND** Agent 存在但 `settings.user_selectable` 不為 `true`
- **THEN** 系統 SHALL 回覆「Agent {name} 不可切換，請用 /agent 查看可用清單」

#### Scenario: 重置為預設 Agent
- **WHEN** 管理員發送 `/agent reset`
- **THEN** 系統 SHALL 清除該對話的 Agent 偏好（設為 NULL）
- **AND** 回覆「已恢復預設 Agent」

#### Scenario: 指令權限限制
- **WHEN** 非管理員用戶發送 `/agent`
- **THEN** 系統 SHALL 回覆「此指令僅限管理員使用」

#### Scenario: 未綁定用戶發送 /agent
- **WHEN** 未綁定帳號的用戶發送 `/agent`
- **THEN** 系統 SHALL 回覆「請先綁定帳號」

### Requirement: Agent 偏好持久化
系統 SHALL 持久化儲存每個對話的 Agent 偏好，直到手動重置。

#### Scenario: 個人對話偏好儲存
- **WHEN** 管理員在個人對話中執行 `/agent <name>`
- **THEN** 系統 SHALL 將偏好存在 `bot_users.active_agent_id`
- **AND** 僅影響該用戶的個人對話

#### Scenario: 群組對話偏好儲存
- **WHEN** 管理員在群組對話中執行 `/agent <name>`
- **THEN** 系統 SHALL 將偏好存在 `bot_groups.active_agent_id`
- **AND** 僅影響該特定群組的對話
- **AND** 其他群組和個人對話不受影響

#### Scenario: 偏好跨 session 持續
- **WHEN** 對話已設定 Agent 偏好
- **AND** 過了一段時間後再發送訊息
- **THEN** 系統 SHALL 繼續使用已設定的 Agent

#### Scenario: Agent 被刪除時自動恢復預設
- **WHEN** 對話偏好的 Agent 從資料庫被刪除
- **THEN** `active_agent_id` SHALL 自動設為 NULL（`ON DELETE SET NULL`）
- **AND** 對話恢復使用預設 Agent

### Requirement: Agent 路由偏好覆蓋
系統 SHALL 在 Agent 路由時優先使用對話的偏好設定。

#### Scenario: 群組有偏好時使用偏好 Agent
- **WHEN** 群組 `bot_groups.active_agent_id` 不為 NULL
- **AND** 群組收到已綁定用戶的訊息
- **THEN** 系統 SHALL 使用偏好的 Agent 處理訊息
- **AND** 不使用預設的 `linebot-group` Agent

#### Scenario: 群組無偏好時使用預設 Agent
- **WHEN** 群組 `bot_groups.active_agent_id` 為 NULL
- **THEN** 系統 SHALL 使用預設的 `linebot-group` Agent

#### Scenario: 個人對話有偏好時使用偏好 Agent
- **WHEN** 用戶 `bot_users.active_agent_id` 不為 NULL
- **AND** 在個人對話中發送訊息
- **THEN** 系統 SHALL 使用偏好的 Agent 處理訊息
- **AND** 不使用預設的 `linebot-personal` Agent

#### Scenario: 個人對話無偏好時使用預設 Agent
- **WHEN** 用戶 `bot_users.active_agent_id` 為 NULL
- **THEN** 系統 SHALL 使用預設的 `linebot-personal` Agent

#### Scenario: 未綁定用戶不受偏好影響
- **WHEN** 未綁定用戶發送訊息
- **AND** 系統執行受限模式處理（`identity_router`）
- **THEN** Agent 偏好 SHALL 不影響受限模式的 Agent 選擇
- **AND** 受限模式始終使用 `bot-restricted` Agent

### Requirement: Agent 可選標記
系統 SHALL 使用 `ai_agents.settings` JSONB 中的 `user_selectable` 旗標標記可供切換的 Agent。

#### Scenario: 預設 Agent 不可選
- **WHEN** 系統初始化預設 Agent（`linebot-personal`、`linebot-group`、`bot-restricted`、`bot-debug`）
- **THEN** 這些 Agent 的 `settings.user_selectable` SHALL 不設定或為 `false`

#### Scenario: 管理員標記 Agent 為可選
- **WHEN** 管理員透過 AI 管理介面修改 Agent 的 settings
- **AND** 設定 `user_selectable: true`
- **THEN** 該 Agent SHALL 出現在 `/agent` 可切換清單中

#### Scenario: 查詢可選 Agent 清單
- **WHEN** 系統需要列出可切換的 Agent
- **THEN** 系統 SHALL 查詢 `ai_agents` 表中 `is_active = true` 且 `settings->>'user_selectable' = 'true'` 的 Agent
