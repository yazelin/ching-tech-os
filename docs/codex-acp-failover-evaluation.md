# Codex ACP 備援評估報告

> 評估日期：2026-08-04
> 狀態：Phase 0–5 完成；安全旁路、usage monitor、ACP 相容層與 Codex Provider 已受測，正式流量仍固定 Claude且尚無 caller 遷移
> 後續計畫：`openspec/changes/add-codex-acp-failover/`

## 1. 結論

在 `ching-tech-os` 加入「Claude OAuth 用量達 90% 時，將新請求切換至 Codex」技術上可行，但不能直接移植 `ctos-lite` 的實作。

目前判定為「有條件 No-Go」：可以開始測試先行的架構與 adapter 開發，但在完成 provider 契約、MCP 權限、真實唯讀 smoke、canary、監控與 kill switch 前，不得開啟正式流量的自動切換。

主要原因不是模型文字輸出，而是 `ching-tech-os` 的 `call_claude()` 已同時承擔工具安全、身份注入、MCP server 動態載入、部分結果保存、進度通知與多入口整合。任何 provider 替換都必須先證明這些行為沒有退化。

## 2. 評估範圍

初始評估完成以下唯讀檢查與測試；後續 Phase checkpoint 則依測試先行逐步加入預設不啟用的隔離元件：

- 查閱 `docs/module-index.md` 定位 AI、Bot、MCP 與部署模組。
- 還原 `ctos-lite` 的 Claude/Codex provider router、Claude 用量快取與 Codex ACP adapter。
- 盤點 `ching-tech-os` 所有直接使用 `call_claude()` 的入口與回應依賴。
- 檢查主系統 `.mcp.json` 的 stdio/HTTP MCP 組成與動態 extends MCP。
- 檢查 systemd 安裝腳本、PATH、執行使用者與 npm/uv 依賴管理方式。
- 檢查已安裝的 Codex CLI、`codex-acp` adapter 與 Python Generic ACP client。
- 對照目前官方 Codex App Server、認證與 rate-limit 能力文件。
- 執行主系統相關測試、完整後端測試與 `ctos-lite` provider 測試。

初始評估沒有執行真實 Claude/Codex 推論，也沒有用正式 MCP 寫入工具做端到端驗證。Phase 4 已補上真實 Codex 唯讀 smoke 與隔離 MCP fixture；正式 MCP 寫入、正式資料及正式流量仍未觸碰，並保留為後續啟用 gate。

## 3. `ctos-lite` 參考實作

### 3.1 路由流程

`ctos-lite/backend/src/ctos_lite/services/ai_factory.py` 的行為如下：

1. `AI_PROVIDER=claude`：固定 Claude。
2. `AI_PROVIDER=codex`：固定 Codex ACP。
3. `AI_PROVIDER=auto`：讀取記憶體內的 Claude OAuth 用量。
4. 用量 `>= USAGE_THRESHOLD`（預設 `0.90`）：新請求直接送 Codex。
5. 用量低於門檻：先送 Claude。
6. Claude 回傳失敗且 `AUTO_FALLBACK_TO_CODEX=true`：將整個請求重新送 Codex。
7. 每次呼叫結束後，以 background task 嘗試刷新 Claude 用量。

### 3.2 用量來源

`ctos-lite/backend/src/ctos_lite/services/claude_usage.py`：

- 讀取 `~/.claude/.credentials.json` 的 OAuth access token。
- 呼叫 Anthropic OAuth usage endpoint。
- 同時讀取 5 小時與 7 天 utilization，取兩者最大值。
- 相容 `0.90` 與 `90.0` 兩種百分比格式。
- 記憶體 cache TTL 為 60 秒。

### 3.3 Codex ACP adapter

`ctos-lite/backend/src/ctos_lite/services/codex_agent.py`：

