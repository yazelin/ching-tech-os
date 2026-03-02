## ADDED Requirements

### Requirement: scheduled_tasks 資料表
系統 SHALL 提供 `scheduled_tasks` 資料表儲存動態排程定義，支援持久化和服務重啟後恢復。

#### Scenario: 資料表結構
- **WHEN** Alembic migration 執行完成
- **THEN** `scheduled_tasks` 表 SHALL 包含以下欄位：
  - `id` (UUID, PK)
  - `name` (VARCHAR(128), UNIQUE, NOT NULL)
  - `description` (TEXT, nullable)
  - `trigger_type` (VARCHAR(16), NOT NULL) — 值為 `cron` 或 `interval`
  - `trigger_config` (JSONB, NOT NULL) — 觸發規則參數
  - `executor_type` (VARCHAR(16), NOT NULL) — 值為 `agent` 或 `skill_script`
  - `executor_config` (JSONB, NOT NULL) — 執行目標參數
  - `is_enabled` (BOOLEAN, DEFAULT true)
  - `created_by` (INTEGER, FK → users.id, nullable)
  - `last_run_at` (TIMESTAMP, nullable)
  - `next_run_at` (TIMESTAMP, nullable)
  - `last_run_success` (BOOLEAN, nullable)
  - `last_run_error` (TEXT, nullable)
  - `created_at` (TIMESTAMP, NOT NULL)
  - `updated_at` (TIMESTAMP, NOT NULL)

#### Scenario: trigger_config 格式 — cron
- **WHEN** `trigger_type` 為 `cron`
- **THEN** `trigger_config` SHALL 包含 APScheduler CronTrigger 支援的欄位子集：`minute`、`hour`、`day`、`month`、`day_of_week`
- **THEN** 每個欄位 SHALL 接受字串值（如 `"*/5"`、`"1-5"`、`"*"`）

#### Scenario: trigger_config 格式 — interval
- **WHEN** `trigger_type` 為 `interval`
- **THEN** `trigger_config` SHALL 包含以下欄位之一或多個：`weeks`、`days`、`hours`、`minutes`、`seconds`
- **THEN** 欄位值 SHALL 為正整數

#### Scenario: executor_config 格式 — agent
- **WHEN** `executor_type` 為 `agent`
- **THEN** `executor_config` SHALL 包含：
  - `agent_name` (string, 必填) — 對應 `ai_agents.name`
  - `prompt` (string, 必填) — 要求 Agent 執行的指令
  - `ctos_user_id` (integer, 選填) — 執行身份

#### Scenario: executor_config 格式 — skill_script
- **WHEN** `executor_type` 為 `skill_script`
- **THEN** `executor_config` SHALL 包含：
  - `skill` (string, 必填) — Skill 名稱
  - `script` (string, 必填) — Script 名稱
  - `input` (string, 選填) — JSON 格式的輸入資料
  - `ctos_user_id` (integer, 選填) — 執行身份

### Requirement: 排程 CRUD Service
系統 SHALL 提供 `services/task_scheduler.py` 實作排程定義的 CRUD 操作。

#### Scenario: 建立排程
- **WHEN** 呼叫 `create_scheduled_task(data)` 並提供有效資料
- **THEN** SHALL 在 `scheduled_tasks` 表插入一筆記錄
- **THEN** SHALL 回傳新建排程的完整資料（含 `id`、`created_at`）

#### Scenario: 建立排程 — 名稱重複
- **WHEN** 提供的 `name` 已存在
- **THEN** SHALL raise 錯誤，不建立記錄

#### Scenario: 查詢排程列表
- **WHEN** 呼叫 `list_scheduled_tasks()`
- **THEN** SHALL 回傳所有排程記錄，依 `created_at` 降序排列

#### Scenario: 查詢單一排程
- **WHEN** 呼叫 `get_scheduled_task(task_id)` 並提供有效 UUID
- **THEN** SHALL 回傳該排程的完整資料

#### Scenario: 查詢單一排程 — 不存在
- **WHEN** 提供的 `task_id` 不存在
- **THEN** SHALL 回傳 None

#### Scenario: 更新排程
- **WHEN** 呼叫 `update_scheduled_task(task_id, data)` 並提供有效資料
- **THEN** SHALL 更新對應記錄並更新 `updated_at`
- **THEN** SHALL 回傳更新後的完整資料

#### Scenario: 刪除排程
- **WHEN** 呼叫 `delete_scheduled_task(task_id)` 並提供有效 UUID
- **THEN** SHALL 刪除對應記錄
- **THEN** SHALL 回傳 True

#### Scenario: 切換啟用狀態
- **WHEN** 呼叫 `toggle_scheduled_task(task_id, is_enabled)`
- **THEN** SHALL 更新 `is_enabled` 欄位並更新 `updated_at`

#### Scenario: 更新執行結果
- **WHEN** 呼叫 `update_task_run_result(task_id, success, error)`
- **THEN** SHALL 更新 `last_run_at`、`last_run_success`、`last_run_error` 欄位
