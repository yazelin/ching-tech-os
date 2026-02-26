## Why

目前 research 任務雖已有 start/check 兩段式，但核心搜尋仍偏簡化；當模型改走內建 WebSearch/WebFetch 時，又可能回到單回合同步執行並觸發 480 秒 timeout。  
需要把「完整研究（多輪 search + fetch + 統整）」搬到背景 worker，先回覆受理，再讓使用者查進度與取結果。

## What Changes

- 在 `research-skill` 新增背景研究執行模式：`start-research` 建立 job 後，由 worker 在背景執行完整研究流程。
- worker 內部支援「第二層 Claude 呼叫」策略，允許使用 WebSearch/WebFetch 進行多來源研究，但不阻塞當前對話回合。
- `check-research` 擴充狀態模型（queued/running/completed/failed）與階段資訊，回傳可讀進度、錯誤原因與結果路徑。
- 統一研究產物：`status.json`、`result.md`、`sources.json`、`tool_trace.json`，讓結果可重現、可審計、可二次分析。
- 新增任務治理：重試策略、併發上限、單任務時間上限、同主題去重與取消機制（避免資源被長任務耗盡）。
- Bot 提示規則更新：研究類需求固定走 start/check；禁止在同主題中回退為同步 WebSearch/WebFetch。

## Capabilities

### New Capabilities
- `research-background-worker`: 非同步背景 worker 執行研究任務生命週期（排隊、執行、完成、失敗、取消）。
- `research-claude-webtools-executor`: 在 worker 中以受控方式呼叫 Claude + WebSearch/WebFetch，產生完整研究結果。
- `research-artifact-tracking`: 研究結果與工具軌跡落盤為標準產物，供 `check-research` 與後續分析使用。

### Modified Capabilities
- `research-skill`: 從「簡化搜尋腳本」升級為「可選擇執行策略的研究協調器」。
- `bot-platform`: 研究場景工具決策規則強化，避免回到同步長回合流程。
- `ai-log-observability`: 增加 worker 任務與子流程（search/fetch/summarize）可觀測欄位。

## Impact

- 受影響程式：
  - `backend/src/ching_tech_os/skills/research-skill/scripts/start-research.py`
  - `backend/src/ching_tech_os/skills/research-skill/scripts/check-research.py`
  - `backend/src/ching_tech_os/services/linebot_ai.py`
  - `backend/src/ching_tech_os/services/claude_agent.py`（worker 內受控呼叫介面）
  - `backend/src/ching_tech_os/services/*`（新增 worker / queue / rate-limit 模組）
- 受影響行為：
  - 使用者先拿到 job_id 與受理訊息；完整研究在背景執行，不阻塞即時回覆。
  - 研究結果可追蹤來源與工具軌跡，支援後續二次分析與除錯。
- 風險與代價：
  - 需要控制併發與 API 成本，避免背景任務堆積。
  - 需要更完整的失敗恢復與任務回收策略，避免殭屍任務。
- 外部相依：
  - Claude CLI/ACP 穩定性與 WebSearch/WebFetch 可用性。
  - （可選）Brave API key；無 key 時仍應提供可用備援策略。