- 每次請求啟動一個 `codex-acp` stdio subprocess。
- 透過 `claude-code-acp` 內的 Generic ACP client 溝通。
- 修正 Generic client 以 substring 去重 message chunk，可能吃掉重複文字的問題。
- 收集工具開始/完成事件、文字、token usage 與實際模型資訊。
- 設定 `INITIAL_AGENT_MODE=read-only`。
- 阻擋 terminal 與 file-write callback。
- 依工具白名單回答 ACP permission request。
- 將 Claude 的 haiku/sonnet/opus 工作負載角色映射到 Codex 模型角色。

### 3.4 成熟度判斷

這套功能由 `ctos-lite` commit `21a2973 Add Codex ACP provider fallback` 於 2026-08-04 一次加入，修改 12 個檔案。它可以作為可行性參考，但尚不能視為已經過長期正式流量驗證的成熟元件。

## 4. `ching-tech-os` 現行 AI 契約

核心函式位於 `backend/src/ching_tech_os/services/claude_agent.py`。除了推論之外，目前還提供：

- 每次呼叫建立並清理隔離的 session 工作目錄。
- 合併專案 `.mcp.json` 與 enabled extends 的 MCP server。
- 同時支援 stdio 與 HTTP MCP server。
- 依 Agent 權限只載入需要的 MCP server。
- 工具白名單與單回合工具呼叫次數上限。
- `ctos_user_id` framework 級身份注入，避免 LLM 偽造使用者。
- `extra_mcp_env` 注入群組、Agent、NAS 存取範圍等安全上下文。
- `on_tool_start` / `on_tool_end` callback，供 Telegram 顯示進度。
- timeout 時保留 partial text、已完成 tool calls 與 pending tool 摘要。
- token usage、tool timings 與 session cleanup。

直接或間接依賴這個契約的入口包含：

- Line Bot 個人與群組對話。
- Telegram Bot 對話與進度通知。
- 未綁定使用者 restricted mode。
- `/debug` 管理指令。
- Web AI Chat 與 Agent 測試。
- 排程 Agent。
- 簡報 outline JSON 與圖片生成。
- research-skill 的 WebSearch/WebFetch 與 fallback 統整。
- Intent Guard 無 API key 時的 CLI fallback。
- 對話摘要壓縮。

因此 provider 導入必須逐入口遷移，不能一次改寫 `call_claude()` 的語意。

## 5. 主要風險

### 5.1 跨 provider 重送造成重複副作用

`ctos-lite` 在 Claude 失敗時，會將完整 prompt 重新送 Codex。Claude 可能已經執行過 MCP 工具，只是在取得最終文字前 timeout 或失敗。若 Codex 再執行一次，可能重複：

- 建立或修改知識庫資料。
- 建立分享連結。
- 發送 Line/Telegram 訊息。
- 建立排程或背景工作。
- 上傳、移動或處理 NAS 檔案。
- 呼叫需付費的生圖或外部服務。

第一版禁止 provider 執行後的通用 fallback。provider 必須在請求開始前選定，同一請求內保持不變。只有經明確證明「尚未啟動工具及副作用」的錯誤類別，未來才可另案考慮安全重試。

### 5.2 HTTP MCP 不相容

目前 Python Generic ACP client 的 `new_session()` 只將設定轉成 `McpServerStdio`。主系統 `.mcp.json` 包含 HTTP GitHub MCP，直接套用 `ctos-lite` converter 會得到空 command，造成 server 無法啟動或靜默缺少工具。

Codex adapter 必須有 stdio 與 HTTP MCP 的契約測試，不能把 server config 當成同一種 dict 處理。

### 5.3 工具權限比對過寬

`ctos-lite` 的白名單允許用 normalized suffix 匹配工具名稱。不同 MCP server 若存在同名工具，可能把某 server 的授權套到另一個 server。

主系統必須以完整 canonical identity 比對：

- 內建工具使用明確名稱表。
- MCP 工具使用 server + tool 完整名稱。
- `Unknown` permission 只有在事件能唯一、可靠地對應已開始工具時才允許。
- 任何模糊或衝突一律 fail closed。

### 5.4 現行工具限制未被 Codex 實作

Codex adapter 尚未具備：

