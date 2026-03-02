## Context

系統目前使用 APScheduler（AsyncIOScheduler）執行排程任務，所有排程定義分散在兩處：

1. **核心硬編碼**（`scheduler.py` 的 `start_scheduler()`）：cleanup_old_messages、create_next_month_partitions、cleanup_expired_share_links、cleanup_old_bot_tracking
2. **模組宣告**（`modules.py` 的 `BUILTIN_MODULES` + Skill `contributes.scheduler`）：由 `_register_module_job()` 在啟動時從模組 registry 動態註冊

兩者共同點：排程定義在程式碼中，執行的是 Python 函式，純記憶體儲存，重啟後從程式碼重建。

Agent 系統已有成熟的程式化呼叫路徑：`call_claude(prompt, model, system_prompt, tools, ctos_user_id)` 支援指定 Agent 執行任務，並自動記錄到 `ai_logs`。Skill Script 系統也已有 `run_skill_script(skill, script, input)` 可直接呼叫。

## Goals / Non-Goals

**Goals:**
- 使用者可在 Web UI 管理動態排程（查看 / 新增 / 編輯 / 刪除 / 啟停用）
- 排程定義持久化到資料庫，服務重啟後自動恢復
- 支援兩種執行模式：Agent 執行（指定 Agent + 指令）與 Skill Script 呼叫
- AI Agent 可透過 MCP 工具動態建立排程
- 排程執行結果有完整日誌可追蹤
- 與現有硬編碼排程和平共存

**Non-Goals:**
- 不遷移現有核心硬編碼排程（cleanup、partition 等維運任務保持原狀）
- 不實作 DAG / 任務依賴鏈（排程之間互相獨立）
- 不實作分散式排程（單機 APScheduler 足夠）
- 不實作排程任務的即時輸出串流（僅記錄最終結果）
- 不實作複雜的重試策略（首版只支援簡單的失敗記錄）

## Decisions

### D1: 資料庫表格設計 — 單表 `scheduled_tasks`

**選擇**：使用單一表格 `scheduled_tasks` 儲存所有動態排程定義。

**欄位設計**：
```
id              UUID PK
name            VARCHAR(128) UNIQUE     -- 排程名稱
description     TEXT                    -- 說明
trigger_type    VARCHAR(16)             -- 'cron' | 'interval'
trigger_config  JSONB                   -- cron: {hour, minute, day_of_week, ...}
                                        -- interval: {hours, minutes, seconds}
executor_type   VARCHAR(16)             -- 'agent' | 'skill_script'
executor_config JSONB                   -- agent: {agent_name, prompt, ctos_user_id}
                                        -- skill_script: {skill, script, input}
is_enabled      BOOLEAN DEFAULT true
created_by      INTEGER REFERENCES users(id)
last_run_at     TIMESTAMP
next_run_at     TIMESTAMP
last_run_success BOOLEAN
last_run_error  TEXT
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

**替代方案**：分表（排程定義 + 執行記錄分開）。首版不需要，執行結果只記錄最後一次狀態，詳細記錄由 `ai_logs` 承擔。未來若需完整執行歷史再加 `scheduled_task_runs` 表。

### D2: 執行引擎架構 — 擴充現有 scheduler.py

**選擇**：在現有 `scheduler.py` 中新增動態排程載入邏輯，新增 `services/task_scheduler.py` 處理 CRUD 和執行邏輯。

**啟動流程**：
```
start_scheduler()
├── 註冊核心硬編碼任務（不變）
├── 註冊模組宣告任務（不變）
└── load_dynamic_tasks()  ← 新增
    ├── 從 DB 查詢所有 is_enabled=true 的排程
    └── 逐一用 scheduler.add_job() 註冊
