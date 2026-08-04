## Context

目前所有核心 AI 工作都透過 `services/claude_agent.py::call_claude()`。這個函式不只是 provider client，也包含 session 隔離、MCP server 組裝、工具權限、使用者身份、進度 callback、token、partial result 與 cleanup。

`ctos-lite` 的 provider factory 證明 Codex ACP 基本呼叫可行，但它的 Python Generic ACP client 只建立 stdio MCP，permission identity 也比主系統需求寬鬆。主系統還包含 Line、Telegram、Web、restricted mode、排程、簡報、研究與摘要等不同輸出契約。

本設計採「新增旁路、逐入口遷移」而非「替換全域函式」。

## Goals / Non-Goals

**Goals:**

- Claude 用量達 90% 時，將尚未開始的新請求安全地路由至 Codex。
- 保持現有 Claude caller 與 `ClaudeResponse` 行為相容。
- Codex provider 遵守現有 MCP、權限、身份、callback、timeout 與 partial result 契約。
- 以測試、feature flag、canary、監控和 kill switch 控制導入風險。
- 每次請求可追查 provider、實際模型與路由原因。

**Non-Goals:**

- 不要求兩個模型輸出品質一對一相同。
- 不重放已經開始工具執行的請求。
- 不在第一階段遷移所有背景或結構化輸出 pipeline。
- 不同時執行雙 provider 做 agentic shadow comparison。
- 不在第一階段建立前端 provider 管理 UI。

## Decisions

### 1. 保留 `call_claude()`，新增 `call_ai()`

**選擇**：`call_claude()` 繼續代表純 Claude provider；新增 provider-neutral `call_ai()`，caller 必須明確遷移。

**理由**：

- 避免 feature code 一合併就改變至少 11 個模組的語意。
- 可讓未完成 parity 驗證的簡報、研究、排程等路徑繼續固定 Claude。
- 測試與 canary 可按 context/Agent 分批進行。
- kill switch 不需要回滾所有 caller import。

**不選**：直接將 `call_claude()` 內部改成 router。這會造成一次性 blast radius，且難以判斷哪個入口已完成 Codex parity。

### 2. Provider 契約保持 keyword-compatible

`call_ai()` 第一階段接受與 `call_claude()` 相同的參數，另加選填 routing context：

- `prompt`
- `model`
- `history`
- `system_prompt`
- `timeout`
- `tools`
- `tool_call_limits`
- `on_tool_start` / `on_tool_end`
- `required_mcp_servers`
- `ctos_user_id`
- `extra_mcp_env`
- `routing_context`（新，供 canary/觀測，不交給模型）

回應沿用相容 dataclass，新增有預設值的 metadata：

- `provider`
- `actual_model`
- `route_reason`
- `provider_started`
- `usage_snapshot`

既有 caller 不讀取新欄位時不受影響。

**Phase 2 checkpoint（2026-08-04）**：已新增共用 `AIResponse`/`AIProvider`，並以 alias 保留 `ClaudeResponse`/`ToolCall`。`call_ai()` 已建立但固定委派 Claude，`routing_context` 不傳入 provider。provider mode 已驗證 `claude`/`codex`/`auto`，並以 context/Agent exact-match 限制 canary；因 usage 與 Codex provider 尚未實作，三種 mode 都安全回到 Claude。`ProviderRouter` 只允許 readiness 尚未進入 `provider.call()` 前改選明確 fallback；一旦進入 call，不論回應標記、失敗或 exception 都不跨 provider 重送。fake provider tests 已覆蓋 readiness false/error/missing、fallback unavailable 與 sticky boundary；預設 registry 仍只有 Claude，尚無既有 caller 使用此旁路。

### 3. Provider 在執行前選定並保持 sticky

router 只在任何 provider subprocess、session 或 tool 尚未開始前做一次選擇。選擇完成後，該請求直到成功、timeout 或失敗都使用同一 provider。

第一版不提供 provider execution failure retry：

- Claude 已開始後失敗，不送 Codex。
- Codex 已開始後失敗，不送 Claude。
- readiness/preflight 在 provider 尚未開始前失敗，才可依設定選擇替代 provider。

這個規則比可用性優先，但能避免重複副作用。

### 4. 路由狀態機使用 90% / 85% hysteresis

狀態：

- `forced_claude`
- `forced_codex`
- `auto_claude`
- `auto_codex`
- `usage_unknown`
- `usage_stale`
- `codex_unready`
- `circuit_open`

自動模式規則：