- `tool_call_limits`。
- nanobanana/codex-image 全域單回合限制。
- 完整 `ctos_user_id` 與 `extra_mcp_env` 行為。
- Telegram callbacks 與 callback error isolation。
- 與 Claude 相同的 tool timings。

這些不是可選優化，而是 provider 契約的一部分。

### 5.5 用量 cache 狀態不完整

`ctos-lite` cache 的初始 utilization 是 0，造成服務剛啟動或 credentials 不可用時，系統無法區分「確定為 0%」與「尚未取得資料」。此外還有：

- 沒有 refresh lock，多個 stale request 可能同時打 usage endpoint。
- 沒有 freshness、last error 或 consecutive failure 狀態。
- API 失敗時可能長期沿用過高或過低的 stale 值。
- 90% 附近沒有 hysteresis，可能反覆切換。
- 每次 AI request 都排 background refresh，不利於流量尖峰控制。

主系統需要明確的 `unknown / fresh / stale / error` 狀態、single-flight refresh、週期更新與切換遲滯。

### 5.6 部署與版本漂移

目前開發機環境：

- Codex CLI：`0.146.0`
- `@agentclientprotocol/codex-acp`：`1.1.9`

但 `codex-acp` 是全域 npm 安裝，不在 repo 的 package lock 中。正式機安裝腳本也沒有安裝或驗證它。systemd 服務還需確認：

- `ct` 使用者能找到正確 binary。
- service 的 Codex auth storage 路徑正確。
- headless 模式不會啟動 browser login。
- auth 過期時能回傳可監控的 readiness error。
- adapter 與 Codex CLI 版本相容。

正式導入必須 pin runtime 版本並提供 preflight，不可依賴部署機曾手動全域安裝的版本。

### 5.7 可觀測性不足

主系統目前 `ai_logs.model` 主要記錄 Agent 所選 Claude alias，沒有獨立 provider 欄位。若發生切換，需要至少記錄：

- requested provider/model role。
- selected provider。
- actual model。
- route reason。
- Claude usage ratio、資料時間與 freshness。
- Codex readiness/circuit 狀態。
- tool started/completed 狀態。
- provider error category。

第一階段可先將 metadata 放入 response、structured log 與 `parsed_response`，避免立即修改分區表 schema；是否新增正式 provider 欄位再依 canary 查詢需求決定。

### 5.8 subprocess 併發與清理

Codex ACP 每個請求啟動 Node/Codex subprocess。需要：

- provider semaphore 與 queue timeout。
- subprocess 啟動失敗分類。
- timeout cancel 後的強制 cleanup。
- bounded stderr tail，不能直接丟棄所有診斷。
- circuit breaker，避免 adapter 壞掉時每個使用者都重複啟動失敗行程。
- load test 驗證無 zombie process 與無限制記憶體成長。

## 6. 測試結果

### 6.1 `ching-tech-os`

- AI 相關測試：`87 passed in 3.44s`
- 完整後端：`1269 passed, 10 skipped, 1 warning in 115.02s`
- 完整 coverage：`85.50%`；`claude_agent.py` 為 `82%`。
- warning 為既有 `datetime.utcnow()` deprecation，與本功能無關。

### 6.2 `ctos-lite`

- provider 測試：`16 passed`
- 三個相關模組 coverage：60%
- `ai_factory.py`：94%
- `claude_usage.py`：84%
- `codex_agent.py`：51%

現有 `ctos-lite` 測試證明基本路由與成功路徑，但不足以保護主系統需要的事件、HTTP MCP、permission、timeout、cleanup、callback、tool limit 與身份安全分支。

### 6.3 Coverage gate 差異

- 2026-08-04 實測整體 coverage 為 85.50%。
- GitHub Actions `backend-tests.yml` 目前要求 85%。
- 本機 `test:backend:cov` 與 GitHub Actions 先統一為 85% 防退步 gate，`test:backend:cov:next` 以 86% 作為下一階預檢。
- 新增 `test:backend:cov:target` 保留 90% 目標；Codex auto mode 與 canary 必須等此 target 通過後才可啟用。

