# add-codex-pipeline-parity

## Why

第一階段（`add-codex-acp-failover`，已 archive）完成了 Claude/Codex 雙備援的核心：provider router、usage monitor、Codex adapter、五個對話入口遷移與群組 canary 上線。但五類特殊 pipeline——**簡報 JSON、生圖流程、research、scheduler 排程任務、對話摘要**——仍固定呼叫 `call_claude()`。Claude 限流時這些功能沒有備援，與「完整雙系統備援」的最終目標仍有落差。

這些 pipeline 各自有嚴格的輸出契約（結構化 JSON、FILE_MESSAGE marker、工具呼叫序列、背景任務副作用），不能像對話入口一樣直接切換：必須先以 parity tests 鎖住每個 pipeline 的輸出契約，證明 Codex 能滿足後才逐一遷移；無法滿足者明確維持 Claude 並記錄原因。

## What Changes

### 1. Pipeline parity test harness

- 為每個 pipeline 定義 provider-neutral 的輸出契約測試（fake provider 可注入），涵蓋：JSON 結構、marker 格式、工具序列、錯誤與重試行為。
- Parity tests 同時對 Claude 契約（characterization）與 Codex fake/真實 smoke 執行。

### 2. 逐 pipeline 遷移（風險由低到高）

1. **summary（對話壓縮）**：純文字輸出，最低風險，先行。
2. **簡報 JSON（outline 生成）**：結構化 JSON 輸出，沿用既有 JSON 解析/修復路徑。
3. **research**：WebSearch/WebFetch 工具契約與背景 job 狀態格式。
4. **生圖流程**：nanobanana/codex-image marker 與 fallback 階梯的 provider 相容性。
5. **scheduler 排程任務**：副作用最多（訊息發送、資料寫入），最後遷移；需要 per-pipeline 工具政策支撐。

每個 pipeline 遷移 = 通過 parity tests + 改用 `call_ai()` + 專屬 `RoutingContext`；未通過者維持 `call_claude()` 並在 tasks 記錄阻擋原因。

### 3. Per-pipeline 工具政策

- 現行 Codex 唯讀過濾（`search_/get_/read_/list_/find_`）對 scheduler/生圖不足。
- 擴充 router 的工具過濾為可依 routing context 附帶「明確額外 allowlist」，預設仍為唯讀 fail-closed；任何放行的副作用工具必須有專屬測試。

### 4. 可觀測性沿用

- 各 pipeline 的 routing metadata 寫入 `ai_logs.parsed_response`，沿用 `ai_route` structured log 與 canary checklist。

## Capabilities

### New Capabilities

（無——本 change 全部屬於既有 routing capability 的需求擴充）

### Modified Capabilities

- `ai-provider-routing`: 新增特殊 pipeline 的 parity gate 要求、per-context 工具政策擴充，以及 pipeline 遷移順序與阻擋記錄規則。

## Impact

- **修改**：`services/ai_router.py`（per-context 工具政策）、`services/presentation.py`、`services/claude_agent.py::call_claude_for_summary` 的 caller、research/scheduler/生圖相關 caller、對應 prompt 若需 provider-neutral 化。
- **新增測試**：每 pipeline 的 parity tests、工具政策測試。
- **不動**：資料庫 schema、部署流程、既有對話入口行為。
- **設定**：canary contexts 逐 pipeline 加入（env，營運控制）。

## Constraints

- 未通過 parity tests 的 pipeline MUST 維持 `call_claude()`。
- per-pipeline 額外工具 allowlist MUST fail-closed、逐工具明確列舉並有測試。
- 整體 coverage 不得低於 90% gate。
- 不得改變任何已遷移對話入口的行為。

## Out of Scope

- `CODEX_MODEL` 按 role 分級對應。
- 一般 `linebot-personal` / `telegram-*` / restricted 的 canary 開通（純營運設定，不需程式變更）。
- 跨 provider shadow comparison 與品質評比。
- intent_guard（Haiku 前置過濾）與 `/debug` 管理指令的遷移。