1. 預設設定是 forced Claude；只有明確開啟 auto 才讀 usage 決策。
2. fresh utilization `>= 0.90`：切到 Codex。
3. 已在 Codex 狀態時，fresh utilization 必須 `< 0.85` 才切回 Claude。
4. fresh utilization 位於 85%–90%：維持上一個穩定 provider。
5. 啟動時 usage unknown：使用 Claude 並告警，保持既有行為。
6. 短時間 stale：在設定的 max-stale 內維持上一個穩定 provider。
7. 超過 max-stale：使用 Claude 並告警。
8. Codex preflight unready 且尚未開始請求：依 `codex_unavailable_policy`，預設回到 Claude 並記錄 critical route reason。

所有 threshold 與 TTL 都要做範圍驗證，非法設定不得靜默進 auto。

Phase 0 固定的初始營運預設如下：

- usage refresh TTL：60 秒。
- usage max-stale：300 秒。
- Codex preflight unavailable：回到 Claude，並記錄 critical route reason。
- 首批 canary：僅 internal admin/test-agent，且只允許純文字與唯讀工具。
- 首批 canary 禁止：建立、修改或刪除知識庫/圖書館資料，檔案寫入、移動或刪除，外部訊息發送，ERP 寫入，shell/terminal，以及圖片生成或編輯。

這些值先作為可由環境設定覆寫的安全預設；任何覆寫都必須通過設定範圍驗證。正式擴大流量前可依 canary 數據另提調整，但不得在未留紀錄下改變。

### 5. Usage monitor 使用週期刷新與 single-flight

usage monitor 由 FastAPI lifespan 啟動與關閉：

- 啟動時以短 timeout 嘗試一次 refresh，不阻止服務啟動。
- 背景 task 依固定 interval 更新。
- stale request 可觸發 single-flight refresh，但同時間只有一個 HTTP request。
- cache 同時保存 utilization、5h、7d、fetched_at、last_attempt_at、last_error 與 consecutive_failures。
- credentials、token、完整 response body 不得進 log。

router 只讀記憶體 snapshot，不在使用者 request critical path 等待遠端 usage API。

**Phase 3 checkpoint（2026-08-04）**：已完成 `UsageSnapshot` 的 unknown/fresh/stale/error 狀態、5h/7d payload 正規化、single-flight refresh、TTL/max-stale、週期 task 與 90%/85% hysteresis。只有 `AI_PROVIDER_MODE=auto` 會在 FastAPI lifespan 啟動 monitor；預設 Claude 不讀 credentials。HTTP/credentials 的錯誤只保留安全 category，不記 token、完整 response body 或原始 network exception。Codex provider 尚未註冊，因此 auto 決策即使選到 Codex也只會在 pre-start readiness 階段安全回到 Claude。

### 6. Codex adapter 先走 ACP compatibility spike

第一候選為 pin 版 `@agentclientprotocol/codex-acp` stdio adapter，因為 `ctos-lite` 已驗證基本可行，且 adapter 會轉接 Codex App Server。

spike 必須先證明：

- repeated text delta 不遺失。
- tool start/progress/end 可可靠去重。
- stdio 與 HTTP MCP 都能建立。
- permission request 能取得完整、唯一的 tool identity。
- token、actual model、partial text 與 cancel 可取得。
- subprocess 可完全清理。

如果完整 tool identity、HTTP MCP 或事件契約無法安全實作，停止 ACP adapter 擴張，改比較直接使用官方 `codex app-server` stdio。不能以模糊 permission 或停用 HTTP 工具作為正式解法。

### 7. MCP 組裝沿用主系統安全上下文

Codex provider 必須使用與 Claude 相同的 session workdir、enabled extends、required server filtering 與環境注入來源。

不得另外掃描全域 MCP 或讓 Codex 自行載入未經過主系統過濾的工具。

HTTP MCP 必須保留 URL 與 headers；stdio MCP 必須保留 command、args 與 env。敏感 header/env 不得寫入一般 log。

### 8. Permission 採 canonical identity，模糊時拒絕

允許判斷順序：

1. 從 ACP 結構化 metadata 取得 server/tool canonical identity。
2. 若 adapter 只提供 display title，必須透過實際 event fixture 建立無歧義 mapping。
3. `Unknown` 只有在同一時間恰有一個 active tool，且 active tool 已有 canonical identity 時才可歸因。
4. 同名、多個 active tool、缺少 namespace 或格式未知全部拒絕。

terminal、shell、file-write 與 Codex native image generation 預設拒絕；圖片需求必須使用主系統允許的 MCP 工具與既有檔案傳送路徑。

tool-call limit 在 permission 核准前計數，provider 不能繞過 nanobanana/codex-image 全域上限。

### 9. Codex subprocess 受 concurrency 與 circuit breaker 控制

- 使用可設定 semaphore 限制同時 Codex session。
- queue wait 有獨立 timeout，不消耗完整 AI timeout。
- adapter 啟動、auth、protocol、MCP startup、provider overload 分類記錄。
- 連續 readiness/啟動失敗達門檻後開啟短時間 circuit。
- circuit open 時不再重複 spawn；provider 尚未開始，因此可依 preflight policy 選 Claude 或受控失敗。
- stderr 僅保存 bounded tail，並清理 credential-like 字串。

