## 1. 資料庫與 Model

- [x] 1.1 建立 Alembic migration：新增 `scheduled_tasks` 資料表（含所有欄位、索引、FK）
- [x] 1.2 建立 Pydantic 資料模型 `models/scheduled_task.py`（ScheduledTask、ScheduledTaskCreate、ScheduledTaskUpdate、trigger/executor config 子模型）

## 2. Service 層（CRUD + 執行引擎）

- [x] 2.1 建立 `services/task_scheduler.py`：實作 CRUD 函式（create / list / get / update / delete / toggle / update_run_result）
- [x] 2.2 實作 `execute_dynamic_task(task_id)` 執行函式：根據 executor_type 呼叫 Agent（call_claude）或 Skill Script（run_skill_script），執行後更新 last_run 結果
- [x] 2.3 實作 `register_dynamic_job()` / `unregister_dynamic_job()` 輔助函式：將排程定義轉換為 APScheduler add_job / remove_job 呼叫

## 3. 排程載入整合

- [x] 3.1 在 `services/scheduler.py` 的 `start_scheduler()` 末尾新增 `load_dynamic_tasks()` 呼叫，從 DB 載入所有啟用排程並註冊到 APScheduler
- [x] 3.2 處理 DB 連線失敗的 graceful fallback（log error 但不阻止核心排程）

## 4. REST API

- [x] 4.1 建立 `api/scheduler.py` 路由：GET `/api/scheduler/tasks`（列出所有排程，含靜態排程資訊）
- [x] 4.2 實作 POST `/api/scheduler/tasks`（建立排程 + 同步 APScheduler）
- [x] 4.3 實作 GET `/api/scheduler/tasks/{task_id}`（取得單一排程）
- [x] 4.4 實作 PUT `/api/scheduler/tasks/{task_id}`（更新排程 + 同步 APScheduler）
- [x] 4.5 實作 DELETE `/api/scheduler/tasks/{task_id}`（刪除排程 + 移除 APScheduler job）
- [x] 4.6 實作 PATCH `/api/scheduler/tasks/{task_id}/toggle`（啟停用切換 + 同步 APScheduler）
- [x] 4.7 實作 POST `/api/scheduler/tasks/{task_id}/run`（手動觸發立即執行一次）
- [x] 4.8 所有端點加上管理員權限檢查
- [x] 4.9 在 `main.py` 註冊 scheduler router

## 5. 靜態排程資訊收集

- [x] 5.1 在 API 列表端點中整合核心硬編碼排程和模組排程的唯讀資訊（source: system / module / dynamic 標記）

## 6. MCP 工具

- [x] 6.1 在 `services/mcp_server.py` 新增 `manage_scheduled_task` MCP 工具（action 參數：create / update / delete / enable / disable）
- [x] 6.2 新增 `list_scheduled_tasks` MCP 工具（支援 is_enabled 篩選）
- [x] 6.3 兩個工具都加上管理員權限檢查（驗證 ctos_user_id）

## 7. Skill 定義

- [x] 7.1 建立 `backend/src/ching_tech_os/skills/task-scheduler/SKILL.md`：宣告 allowed-tools、contributes.app（id、name、icon、loader、css）、contributes.permissions

## 8. 前端 — 排程管理桌面應用

- [x] 8.1 建立 `frontend/js/task-scheduler.js`：IIFE 模組，實作 TaskSchedulerApp
- [x] 8.2 實作排程列表畫面：卡片顯示名稱、觸發規則摘要、執行類型、啟用狀態、下次執行時間、最後執行結果（含顏色指示）
- [x] 8.3 區分動態排程與靜態排程（標籤 / 分組），靜態排程不可編輯刪除
- [x] 8.4 實作新增 / 編輯排程 Modal 表單：基本資訊、觸發類型切換（cron / interval）、執行類型切換（agent / skill_script）
- [x] 8.5 Agent 模式表單：載入 Agent 下拉選單、prompt 多行輸入
- [x] 8.6 Skill Script 模式表單：載入 Skill / Script 下拉選單、input JSON 輸入
- [x] 8.7 實作啟停用切換、手動觸發、刪除確認功能
- [x] 8.8 建立 `frontend/css/task-scheduler.css`：排程管理應用樣式（使用 CSS 變數）

## 9. 前端整合

- [x] 9.1 在 `index.html` 引入 `task-scheduler.css`
- [x] 9.2 在 `desktop.js` 的 `fallbackAppLoaders` 中註冊排程管理應用（Skill contributes.app 自動註冊機制可用）
- [x] 9.3 確認 `calendar-clock` 圖示存在於 `icons.js`

## 10. Skill Contributes 擴充

- [x] 10.1 擴充 `contributes.scheduler` 宣告支援動態排程項目（含 `executor_type` 欄位時寫入 `scheduled_tasks` 表而非直接註冊函式）
- [x] 10.2 更新模組 registry（`modules.py`）的 `_register_module_job()` 邏輯以區分靜態 vs 動態排程

## 11. 自動化測試

- [x] 11.1 建立 `tests/test_task_scheduler_service.py`：測試 CRUD 函式（create / list / get / update / delete / toggle），mock DB 連線驗證 SQL 呼叫與回傳值
- [x] 11.2 測試 `execute_dynamic_task()`：mock `call_claude` 和 `run_skill_script`，驗證 Agent 模式和 Skill Script 模式分別正確呼叫，驗證成功/失敗情境下 last_run 結果更新
- [x] 11.3 測試 `register_dynamic_job()` / `unregister_dynamic_job()`：mock APScheduler，驗證 cron/interval 兩種 trigger 正確轉換為 add_job 參數，驗證 job ID 格式為 `dynamic:{uuid}`
- [x] 11.4 測試 `load_dynamic_tasks()`：mock DB 回傳多筆啟用排程，驗證全部註冊到 scheduler；mock DB 連線失敗時不拋出例外
- [x] 11.5 建立 `tests/test_api_scheduler_routes.py`：使用 httpx AsyncClient + ASGI transport 測試所有 API 端點（CRUD、toggle、run），驗證回傳狀態碼和 JSON 結構
- [x] 11.6 測試 API 權限檢查：非管理員請求應回傳 403，名稱重複應回傳 409，不存在的 task_id 應回傳 404
- [x] 11.7 測試 Pydantic 模型驗證：trigger_config / executor_config 的必填欄位缺失、不合法值應觸發 ValidationError

## 12. 手動驗證

- [ ] 12.1 手動測試：建立 cron / interval 排程、Agent / Skill Script 兩種執行模式
- [ ] 12.2 驗證服務重啟後動態排程自動恢復
- [ ] 12.3 驗證 MCP 工具可正常建立和管理排程
- [ ] 12.4 驗證前端 UI 所有操作（CRUD、啟停用、手動觸發、狀態顯示）