後續依新增測試的實際 coverage 逐整數調高 CI gate，最終在進入 canary 前達到 90%。router、usage state machine 與 permission guard 的重要分支仍必須逐條測試，不能只依賴 aggregate line coverage。

### 6.4 第一批 characterization tests 進度（2026-08-04）

- `test_claude_agent.py`：`11 passed`。
- `claude_agent.py` 完整測試 coverage：91%（基線 82%）。
- 新增共用 provider contract fixture，固定 request kwargs、response/partial-result、routing metadata 與 tool event 欄位。
- 新增保護：完整參數傳遞、history/system prompt、required MCP server、身份環境注入、`ctos_user_id` 不可由模型偽造、白名單拒絕、call-site limit、nanobanana/codex-image 全域上限，以及 callback error isolation。
- 新增 MCP merge/filter 保護：enabled extends、base precedence、stdio/HTTP 設定與敏感 env/header 不進 log。
- 新增 timeout/cancel 保護：partial text、已完成與執行中工具、token/timing、client close 與 workdir cleanup。
- 完成後的 `npm run ci:check`：`1275 passed, 10 skipped, 1 warning in 180.98s`，整體 coverage 85.70%（基線 85.50%）。

這批測試沒有修改正式 Claude 實作或任何 AI 路由。Phase 1 characterization gate 已完成；下一步可在 feature flag 預設關閉下，先建立向下相容的 provider-neutral response/protocol 與 `call_ai()` 旁路。

### 6.5 Provider-neutral 安全旁路 checkpoint（2026-08-04）

- 新增 `services/ai_provider.py`：`AIResponse`、`ToolCall`、callback 型別與 runtime-checkable `AIProvider` Protocol。
- `claude_agent.ClaudeResponse` 與 `ToolCall` 保留為共用型別的向下相容 alias。
- 新增 `services/ai_router.py::call_ai()`，完整接受既有 Claude kwargs 加上 `routing_context`，但目前永遠只呼叫 Claude 一次。
- `routing_context` 不傳入 prompt 或 Claude provider；provider exception 不做 retry。
- 尚未有任何既有 caller 遷移至 `call_ai()`，因此 Line、Telegram、Web、排程、簡報與 research 路徑仍直接使用純 Claude。
- 尚未新增 provider mode、usage monitor、Codex adapter 或 subprocess。
- 完成後 `npm run ci:check`：`1280 passed, 10 skipped, 1 warning in 180.28s`，整體 coverage 85.71%。
- 新增模組 coverage：`ai_provider.py` 97%、`ai_router.py` 100%；`claude_agent.py` 維持 91%。

此 checkpoint 只建立可測試的旁路接縫，不構成 Codex 備援可用或可進 canary 的證明。下一步應先加入安全設定驗證與 canary scope 判斷，預設仍為 forced Claude。

### 6.6 Provider mode 與 canary scope checkpoint（2026-08-04）

- 新增 `AI_PROVIDER_MODE` 驗證，只接受 `claude`、`codex`、`auto`；預設與非法值都安全使用 Claude，非法值會留下明確 error log。
- 新增 `AI_PROVIDER_CANARY_CONTEXTS` 與 `AI_PROVIDER_CANARY_AGENTS`，預設只包含 internal admin/test 與 `test-agent`。
- 新增 frozen `RoutingContext`，context/Agent 會正規化並以 exact match 判斷；空 context 直接拒絕。
- `routing_context` 不會傳入 Claude kwargs、prompt 或 model context。
- 因 Codex provider 與 usage monitor 尚未存在，所有 mode 目前仍只呼叫 Claude 一次：`claude` 為 `forced_claude`、`codex` 為 `codex_unready`、auto 非 canary 為 `canary_not_allowed`、auto canary 為 `usage_unknown`。
- focused：`28 passed`；`ai_router.py` 100%。
- 完整 `npm run ci:check`：`1292 passed, 10 skipped, 1 warning in 184.81s`，整體 coverage 85.75%。