```

**動態更新**：當使用者透過 API 新增 / 修改 / 刪除排程時，同步更新 APScheduler 中的 job（`add_job` / `modify_job` / `remove_job`），無需重啟。

**替代方案**：完全獨立的排程引擎。不採用，因為 APScheduler 已滿足需求，且核心任務也使用它，統一管理更簡單。

### D3: 執行模式 — Agent 與 Skill Script 雙軌

**Agent 模式**（`executor_type = 'agent'`）：
```python
agent = await ai_manager.get_agent_by_name(config['agent_name'])
response = await call_claude(
    prompt=config['prompt'],
    model=agent['model'],
    system_prompt=agent['system_prompt_content'],
    tools=agent.get('tools'),
    ctos_user_id=config.get('ctos_user_id'),
)
```

**Skill Script 模式**（`executor_type = 'skill_script'`）：
```python
result = await run_skill_script(
    skill=config['skill'],
    script=config['script'],
    input=config.get('input', ''),
    ctos_user_id=config.get('ctos_user_id'),
)
```

兩種模式都已有成熟的執行路徑和日誌記錄（`ai_logs`），不需要造新輪子。

### D4: 前端 — 桌面應用程式（Skill contributes 方式）

**選擇**：以新的 Skill（`task-scheduler`）透過 `contributes.app` 提供桌面應用。

**理由**：遵循現有架構模式（類似 `agent-settings`、`ai-assistant` 等應用），符合模組化設計。

**UI 功能**：
- 排程列表（表格，含狀態、下次執行時間、最後執行結果）
- 新增 / 編輯排程的 Modal 表單（選擇觸發類型、設定時間、選擇 Agent 或 Skill Script、輸入 prompt）
- 啟用 / 停用切換
- 手動觸發（立即執行一次）
- 刪除確認

### D5: Agent Skill — MCP 工具設計

**新增 MCP 工具**：

| 工具名稱 | 用途 |
|---------|------|
| `manage_scheduled_task` | 建立 / 修改 / 刪除排程（合併為單一工具，以 action 參數區分） |
| `list_scheduled_tasks` | 查詢排程列表 |

**合併工具的理由**：減少 Agent 的工具選擇負擔，一個工具用 action 參數（create / update / delete / enable / disable）涵蓋所有操作。

### D6: 動態排程 Job ID 命名

**格式**：`dynamic:{task_uuid}`

**理由**：與核心任務（如 `cleanup_old_messages`）和模組任務（如 `file-manager:cleanup_linebot_temp_files`）命名空間隔離，避免衝突。

### D7: 權限控制

**選擇**：排程管理需要管理員權限（`role = admin`），Agent 建立排程需通過 `ctos_user_id` 的權限檢查。

**理由**：排程可以觸發 Agent 執行任意指令，屬於高權限操作。首版限制為管理員專用，未來可考慮更細粒度的權限。

## Risks / Trade-offs

- **排程觸發 Agent 的成本風險** → 設定排程最小間隔限制（如 cron 最小 1 分鐘、interval 最小 5 分鐘），UI 顯示預估費用提醒
- **Agent 執行超時** → 使用 `call_claude` 的 timeout 參數（預設 180 秒），超時記錄為失敗
- **排程失敗無人察覺** → `last_run_success` / `last_run_error` 欄位 + UI 上以顏色標示失敗狀態；未來可加通知機制
- **服務重啟時排程遺失** → 啟動時從 DB 重建所有動態排程，APScheduler 用 `replace_existing=True`
- **併發衝突（同一排程重複觸發）** → APScheduler 的 `max_instances=1` 確保同一 job 不會併發執行

## Migration Plan

1. 新增 Alembic migration 建立 `scheduled_tasks` 表格
2. 部署後端（新增 service + API + MCP 工具）
3. 部署前端（新增桌面應用）
4. 服務重啟後 `start_scheduler()` 自動從 DB 載入動態排程
5. 無需資料遷移，現有排程不受影響

**Rollback**：移除 API 路由和前端即可，`scheduled_tasks` 表格保留不影響系統運行。

## Open Questions

- 是否需要排程執行歷史表（`scheduled_task_runs`）？首版只記錄最後一次結果，詳細日誌在 `ai_logs` 中已有
- 未來是否允許非管理員建立排程？（可能需要 quota 或審核機制）
- 是否需要排程分組 / 標籤功能？
