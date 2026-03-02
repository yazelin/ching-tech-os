## ADDED Requirements

### Requirement: 排程管理 REST API
系統 SHALL 提供 `/api/scheduler/` 路由群組，供前端和外部呼叫管理動態排程。所有端點 SHALL 要求管理員權限。

#### Scenario: 列出所有排程
- **WHEN** GET `/api/scheduler/tasks`
- **THEN** SHALL 回傳所有動態排程的列表（含靜態核心排程的唯讀資訊）
- **THEN** 回應 SHALL 包含每筆排程的 `id`、`name`、`description`、`trigger_type`、`trigger_config`、`executor_type`、`executor_config`、`is_enabled`、`last_run_at`、`next_run_at`、`last_run_success`、`last_run_error`、`created_at`

#### Scenario: 列出排程 — 包含靜態排程
- **WHEN** GET `/api/scheduler/tasks`
- **THEN** 回應 SHALL 額外包含核心硬編碼排程和模組排程的唯讀資訊
- **THEN** 靜態排程 SHALL 標記 `source: "system"` 或 `source: "module"`，動態排程標記 `source: "dynamic"`

#### Scenario: 建立排程
- **WHEN** POST `/api/scheduler/tasks` 並提供有效的排程定義
- **THEN** SHALL 在資料庫建立排程記錄
- **THEN** SHALL 同步在 APScheduler 註冊 job
- **THEN** SHALL 回傳 201 和新建排程資料

#### Scenario: 建立排程 — 驗證失敗
- **WHEN** POST 提供的資料缺少必填欄位或格式錯誤
- **THEN** SHALL 回傳 422 Validation Error

#### Scenario: 建立排程 — 名稱重複
- **WHEN** POST 提供的 `name` 已存在
- **THEN** SHALL 回傳 409 Conflict

#### Scenario: 取得單一排程
- **WHEN** GET `/api/scheduler/tasks/{task_id}`
- **THEN** SHALL 回傳該排程的完整資料

#### Scenario: 取得排程 — 不存在
- **WHEN** GET `/api/scheduler/tasks/{task_id}` 且 `task_id` 不存在
- **THEN** SHALL 回傳 404

#### Scenario: 更新排程
- **WHEN** PUT `/api/scheduler/tasks/{task_id}` 並提供更新資料
- **THEN** SHALL 更新資料庫記錄
- **THEN** SHALL 同步更新 APScheduler 中的 job（remove + add）
- **THEN** SHALL 回傳更新後的排程資料

#### Scenario: 刪除排程
- **WHEN** DELETE `/api/scheduler/tasks/{task_id}`
- **THEN** SHALL 刪除資料庫記錄
- **THEN** SHALL 從 APScheduler 移除對應 job
- **THEN** SHALL 回傳 204

#### Scenario: 切換啟用狀態
- **WHEN** PATCH `/api/scheduler/tasks/{task_id}/toggle` 並提供 `{"is_enabled": bool}`
- **THEN** SHALL 更新啟用狀態
- **THEN** 啟用時 SHALL 在 APScheduler 註冊 job；停用時 SHALL 移除 job

#### Scenario: 手動觸發排程
- **WHEN** POST `/api/scheduler/tasks/{task_id}/run`
- **THEN** SHALL 立即執行一次該排程的任務（不影響原本的觸發規則）
- **THEN** SHALL 回傳 202 Accepted

#### Scenario: 權限檢查
- **WHEN** 非管理員使用者存取 `/api/scheduler/` 下的任何端點
- **THEN** SHALL 回傳 403 Forbidden
