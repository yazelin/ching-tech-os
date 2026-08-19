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

## 附註:1.1 盤點結果(2026-08-19)

### 各 pipeline 實際契約與遷移含意

| Pipeline | 呼叫點 | 契約 | 關鍵發現 |
|----------|--------|------|----------|
| summary | `claude_agent.call_claude_for_summary`(api/ai.py compress)| 純文字摘要 → caller 包成 `[對話摘要]\n{...}` system message;model=haiku、summarizer prompt 來自 DB、無工具 | 最單純,直接遷 |
| 簡報 JSON | `presentation.generate_outline` | prompt 要求純 JSON;解析=剝 ``` fence → `json.loads`;失敗 raise ValueError(不重試)| 無工具、單次呼叫;「修復」僅 fence 剝除 |
| research | **無獨立 AI 呼叫** — 經 8.3 已遷移的 `process_message_with_ai`,靠 `mcp__ching-tech-os__run_skill_script`(start/check-research)| job 狀態 JSON 由 MCP 工具回傳,`_extract_research_tool_feedback` 解析 | `run_skill_script` 非唯讀前綴 → Codex 過濾掉;**工具層無法按 script 參數細分權限**,放行=放行任意 script,不可接受 → 第一版 research 意圖(啟動+查詢)一律固定 Claude,以 caller 端既有的決定性偵測(`_should_force_research_check_mode` 同型)實作 |
| 生圖 | 同上經 Line 流程;工具 `mcp__nanobanana__generate_image` 等 + FILE_MESSAGE marker + FLUX fallback | marker 解析與 fallback 在 caller 端,對 provider 中立 | `generate_` 前綴被過濾 → Codex 窗口內無法生圖;3.4 的評估=是否將 nanobanana 生圖工具列入群組 context 的額外 allowlist(受既有全域生圖上限保護);`presentation.fetch_image` 是直接服務呼叫,不經 AI 路由,不受影響 |
| scheduler | `task_scheduler._execute_agent_task`(context_type=scheduler)| agent 設定的 prompt/tools;副作用由 MCP 工具執行;失敗 raise 讓排程記錄 | 遷移需 per-context allowlist;排程屬背景批次,Claude 限流時延後執行即可 → 遷移價值最低,允許結論為「維持 Claude」 |

### 1.2/1.3 現況

Characterization 已由第一階段與 coverage 衝刺覆蓋:`test_claude_agent.py`(summary 契約)、`test_api_ai_events.py`(compress 流程)、`test_presentation_service.py`(outline 成功/壞 JSON/fence)、`test_task_scheduler_service.py`(agent task 成功/找不到)、`test_linebot_ai_service.py`(marker/research feedback 解析)。parity fixture 模式(fake provider 注入 call_ai 邊界)已於 `test_ai_routing_observability.py` 建立,3.x 各遷移沿用並於當步補 provider-neutral 斷言。

## 附註:3.4/3.5 評估結論(2026-08-19)

**3.4 生圖:機制就緒,預設不放行,由營運以 env 啟用。** 放行方式為 `CODEX_CONTEXT_TOOL_ALLOWLIST=linebot-group:mcp__nanobanana__generate_image`(全域生圖上限已在 provider 層強制,phase 5 測試覆蓋)。建議等第一次真實 usage 切換、觀察群組在 Codex 下的表現後再開啟。FLUX fallback 與 marker 解析在 caller 端,對 provider 中立,無需修改。

**3.5 scheduler:維持 Claude(阻擋原因記錄)。** 理由:(1) 背景批次任務在 Claude 限流時延後執行即可,無即時性壓力;(2) 排程 agent 的工具多為副作用型(訊息發送、資料寫入),無法整批安全放行;(3) 遷移價值最低。若未來特定唯讀型排程任務有需求,可用 per-context allowlist 個案處理。

**4.2 真實 smoke(2026-08-19)**:forced codex 下 summarize_messages(結構化摘要格式正確)與 generate_outline(合法 JSON、layout 規則符合)皆通過,actual_model=gpt-5.6-luna,ai_route 的 context 欄位正確。
