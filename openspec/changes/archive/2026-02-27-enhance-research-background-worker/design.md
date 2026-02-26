## Context

目前 `research-skill` 已提供 `start-research` / `check-research` 兩段式，但核心流程仍以輕量搜尋與擷取為主。  
當 LLM 在對話主回合中改走內建 `WebSearch/WebFetch`，整體會被 480 秒 timeout 綁死，導致使用者拿不到完整結果或只拿到部分結果。

本變更目標是把「完整研究（多輪 search + fetch + synthesis）」移到背景 worker，讓主回合只負責受理與回報進度。  
同時保留在 worker 內呼叫 Claude（含 `WebSearch/WebFetch`）的能力，兼顧結果品質與即時回覆穩定性。

## Goals / Non-Goals

**Goals:**
- 建立可持續執行的研究任務生命週期（queued/running/completed/failed/canceled）。
- `start-research` 快速回傳 `job_id`，不阻塞主回合。
- 背景 worker 可執行「Claude + WebSearch/WebFetch」完整研究流程，並輸出可重現產物。
- `check-research` 可回傳階段、進度、失敗原因、結果路徑，支援使用者反覆查詢。
- 提供併發上限、超時、重試與去重策略，避免任務堆積。

**Non-Goals:**
- 本次不將所有一般問答都改為背景任務。
- 本次不改動 Claude 內建工具本身（仍透過既有 `call_claude`）。
- 本次不做跨機器分散式 queue（先以單機背景執行為主）。

## Decisions

### 1) 採「協調器 + worker」架構，start/check 只做控制平面
- **Decision**: `start-research` 只建立 job 與排隊；`check-research` 只讀狀態與結果，不執行重負載研究。
- **Why**: 避免對話主回合被長任務綁住，確保先回覆使用者。
- **Alternatives considered**:
  - 在 `start-research` 內直接做完整研究：仍有主回合 timeout 風險，不採用。
  - 只靠 prompt 約束模型：無法保證執行路徑，不採用。

### 2) worker 內允許第二層 Claude 呼叫（受控工具白名單）
- **Decision**: worker 內新增 research executor，呼叫 `call_claude(...)`，工具限制為研究所需集合（WebSearch/WebFetch + 必要腳本工具）。
- **Why**: 內建 web tools 結果完整度較高，且不再影響即時回覆。
- **Alternatives considered**:
  - 全面改成純腳本爬取：實作成本高、品質不穩，不採用。
  - 完全依賴 Brave/DDG provider：品質不足，不採用。

### 3) 研究結果標準化落盤
- **Decision**: 每個 job 產出固定檔案：
  - `status.json`（狀態/進度/錯誤/provider）
  - `result.md`（最終研究報告）
  - `sources.json`（來源清單）
  - `tool_trace.json`（工具呼叫摘要）
- **Why**: 便於 `check-research` 回傳、追查與後續再分析。
- **Alternatives considered**:
  - 僅存最終摘要：除錯困難，不採用。
  - 全存 DB：本次先沿用檔案型 job storage，降低遷移風險。

### 4) 任務治理：去重、重試、併發與上限
- **Decision**:
  - 同使用者/同主題短時間內可做 job 去重（回傳既有 job_id）。
  - worker 設置併發上限與任務 TTL。
  - 階段性失敗（例如 fetch 層）允許有限重試。
- **Why**: 降低 API 成本與資源耗盡風險，避免殭屍任務。
- **Alternatives considered**:
  - 無治理自由執行：高風險，不採用。
  - 嚴格單工不重試：成功率過低，不採用。

### 5) Bot 規則強制化（研究路徑鎖定）
- **Decision**: 在 bot prompt 與 usage tips 強制規則：研究類需求固定 start/check；check 失敗需重新 start，不切回同步 `WebSearch/WebFetch`。
- **Why**: 避免已知「回到同步流程再超時」回歸。
- **Alternatives considered**:
  - 只加建議語氣：仍可能被模型忽略，不採用。

## Risks / Trade-offs

- **[worker 內再呼叫 Claude 成本上升]** → 以任務去重、併發上限、單任務 token/時間上限控制成本。  
- **[背景任務堆積]** → 增加 queue depth 監控、過期回收、取消機制。  
- **[WebSearch/WebFetch 外部波動]** → 增加重試與階段降級（部分來源仍可輸出 partial result）。  
- **[資料追蹤檔案膨脹]** → `tool_trace.json` 做截斷與保留天數清理。  
- **[模型偏離規則]** → 在 prompt 外，再由研究協調器層做路徑守衛（check 失敗時直接回建議重啟，不自動同步抓取）。

## Migration Plan

1. 新增 worker 模組與 job queue（先單機 in-process background task）。
2. 重構 `start-research`：
   - 建 job + status=queued
   - enqueue 並立即回 `job_id`
3. 實作 worker research executor：
   - 更新狀態（running/fetching/synthesizing）
   - 呼叫 `call_claude`（受控工具）
   - 落盤 `result.md` / `sources.json` / `tool_trace.json`
4. 擴充 `check-research` 回傳欄位與失敗診斷。
5. 更新 linebot prompt / usage tips，防止切回同步路徑。
6. 加上回歸測試（兩段式、失敗重啟、worker 成功完成、超時治理）。

Rollback:
- 保留舊 `start-research` 執行器實作，透過 feature flag 切回簡化模式。
- worker 異常時，`start-research` 可降級為「僅建立任務+提示稍後重試」而不啟動完整流程。

## Open Questions

- 背景 worker 啟動方式：沿用 `os.fork` 還是改為專用 asyncio task/queue manager？
- worker 內 Claude 模型預設是否固定（sonnet）或依情境（haiku/sonnet）切換？
- `tool_trace.json` 需保留到多細（完整 output vs 摘要）以兼顧可觀測與敏感資料風險？
- 是否要把 job metadata 逐步搬到資料庫，提升查詢與清理能力？
