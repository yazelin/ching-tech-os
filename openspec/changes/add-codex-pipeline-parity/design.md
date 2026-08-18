# add-codex-pipeline-parity 設計

## Context

第一階段的 `call_ai()` 路由已上線（0.10.0，auto mode + 群組 canary），五類特殊 pipeline 仍固定 `call_claude()`：

| Pipeline | 入口 | 輸出契約 | 工具需求 |
|----------|------|----------|----------|
| summary | `claude_agent.call_claude_for_summary`（`api/ai.py` 對話壓縮）| 純文字摘要 | 無 |
| 簡報 JSON | `presentation.generate_outline` | 嚴格 JSON（slides 結構）| 無 |
| research | research-skill 背景 job | job 狀態 JSON、WebSearch/WebFetch | WebSearch/WebFetch（非 MCP）|
| 生圖 | linebot 生圖流程、`presentation.fetch_image` | FILE_MESSAGE marker、nanobanana 工具序列 | nanobanana/codex-image MCP（生圖=副作用類）|
| scheduler | `task_scheduler` agent 任務 | 執行結果 + 副作用工具 | 訊息發送、資料寫入等副作用 MCP |

Codex 端既有限制：唯讀工具過濾（`filter_codex_readonly_tools`）、原生圖片/terminal/file-write deny、WebSearch/WebFetch 等非 canonical 名稱會被過濾掉。

## Goals / Non-Goals

**Goals:**

- 每個 pipeline 有 provider-neutral parity tests，鎖住輸出契約後才遷移。
- 依風險由低到高遷移；被阻擋的 pipeline 維持 Claude 並記錄原因。
- Router 支援 per-context 額外工具 allowlist（fail-closed），供 scheduler/生圖使用。
- 沿用既有可觀測性（ai_route log、parsed_response.routing）。

**Non-Goals:**

- 不追求兩個模型輸出品質等價，只驗證「格式與工具契約可被滿足」。
- 不做 CODEX_MODEL 分級、shadow comparison。
- 不動已遷移入口與資料庫 schema。

## Decisions

### 1. Parity test 形式

以 fake provider 注入 `call_ai()` 邊界驗證 caller 端解析行為（characterization），另以 Codex fake client fixture 驗證 provider 端輸出傳遞；真實 Codex smoke（opt-in env）只驗最小案例。三層與第一階段測試策略一致。

### 2. 遷移順序與 gate

summary → 簡報 JSON → research → 生圖 → scheduler。每階段獨立 commit、獨立 canary context（如 `presentation`、`scheduler`），營運可逐 pipeline 用 env 開關。前一階段未過不阻擋後一階段的 parity test 開發，但阻擋其「遷移」。

### 3. Per-context 工具政策

`ProviderRouter.execute()` 的 Codex 過濾改為：唯讀前綴 allowlist ∪ 該 routing context 的明確額外 allowlist（新設定 `CODEX_CONTEXT_TOOL_ALLOWLIST`，格式 `context:tool1|tool2,context2:...`，經驗證解析）。預設空 = 現行為完全不變。任何額外放行需 spec scenario + 測試。

### 4. WebSearch/WebFetch（research）

非 MCP 工具在 Codex 端無對應能力，第一版 research 遷移只涵蓋「job 狀態查詢」路徑（唯讀）；啟動新研究維持 Claude。若 Codex 端未來提供等價工具再另議。

## Risks / Trade-offs

- **[結構化 JSON 差異]** Codex 輸出 JSON 格式偏差 → 沿用既有 JSON 修復/重試 parser，parity test 覆蓋修復路徑；仍失敗則該 pipeline 維持 Claude。
- **[scheduler 副作用]** 排程任務跨 provider 重放風險 → 沿用「provider 失敗不重送」規則；額外 allowlist 逐工具開放並測試。
- **[生圖上限]** nanobanana/codex-image 全域上限已在 provider 層強制，遷移不得繞過（沿用第一階段測試）。