此步仍未探測 Codex binary、讀取 Claude usage、啟動 background task 或遷移 caller。下一步應以 fake providers 補齊 sticky selection、pre-start fallback 與執行後禁止跨 provider retry 的 router tests。

### 6.7 Sticky Router 與 pre-start fallback checkpoint（2026-08-04）

- 新增 `ProviderDecision` 與 registry-based `ProviderRouter`；registry key 與 provider identity 不一致時會在建立階段拒絕。
- `AIProvider.is_ready()` 明確代表尚未建立 session 前的 readiness；只有 primary readiness 為 false、拋錯或 provider 未註冊時，才可改選決策中明確指定的 fallback。
- 進入 `provider.call()` 即視為執行邊界；無論回應為成功、`provider_started=false` 的失敗、`provider_started=true` 的失敗或直接拋出 exception，都不會跨 provider 重送。
- fallback 也 unavailable 時，router 在任何 provider call 前以 `ProviderUnavailableError` 結束，不會偷偷改走第三個 provider。
- 預設 registry 仍只有 Claude adapter；fake Codex 只存在測試，沒有安裝套件、探測 binary、建立 session 或 subprocess。
- focused router tests：`26 passed`，`ai_router.py` 100%。
- 完整 `npm run ci:check`：`1301 passed, 10 skipped, 1 warning in 179.21s`，整體 coverage 85.80%。

此 checkpoint 完成 Phase 2。關閉/預設 Claude 模式下，既有入口仍全部直呼 `call_claude()`，完整測試與既有 AI log 路徑無回歸。下一步進入 Phase 3 時，先只新增 usage payload 與 snapshot model 測試，不讀 credentials、不呼叫 HTTP，也不啟動 background task。

### 6.8 Claude Usage Monitor checkpoint（2026-08-04）

- 新增 `services/claude_usage.py`，將 5 小時與 7 天 utilization 正規化為 0–1 並取最大值；0–1、0–100、malformed、NaN/Inf 與 out-of-range 均有測試。
- `UsageSnapshot` 明確區分 unknown、fresh、stale、error，保存 fetched/attempt time、安全錯誤分類與連續失敗次數；短期失敗保留最後有效值，超過 max-stale 則 fail closed 回 Claude。
- refresh 使用 single-flight lock、60 秒 TTL、300 秒 max-stale 與週期 background task；Router 只讀記憶體，不在請求路徑等待 usage HTTP。
- 只有 `AI_PROVIDER_MODE=auto` 才在 FastAPI lifespan 啟動 monitor；初次刷新受短 timeout 保護，missing credentials 或外部服務失敗不阻止系統啟動。
- 401、429、5xx、network timeout、missing/invalid/unreadable credentials、invalid JSON、cache recovery 與 startup/cleanup 均有測試；log 不含 token、完整 response body 或原始 exception 內容。
- `UsageRoutingPolicy` 已鎖定 `>=90%` 切 Codex、`<85%` 切回 Claude、85%–90% 維持穩定 provider；unknown/error 回 Claude，max-stale 內 stale 維持前一狀態。
- focused：`67 passed`；`claude_usage.py` 98%、`ai_router.py` 100%。
- 完整 `npm run ci:check`：`1335 passed, 10 skipped, 1 warning in 180.15s`，整體 coverage 85.95%。

此 checkpoint 完成 Phase 3。尚未註冊 Codex provider、啟動 Codex subprocess 或遷移任何 caller；下一步只進行 ACP protocol compatibility spike 與唯讀 smoke。

### 6.9 Codex ACP compatibility spike checkpoint（2026-08-04）

結論為 **Go**，正式 provider 可建立在 pin 版 ACP compatibility layer，不需改走直接 App Server。

