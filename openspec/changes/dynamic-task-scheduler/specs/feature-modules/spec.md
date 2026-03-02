## MODIFIED Requirements

### Requirement: Conditional Scheduler Jobs
系統 SHALL 只為啟用模組註冊排程任務。

#### Scenario: 啟用模組的排程任務註冊
- **WHEN** 模組啟用且 `ModuleInfo` 包含 `scheduler_jobs`
- **THEN** SHALL 註冊對應的排程任務到 APScheduler

#### Scenario: 停用模組的排程任務不註冊
- **WHEN** 模組停用
- **THEN** 其排程任務 SHALL 不註冊，不執行

#### Scenario: Core 排程任務永遠啟用
- **WHEN** 系統啟動
- **THEN** `cleanup_old_messages`、`create_next_month_partitions`、`cleanup_expired_share_links` SHALL 永遠註冊

#### Scenario: 動態排程載入
- **WHEN** 系統啟動且所有模組排程註冊完成後
- **THEN** SHALL 呼叫 `load_dynamic_tasks()` 從 `scheduled_tasks` 表載入動態排程
- **THEN** 動態排程 SHALL 在核心排程和模組排程之後註冊

#### Scenario: 模組宣告動態排程
- **WHEN** 模組的 `scheduler_jobs` 包含 `executor_type` 欄位的項目
- **THEN** SHALL 將該項目作為動態排程處理（寫入 `scheduled_tasks` 表），而非直接註冊 Python 函式
