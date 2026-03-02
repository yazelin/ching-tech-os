## ADDED Requirements

### Requirement: 動態排程載入
系統 SHALL 在啟動時從資料庫載入所有啟用的動態排程並註冊到 APScheduler。

#### Scenario: 啟動時載入動態排程
- **WHEN** `start_scheduler()` 執行
- **THEN** SHALL 在註冊核心排程和模組排程之後，呼叫 `load_dynamic_tasks()`
- **THEN** `load_dynamic_tasks()` SHALL 查詢所有 `is_enabled=true` 的 `scheduled_tasks` 記錄
- **THEN** SHALL 為每筆記錄呼叫 `scheduler.add_job()` 註冊到 APScheduler

#### Scenario: 動態排程 Job ID
- **WHEN** 註冊動態排程到 APScheduler
- **THEN** Job ID SHALL 使用格式 `dynamic:{task_uuid}`
- **THEN** SHALL 使用 `replace_existing=True` 避免重複註冊

#### Scenario: 資料庫連線失敗
- **WHEN** `load_dynamic_tasks()` 無法連接資料庫
- **THEN** SHALL log error 但不阻止 `start_scheduler()` 完成
- **THEN** 核心排程和模組排程 SHALL 正常運行

### Requirement: Agent 模式執行
系統 SHALL 支援以 Agent 模式執行排程任務——呼叫指定 Agent 執行指令。

#### Scenario: 執行 Agent 任務
- **WHEN** 動態排程觸發且 `executor_type` 為 `agent`
- **THEN** SHALL 從 `executor_config.agent_name` 查詢 Agent 設定
- **THEN** SHALL 呼叫 `call_claude(prompt, model, system_prompt, tools, ctos_user_id)` 執行任務
- **THEN** 執行結果 SHALL 自動記錄到 `ai_logs` 表

#### Scenario: Agent 不存在
- **WHEN** `executor_config.agent_name` 對應的 Agent 不存在
- **THEN** SHALL 記錄失敗（`last_run_success=false`，`last_run_error` 包含 Agent 未找到的訊息）
- **THEN** SHALL 不中斷排程器運行

#### Scenario: Agent 執行超時
- **WHEN** Agent 執行超過 timeout（預設 180 秒）
- **THEN** SHALL 記錄為失敗，`last_run_error` 包含超時訊息

### Requirement: Skill Script 模式執行
系統 SHALL 支援以 Skill Script 模式執行排程任務——直接呼叫指定 Skill 的 Script。

#### Scenario: 執行 Skill Script 任務
- **WHEN** 動態排程觸發且 `executor_type` 為 `skill_script`
- **THEN** SHALL 呼叫 `run_skill_script(skill, script, input, ctos_user_id)` 執行任務
- **THEN** 執行結果 SHALL 記錄到 `ai_logs` 表

#### Scenario: Skill 或 Script 不存在
- **WHEN** 指定的 `skill` 或 `script` 不存在
- **THEN** SHALL 記錄失敗並包含錯誤訊息
- **THEN** SHALL 不中斷排程器運行

### Requirement: 執行結果記錄
系統 SHALL 在每次排程任務執行完成後更新執行結果。

#### Scenario: 執行成功
- **WHEN** 排程任務執行成功
- **THEN** SHALL 更新 `last_run_at` 為當前時間
- **THEN** SHALL 設定 `last_run_success = true`
- **THEN** SHALL 清空 `last_run_error`

#### Scenario: 執行失敗
- **WHEN** 排程任務執行過程中發生例外
- **THEN** SHALL 更新 `last_run_at` 為當前時間
- **THEN** SHALL 設定 `last_run_success = false`
- **THEN** SHALL 將錯誤訊息寫入 `last_run_error`
- **THEN** SHALL 不中斷排程器，後續排程 SHALL 繼續正常觸發

### Requirement: 併發控制
系統 SHALL 防止同一排程任務併發執行。

#### Scenario: 任務仍在執行中時觸發
- **WHEN** 排程任務的上一次執行尚未完成時再次觸發
- **THEN** SHALL 跳過本次觸發（APScheduler `max_instances=1`）

### Requirement: 動態更新同步
系統 SHALL 在排程定義變更時即時同步 APScheduler 狀態。

#### Scenario: 新增排程後同步
- **WHEN** 透過 API 或 MCP 工具新增一筆啟用的排程
- **THEN** SHALL 立即在 APScheduler 註冊對應 job，無需重啟服務

#### Scenario: 修改排程後同步
- **WHEN** 透過 API 修改排程的觸發規則或執行設定
- **THEN** SHALL 移除舊 job 並重新註冊新 job

#### Scenario: 刪除排程後同步
- **WHEN** 透過 API 刪除排程
- **THEN** SHALL 從 APScheduler 移除對應 job

#### Scenario: 停用排程後同步
- **WHEN** 排程的 `is_enabled` 從 true 改為 false
- **THEN** SHALL 從 APScheduler 移除對應 job

#### Scenario: 啟用排程後同步
- **WHEN** 排程的 `is_enabled` 從 false 改為 true
- **THEN** SHALL 在 APScheduler 註冊對應 job
