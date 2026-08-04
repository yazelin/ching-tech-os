## Why

`ching-tech-os` 的主要 AI 推論目前依賴 Claude Code OAuth 用量。當 5 小時或 7 天用量接近上限時，所有 Line、Telegram、Web 與背景 Agent 功能都可能同時失去服務能力。

姐妹專案 `ctos-lite` 已加入 Codex ACP provider，可在 Claude 用量達 90% 時將新請求切至 Codex。但主系統的 AI 呼叫同時承擔動態 MCP、工具權限、身份注入、進度通知、partial result 與多入口工作流程，直接移植會有重複副作用、HTTP MCP 遺失及權限退化風險。

需要先建立 provider-neutral 契約與測試，再以 feature flag、canary 與 kill switch 逐入口導入 Codex 備援。

完整風險與測試基線見 `docs/codex-acp-failover-evaluation.md`。

## What Changes

### 1. Provider-neutral AI 契約

- 保留現有 `call_claude()` 為純 Claude provider。
- 新增 `call_ai()` router，只有明確遷移的 caller 才使用多 provider 路由。
- 統一回應 metadata：provider、實際模型、route reason、token、tool calls、tool timings 與 partial result。
- 以 characterization tests 保護現有 Claude 行為。

### 2. Claude 用量狀態服務

- 讀取 Claude OAuth 的 5 小時與 7 天 utilization，取最高值。
- 使用週期背景刷新與 single-flight lock，不在每個 request 無限制建立 refresh task。
- 區分 unknown、fresh、stale、error 狀態。
- 預設 90% 切到 Codex，低於 85% 才切回 Claude。
- usage 過舊或無法取得時保留既有 Claude 行為並告警。

### 3. Codex provider adapter

- 透過經驗證且 pin 版的 `codex-acp` stdio adapter 呼叫 Codex。
- 若 architecture spike 證明 ACP 無法滿足完整契約，改評估直接使用官方 Codex App Server stdio。
- 支援 stdio/HTTP MCP、完整工具 identity、tool-call limit、身份環境變數、callbacks、partial result、timeout 與 cleanup。
- 限制 terminal/file-write，任何模糊 permission fail closed。
- 加入 subprocess concurrency limit、queue timeout、readiness 與 circuit breaker。

### 4. 安全路由規則

- provider 在請求開始前選定，同一請求中不得切換。
- 第一版不實作 Claude 執行失敗後的跨 provider retry。
- Codex preflight 尚未開始執行就失敗時，依明確設定選擇 Claude 或受控失敗。
- Codex 已開始執行後失敗，不得將相同請求重送 Claude。
- 自動模式預設關閉，提供固定 Claude kill switch 與 context/Agent canary allowlist。

### 5. 可觀測性與逐步導入

- 記錄 selected provider、actual model、route reason、usage freshness、error category 與 tool execution state。
- 先使用 structured log 與 `ai_logs.parsed_response`，第一階段不要求資料庫 schema 變更。
- 依 internal test、Web canary、Bot canary、一般 Bot、特殊 pipeline 的順序遷移。

## Capabilities

### New Capabilities

- `ai-provider-routing`: 依 Claude 用量、readiness、feature flag 與 canary scope 安全選擇 Claude 或 Codex provider。
- `codex-acp-provider`: 符合主系統安全與事件契約的 Codex provider adapter。
- `claude-usage-monitor`: 具 freshness、single-flight、hysteresis 與錯誤狀態的 Claude OAuth 用量監控。

### Modified Capabilities

- `ai-management`: AI log 可辨識實際 provider、模型與路由原因。
- `line-bot`: 經 canary 驗證後，可選擇使用 provider router，現有訊息、圖片、語音與工具結果行為不變。
- `bot-platform`: Telegram/restricted mode 經獨立驗證後逐步支援 provider router。

## Impact

- **新增後端模組（預估）**：
  - provider-neutral contract/router
  - Claude usage monitor
  - Codex adapter
- **可能修改**：
  - `config.py`、`main.py` lifespan
  - `claude_agent.py`（只抽共用型別或補 metadata，不改既有純 Claude 語意）
  - 明確納入 canary 的 AI caller
  - AI log 組裝與部署 preflight
  - root npm runtime dependency/lock
- **測試**：新增 provider contract、usage state machine、permission、MCP parity、入口 integration、deployment/load 測試。
- **資料庫**：第一階段不新增欄位；若 canary 後需要高效率 provider 查詢，再另提 Alembic migration。
- **部署**：需要 pin Codex adapter、確認 systemd 使用者 auth storage，並新增 preflight。

## Constraints

- 不得降低現有工具白名單、身份注入或單回合工具限制。
- 不得將已開始執行的請求跨 provider 重送。
- 不得一次切換所有 `call_claude()` caller。
- 自動模式預設關閉，沒有 kill switch 不得進 canary。
- 未通過 stdio/HTTP MCP 與真實唯讀 smoke，不得承接正式工具請求。
- 所有新程式碼及整體測試 coverage 必須符合 90% gate；安全分支需明確測試。

## Out of Scope

- 同一對話中的跨 provider 原生 session 接續。
- provider 執行失敗後自動重放有副作用的請求。
- 以 shadow mode 同時執行 Claude 與 Codex agentic tools。
- 第一階段新增 AI provider 管理前端。
- 第一階段修改分區 `ai_logs` schema。
- 宣稱 Claude 與 Codex 的模型品質、工具選擇或生成格式完全等價。
