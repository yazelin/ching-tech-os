## ADDED Requirements

### Requirement: 排程管理 MCP 工具
系統 SHALL 提供 MCP 工具讓 AI Agent 可以管理動態排程。

#### Scenario: manage_scheduled_task — 建立排程
- **WHEN** Agent 呼叫 `manage_scheduled_task` 並提供 `action: "create"` 及排程定義
- **THEN** SHALL 建立新的動態排程並同步註冊到 APScheduler
- **THEN** SHALL 回傳新建排程的摘要資訊（id、name、trigger、executor）

#### Scenario: manage_scheduled_task — 更新排程
- **WHEN** Agent 呼叫 `manage_scheduled_task` 並提供 `action: "update"`、`task_id` 及更新資料
- **THEN** SHALL 更新排程定義並同步更新 APScheduler job
- **THEN** SHALL 回傳更新後的排程摘要

#### Scenario: manage_scheduled_task — 刪除排程
- **WHEN** Agent 呼叫 `manage_scheduled_task` 並提供 `action: "delete"` 及 `task_id`
- **THEN** SHALL 刪除排程記錄並從 APScheduler 移除 job
- **THEN** SHALL 回傳刪除確認訊息

#### Scenario: manage_scheduled_task — 啟用排程
- **WHEN** Agent 呼叫 `manage_scheduled_task` 並提供 `action: "enable"` 及 `task_id`
- **THEN** SHALL 設定 `is_enabled = true` 並在 APScheduler 註冊 job

#### Scenario: manage_scheduled_task — 停用排程
- **WHEN** Agent 呼叫 `manage_scheduled_task` 並提供 `action: "disable"` 及 `task_id`
- **THEN** SHALL 設定 `is_enabled = false` 並從 APScheduler 移除 job

#### Scenario: manage_scheduled_task — 權限檢查
- **WHEN** Agent 呼叫 `manage_scheduled_task` 但 `ctos_user_id` 不是管理員
- **THEN** SHALL 回傳權限不足的錯誤訊息

### Requirement: 排程查詢 MCP 工具
系統 SHALL 提供 MCP 工具讓 AI Agent 查詢排程資訊。

#### Scenario: list_scheduled_tasks — 查詢所有排程
- **WHEN** Agent 呼叫 `list_scheduled_tasks`
- **THEN** SHALL 回傳所有動態排程的列表摘要
- **THEN** 每筆記錄 SHALL 包含 name、trigger 摘要、executor 類型、啟用狀態、最後執行結果

#### Scenario: list_scheduled_tasks — 篩選條件
- **WHEN** Agent 呼叫 `list_scheduled_tasks` 並提供 `is_enabled` 參數
- **THEN** SHALL 只回傳符合啟用狀態的排程

### Requirement: 排程管理 Skill 定義
系統 SHALL 提供 `task-scheduler` Skill，在 SKILL.md 中宣告排程管理的 MCP 工具和前端應用。

#### Scenario: Skill 結構
- **WHEN** `task-scheduler` Skill 載入
- **THEN** SHALL 在 SKILL.md 中宣告 `allowed-tools` 包含 `manage_scheduled_task` 和 `list_scheduled_tasks`
- **THEN** SHALL 透過 `contributes.app` 宣告桌面應用

#### Scenario: Skill 工具白名單
- **WHEN** Agent 被設定使用 `task-scheduler` Skill
- **THEN** Agent SHALL 可以存取排程管理的 MCP 工具
