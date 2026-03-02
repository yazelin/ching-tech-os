## Why

目前系統的排程任務全部硬編碼在 `scheduler.py` 或模組定義中，使用 APScheduler 的純記憶體儲存。沒有 UI 可以查看、新增、修改或刪除排程，也無法在執行時期動態調整。要新增排程必須改程式碼並重啟服務。系統需要一個像 OS 等級的排程管理能力——讓使用者和 AI Agent 都能動態管理排程任務，並且排程的執行內容不再侷限於硬編碼函式，而是可以指定由某個 Agent 執行某項工作。

## What Changes

- 新增資料庫表格 `scheduled_tasks` 持久化儲存排程定義（觸發規則、執行目標、啟用狀態等）
- 新增排程管理 API（CRUD）供前端與 Agent 使用
- 新增前端排程管理 UI（桌面應用程式），可查看所有排程、新增 / 編輯 / 刪除 / 啟停用
- 排程執行方式改為「指定 Agent + 指令」模式——排程觸發時由系統呼叫指定 Agent 執行指定任務描述
- 支援 Skill Script 作為排程執行目標（直接呼叫 `run_skill_script`）
- 新增 MCP 工具 / Skill 讓 AI Agent 可以建立和管理排程
- **BREAKING**: 現有硬編碼的核心排程任務（cleanup、partition 等）保留不動，但模組透過 `contributes.scheduler` 宣告的排程未來應遷移為動態排程

## Capabilities

### New Capabilities
- `task-scheduler-storage`: 排程任務的資料庫持久化儲存（表格設計、migration、CRUD service）
- `task-scheduler-api`: 排程管理 REST API（列表、新增、修改、刪除、啟停用）
- `task-scheduler-ui`: 前端排程管理桌面應用程式（查看 / 編輯 / 建立排程）
- `task-scheduler-executor`: 排程執行引擎——支援 Agent 執行和 Skill Script 呼叫兩種模式
- `task-scheduler-agent-skill`: AI Agent 管理排程的 MCP 工具 / Skill（讓 Agent 可以建立排程）

### Modified Capabilities
- `skill-contributes`: `contributes.scheduler` 的宣告方式需擴充，支援宣告動態排程（除了現有的硬編碼函式註冊外）
- `feature-modules`: 模組 registry 的 `scheduler_jobs` 需與新的動態排程系統整合

## Impact

- **資料庫**: 新增 `scheduled_tasks` 表格（需 Alembic migration）
- **後端**: `services/scheduler.py` 需擴充為同時支援靜態 + 動態排程；新增 `services/task_scheduler.py` 或類似的 service 層
- **API**: 新增 `/api/scheduler/` 路由群組
- **前端**: 新增排程管理桌面應用（JS + CSS）
- **MCP/Skills**: 新增排程管理相關 MCP 工具
- **依賴**: 無新增外部依賴（APScheduler 已存在）
- **Agent 系統**: 需整合 `services/bot/agents.py` 的 Agent 呼叫機制，讓排程能觸發 Agent 執行
