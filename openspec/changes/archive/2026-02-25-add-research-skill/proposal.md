## Why

目前 Claude 內建 WebSearch / WebFetch 在多輪外部研究場景容易出現「部分工具成功、整體回合仍超時」的情況，且結果整合品質與可追蹤性不足。現在需要一個可控、可查進度、可持久化中間結果的 research skill，降低超時與回覆不完整風險。

## What Changes

- 新增 script-first 的 `research-skill` 能力，提供「搜尋 + 擷取 + 統整」的一體化流程。
- 新增 `start/check` 兩段式研究流程：
  - `start_research`：立即回傳 `job_id`，背景執行搜尋與擷取。
  - `check_research`：查詢進度、部分結果與最終統整內容。
- 研究流程支援多來源 URL 蒐集、內容擷取、去重與結構化輸出（含來源列表與摘要）。
- Bot 對外部研究任務改為優先走 `research-skill`，降低對 Claude 內建 WebSearch / WebFetch 的直接依賴。
- 保留相容性回退路徑：必要時可回退既有工具，但預設以 `research-skill` 為主。

## Capabilities

### New Capabilities
- `research-skill`: 提供可非同步執行的「搜尋 + 擷取 + 統整」研究能力，包含 start/check 工作流、進度查詢與結果統整格式。

### Modified Capabilities
- `bot-platform`: 調整工具路由策略，外部研究任務優先使用 `research-skill`（`run_skill_script`）並支援回退策略。
- `line-bot`: 群組/個人對話在長時研究任務中採用 start/check 互動模式，先回覆已受理與查詢方式，再由使用者查進度。

## Impact

- 受影響程式：
  - `backend/src/ching_tech_os/skills/`（新增 `research-skill` 與 scripts）
  - `backend/src/ching_tech_os/services/bot/agents.py`
  - `backend/src/ching_tech_os/services/linebot_ai.py`
  - `backend/src/ching_tech_os/services/linebot_agents.py`
- 受影響行為：
  - 外部研究類請求的工具選擇與回覆節奏（同步改為 start/check 非同步）
  - 超時時的降級與結果可見性
- 相依與運維：
  - 可能新增研究任務狀態檔或任務儲存機制
  - 需補齊 skill prompt/文件與測試案例，驗證群組與個人對話的一致行為