- npm lock 固定 `@agentclientprotocol/codex-acp` 1.1.9 與 `@openai/codex` 0.146.0；Python 使用既有 `claude-code-acp` 0.5.1 / ACP 0.8.0。
- 上游 adapter 1.1.9 會啟動 Codex App Server，並原生映射 stdio/HTTP MCP、tool events、usage、permission 與 cancel。官方 App Server 的 initialize/thread/turn lifecycle 因此由 adapter 承擔。
- Generic Python client 的已知缺口已集中修正在 `services/codex_acp.py`：合法重複 chunk 不再被 substring 去重、tool terminal update 只完成一次、PromptResponse token/model metadata 不遺失、stdio/HTTP schema 完整保留。
- HTTP MCP 的 URL/headers 已以 fake connection 驗證，並以本機 Streamable HTTP fixture 完成真實 session handshake。
- 真實 `on-request` permission event 已取得 canonical title `mcp.ctos-readonly-smoke.read_only_marker` 與 raw input 的 `server=ctos-readonly-smoke`、`tool=read_only_marker`；不需要 suffix 或 display-name 模糊比對。
- 真實 read-only smoke：純文字、`repeat repeat repeat`、單一無副作用 stdio MCP tool、HTTP MCP handshake、timeout/cancel 與 subprocess cleanup 全部通過（`3 passed in 28.73s`；canonical permission 強化後單項重跑 `1 passed in 16.95s`）。
- protocol 證據保存在 `backend/tests/fixtures/codex_acp_compatibility_1_1_9.json`；真實 smoke 預設 skip，只有 `RUN_CODEX_ACP_SMOKE=1` 才執行。
- 預設 CI：compatibility `11 passed, 3 skipped`；完整 `npm run ci:check`：`1348 passed, 13 skipped, 1 warning in 181.26s`，coverage 85.88%。

ACP 與直接 App Server 的差異：App Server 提供原生 initialize/thread/start/turn/start/turn/completed 事件與更完整控制；ACP 多一層翻譯，但已提供 ching-tech-os 需要的 client-facing session、MCP 與 permission 事件，且 ctos-lite 與本次真實 smoke 都已驗證。為降低自製 JSON-RPC client 的維護面積，Phase 5 繼續採 ACP；若未來 pin 升級破壞 canonical identity 或 HTTP MCP，則 fail closed 並回到 App Server spike，而不是模糊放行。

此 checkpoint 尚未把 Codex 註冊到 Router；Phase 5 將在相同 compatibility layer 上實作完整 provider contract、權限與資源治理。

### 6.10 Codex Provider checkpoint（2026-08-04）

Phase 5 已完成，Codex provider 已註冊至 `call_ai()` Router，但預設 `AI_PROVIDER_MODE=claude`，且所有正式入口仍直呼 `call_claude()`，所以現有流量不會啟動 Codex。

- 完整 provider kwargs 與 `AIResponse` 契約已對齊；保留 history、system prompt、partial text、completed tool calls、token、actual model、tool timings 與 callback isolation。
- 每請求使用隔離 session workdir；MCP 先依 canonical allowlist server 與 required set 取交集，再沿用主系統 merge/filter、stdio/HTTP transport 與 `CTOS_USER_ID`/Agent scope env injection。
- permission 同時要求 ACP title、raw server/tool 與 allowlist canonical identity 精確一致；短名稱、Unknown、同名不同 server、缺少 namespace、tool-call-id correlation 不一致皆拒絕。
- terminal、file-write 與 Codex native image fail closed；允許的圖片只能走既有 MCP，仍受 nanobanana/codex-image 全域及 call-site 次數上限。
- subprocess 設為 read-only、on-request approval、multi-agent disabled、`NO_BROWSER=1`；並有 concurrency semaphore、獨立 queue timeout、circuit breaker、安全錯誤分類、有界且遮罩的 stderr tail。
- timeout 會 cancel、保留 partial result，再 disconnect/terminate/kill 並清除 session 目錄；binary missing、auth、protocol、MCP startup、overload 與 callback failure 均有獨立測試。
- Phase 5 focused：`64 passed`；`codex_agent.py` 94%，核心安全分支不是只依賴 aggregate coverage。
- 完整後端：`1371 passed, 13 skipped, 1 warning in 114.60s`。
- `npm run ci:check`：前端 build 通過；`1371 passed, 13 skipped, 1 warning in 180.43s`，整體 coverage 85.98%。