### 10. Adapter 與 Codex runtime 必須 pin

不依賴部署機手動全域 npm 安裝：

- 將選定 adapter 以 exact version 納入 repo lock，或提供同等可重現的安裝 artifact。
- 明確設定實際執行的 binary path。
- preflight 驗證 binary、version、auth、headless 環境與最小 session handshake。
- systemd 使用 `ct` 使用者的明確 Codex auth storage，不讀 root credentials。
- `NO_BROWSER=1`，服務中不得啟動互動 login。

### 11. 第一階段不新增 `ai_logs` provider 欄位

為降低分區表 migration 風險，先將 routing metadata 寫入：

- structured service log。
- response metadata。
- 現有 `parsed_response` JSON。

`model` 欄位是否改記 actual model，需先確認既有 AI 管理統計與前端篩選不會退化。若 canary 需要 provider index/query，再提出獨立 migration。

### 12. 按入口逐步遷移

建議順序：

1. internal admin/test-agent，限定無副作用工具。
2. Web Chat canary Agent。
3. allowlist Line/Telegram 使用者或群組。
4. 一般 Line/Telegram 對話。
5. restricted mode。
6. 簡報、research、scheduler、summary 等特殊 pipeline，逐一通過格式或工具 parity 後才遷移。

任何階段都能把 router mode 改回 forced Claude。未列入 allowlist 的 caller 保持呼叫 `call_claude()`。

## Test Strategy

### Characterization tests

在重構共用型別或 helper 前，先鎖住現有 Claude：

- 完整參數傳遞。
- MCP server filtering 與 env injection。
- permission/tool-call limit。
- callback success/failure isolation。
- token/tool timings。
- timeout partial result。
- cleanup。

### Contract tests

用同一組 provider contract tests 驗證 Claude 與 Codex fake client：

- success、empty response、provider exception、timeout、cancel。
- repeated chunks。
- tool progress 去重。
- partial text/tool output。
- actual model/token metadata。

### Router/usage tests

- forced/auto/provider allowlist。
- 0%、89.9%、90%、90.1%、85%、84.9%。
- unknown/fresh/stale/error。
- 1.0 與 100.0 格式。
- malformed/out-of-range payload。
- 401、429、5xx、timeout、missing credentials。
- concurrent refresh single-flight。
- circuit open/half-open/close。
- provider sticky 與 no cross-provider replay。

### Security tests

- stdio/HTTP MCP parity。
- required server 與 disabled extends。
- canonical identity、同名工具、Unknown、concurrent tools。
- terminal/file-write/native image deny。
- `ctos_user_id` 與 Agent scope 無法由 LLM 覆寫。
- tool-call limit across aliases/events。

### Integration and smoke tests

- admin test-agent、Web、Line、Telegram、restricted mode。
- 圖片/語音 marker 與工具結果解析。
- 簡報 JSON、research WebSearch/WebFetch、scheduler side effect 等特殊契約。
- 真實 ACP 只使用唯讀 MCP fixture。
- systemd service user preflight。
- bounded concurrency、timeout、zombie process 與 memory soak。

## Rollback Strategy

1. 將 router mode 設為 forced Claude。
2. 清空 canary allowlist。
3. 停止 usage monitor 與 Codex readiness task，不影響純 Claude caller。
4. 若 adapter 造成 subprocess 問題，停用 Codex provider，不需回滾資料庫。
5. 保留 routing/error logs 供事後分析。

## Risks / Trade-offs

**[用量 endpoint 變動]** → usage monitor 狀態轉 error，不得把缺值當 0；超過 max stale 後回到 Claude 並告警。

**[Codex 與 Claude 工具選擇不同]** → 不宣稱等價；以入口 contract 與 canary 驗證，不一次遷移特殊 pipeline。

**[Codex adapter 事件格式升級]** → pin exact version、保存 protocol fixtures、preflight handshake；升版視為相容性變更。

**[Claude 已接近額度但 Codex 不可用]** → 預設選擇維持 Claude 可用性並發 critical alert；營運方可改為 fail closed。此政策必須在正式啟用前確認。

**[90% 附近切換震盪]** → 使用 90%/85% hysteresis 和 stable provider state。

**[測試全綠仍與真實 adapter 不同]** → 真實唯讀 smoke 與 canary 是獨立 gate，不能用 mock test 取代。

## Open Questions Before Production Auto Mode

- 需要將 provider 正式新增到 `ai_logs` schema，還是 `parsed_response` 足夠？
- ACP compatibility spike 是否能提供可靠的 HTTP MCP 與 canonical tool identity？
- canary 完成後，threshold/TTL 是否需要由環境設定遷移到資料庫設定管理？