這個 checkpoint 完成 adapter 本體，但不是正式啟用許可。Phase 6–9 的部署 preflight、service-user auth、可觀測性、caller canary、load test、kill-switch 演練與 24–72 小時觀察仍是 rollout gate。

## 7. 補完測試後的信心邊界

補完測試可以讓團隊有把握「陸續開發」，但不能把所有階段視為同一種完成度：

| 已完成條件 | 可以有把握進行的下一步 |
|---|---|
| Provider 契約、router、usage 與 permission 單元測試 | 開發 feature-flag 關閉的 router 與 Codex adapter |
| stdio/HTTP MCP integration tests、真實唯讀 ACP smoke | 實作完整 Provider 與部署 readiness |
| Provider、部署 preflight、可觀測性與 kill switch | 開啟內部 admin/test-agent canary |
| Line/Telegram/Web 入口測試、工具副作用防重送測試 | 開啟 allowlist 使用者或 Agent canary |
| systemd preflight、load test、監控與 kill switch | 小比例正式流量自動切換 |
| 24–72 小時 canary 無安全與重複操作問題 | 逐步擴大支援入口 |

換句話說，測試不是一次性保證，而是每一階段的進場門檻。只要嚴格遵守 gate，就能安全地開始開發；未通過 gate 的功能不能向下一階段擴張。

## 8. 建議架構原則

1. 保留 `call_claude()` 為純 Claude provider，不改變所有既有 caller 的語意。
2. 新增 provider-neutral `call_ai()`，只有明確遷移的入口才使用 router。
3. provider 在請求開始前選定，整個請求保持 sticky。
4. 第一版只做 usage-based routing，不做 Claude 執行失敗後跨 provider 重送。
5. 自動模式預設關閉；初始部署仍為固定 Claude。
6. 90% 切到 Codex，低於 85% 才切回 Claude。
7. usage refresh TTL 為 60 秒、max-stale 為 300 秒；超過 max-stale 時回到既有 Claude 行為並發出告警。
8. Codex readiness 在請求開始前失敗時回到 Claude，並記錄 critical route reason；Codex 開始執行後不得跨 provider 重送。
9. Codex 一旦已開始執行但失敗，不得再送 Claude。
10. 逐入口 migration：internal test → Web canary → Bot canary → 一般 Bot → 特殊 pipeline。

## 9. 啟用前必要 gate

- [ ] OpenSpec proposal、design、requirements 經確認。
- [ ] Provider 契約與 safety tests 先寫並確認會失敗。
- [ ] `npm run test:backend:cov:target` 通過，整體 coverage 達 90% 以上。
- [ ] `uv run pytest` 與 `npm run ci:check` 全數通過。
- [ ] stdio 與 HTTP MCP parity 測試通過。
- [ ] 真實 `codex-acp` 唯讀 smoke 通過。
- [ ] side-effect tool 不會因 provider failure 重送。
- [ ] systemd 使用者的 binary/auth/preflight 通過。
- [ ] provider concurrency、timeout、cleanup 與 circuit breaker 通過。
- [ ] provider、route reason、usage freshness 與 error category 可觀測。
- [ ] 固定 Claude kill switch 經實際演練。
- [ ] canary allowlist 與回復流程經實際演練。

## 10. 外部能力邊界

OpenAI 官方文件將 Codex App Server 定位為產品深度整合介面，提供認證、conversation、approval、streamed events、MCP 與 rate-limit 查詢。`codex-acp` 是外部 adapter，內部再將 ACP 轉成 Codex App Server 操作。

第一個 architecture spike 應驗證 ACP adapter 是否能完整承載主系統契約；若 HTTP MCP、permission identity 或事件資料不足，應比較直接使用官方 App Server stdio，而不是為了沿用 `ctos-lite` 而放寬安全契約。

參考：

- https://learn.chatgpt.com/docs/app-server
- https://learn.chatgpt.com/docs/auth
