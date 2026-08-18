## ADDED Requirements

### Requirement: 現有 Claude 呼叫保持向下相容

系統 MUST 保留純 Claude provider 的 `call_claude()` 行為。新增多 provider 路由時，未明確遷移至 `call_ai()` 的 caller MUST 繼續固定使用 Claude，且參數、回應、工具權限、partial result 與 cleanup 行為不得改變。

#### Scenario: Feature flag 關閉

- **GIVEN** AI provider auto mode 未啟用
- **WHEN** 任一既有 caller 呼叫 `call_claude()`
- **THEN** 系統只使用 Claude provider
- **AND** 不啟動 Codex subprocess

#### Scenario: 未遷移的特殊 pipeline

- **GIVEN** 簡報、研究或排程 pipeline 尚未完成 Codex parity 驗證
- **WHEN** pipeline 執行 AI 呼叫
- **THEN** pipeline MUST 維持使用 `call_claude()`

### Requirement: Provider 在請求執行前選定並保持不變

系統 MUST 在建立 provider session 或執行任何工具之前選定 provider。選定後，同一請求 MUST 保持使用該 provider，直到成功、timeout、取消或失敗。

#### Scenario: Claude 執行後失敗

- **GIVEN** router 已選定 Claude
- **AND** Claude session 已開始執行
- **WHEN** Claude timeout 或回傳失敗
- **THEN** 系統 MUST 回傳 Claude 的失敗與 partial result
- **AND** MUST NOT 將相同請求重送 Codex

#### Scenario: Codex 執行後失敗

- **GIVEN** router 已選定 Codex
- **AND** Codex session 已開始執行
- **WHEN** Codex timeout 或回傳失敗
- **THEN** 系統 MUST 回傳 Codex 的失敗與 partial result
- **AND** MUST NOT 將相同請求重送 Claude

#### Scenario: Codex preflight 在執行前失敗

- **GIVEN** auto router 原本要選 Codex
- **AND** Codex readiness 在 session 建立前失敗
- **WHEN** unavailable policy 設為 Claude
- **THEN** 系統 MAY 在任何工具尚未開始前選擇 Claude
- **AND** MUST 記錄 `codex_unready` route reason

### Requirement: Claude 用量達 90% 時選擇 Codex

在 auto mode 與 canary scope 內，系統 SHALL 以 Claude 5 小時與 7 天 utilization 的最高值作為 routing utilization。fresh utilization 大於或等於 90% 時，尚未開始的新請求 SHALL 選擇 Codex。

#### Scenario: 用量低於切入門檻

- **GIVEN** fresh routing utilization 為 89.9%
- **AND** 上一個穩定 provider 為 Claude
- **WHEN** 新請求進入 router
- **THEN** 系統選擇 Claude

#### Scenario: 用量等於切入門檻

- **GIVEN** fresh routing utilization 為 90.0%
- **WHEN** 新請求進入 router
- **THEN** 系統選擇 Codex

#### Scenario: 取 5 小時與 7 天最大值

- **GIVEN** 5 小時 utilization 為 40%
- **AND** 7 天 utilization 為 92%
- **WHEN** usage monitor 建立 snapshot
- **THEN** routing utilization MUST 為 92%

### Requirement: Provider 切換具有 hysteresis

系統 SHALL 使用不同的切入與切回門檻避免 90% 附近反覆切換。預設切入 Codex 門檻為 90%，切回 Claude 門檻為 85%。

#### Scenario: 已在 Codex 且用量位於遲滯區間

- **GIVEN** 上一個穩定 provider 為 Codex
- **AND** fresh utilization 為 87%
- **WHEN** 新請求進入 router
- **THEN** 系統維持 Codex

#### Scenario: 用量低於切回門檻

- **GIVEN** 上一個穩定 provider 為 Codex
- **AND** fresh utilization 為 84.9%
- **WHEN** 新請求進入 router
- **THEN** 系統切回 Claude

### Requirement: Usage 狀態不得將未知值當成 0

usage monitor MUST 區分 unknown、fresh、stale 與 error。系統 MUST NOT 因缺少 credentials、API 失敗或尚未完成首次 refresh 而將 utilization 記為已知的 0%。

#### Scenario: 服務啟動時尚無 snapshot

- **GIVEN** usage monitor 尚未完成首次 refresh
- **WHEN** auto router 收到新請求
- **THEN** 系統使用 Claude 以保持現行行為
- **AND** 記錄 `usage_unknown`

#### Scenario: 短時間 stale

- **GIVEN** snapshot 已超過 refresh TTL
- **AND** 尚未超過 max-stale
- **WHEN** 新請求進入 router
- **THEN** 系統維持上一個穩定 provider
- **AND** snapshot MUST 標記為 stale

#### Scenario: 超過 max-stale

- **GIVEN** snapshot 已超過 max-stale
- **WHEN** 新請求進入 router
- **THEN** 系統使用 Claude
- **AND** 發出可觀測告警

#### Scenario: Usage payload 格式錯誤

- **WHEN** usage endpoint 回傳缺少欄位、非數字或超出合法範圍的 utilization
- **THEN** monitor MUST 將該次 refresh 標記為 error
- **AND** MUST NOT 覆蓋最後一筆有效 snapshot

### Requirement: Usage refresh 為 single-flight 且不阻塞使用者請求

usage monitor SHALL 使用背景週期刷新與 single-flight lock。初始 refresh TTL SHALL 為 60 秒，max-stale SHALL 為 300 秒。router 讀取記憶體 snapshot 時 MUST NOT 等待遠端 usage API。

#### Scenario: 多個請求同時發現 cache stale

- **GIVEN** cache 已 stale
- **WHEN** 多個 request 同時觸發 refresh
- **THEN** 系統最多只執行一個遠端 usage request

#### Scenario: Usage endpoint timeout

- **WHEN** usage endpoint 超過設定 timeout
- **THEN** 使用者 AI request MUST 依現有 snapshot 繼續路由
- **AND** monitor MUST 記錄 refresh error 與 failure count

#### Scenario: Snapshot 超過初始 max-stale

- **GIVEN** 最後有效 snapshot 已超過 300 秒
- **WHEN** 新請求進入 router
- **THEN** 系統使用 Claude
- **AND** 發出可觀測告警

### Requirement: Auto mode 預設關閉並支援 canary

系統 SHALL 預設固定使用 Claude。只有明確啟用 auto mode 且 routing context 符合 canary allowlist 的請求，才可依 usage 切至 Codex。第一批 canary SHALL 僅限 internal admin/test-agent，且只允許純文字與唯讀工具。

#### Scenario: Auto mode 未啟用

- **GIVEN** provider mode 為 Claude
- **WHEN** utilization 超過 90%
- **THEN** 系統仍選擇 Claude

#### Scenario: 不在 canary scope

- **GIVEN** provider mode 為 auto
- **AND** utilization 超過 90%
- **AND** request context 不在 canary allowlist
- **WHEN** 新請求進入 router
- **THEN** 系統選擇 Claude

#### Scenario: Kill switch

- **GIVEN** auto mode 已有 canary 流量
- **WHEN** operator 將 provider mode 改為 Claude 並重新載入生效設定
- **THEN** 所有後續新請求 MUST 停止選擇 Codex

#### Scenario: 首批 canary 要求副作用工具

- **GIVEN** request context 屬於第一批 internal admin/test-agent canary
- **WHEN** 請求要求資料建立、修改或刪除、檔案寫入、外部訊息發送、ERP 寫入、shell/terminal 或圖片生成編輯
- **THEN** 系統 MUST NOT 將該副作用工具暴露給 Codex

### Requirement: Codex provider 必須符合共用回應契約

Codex provider SHALL 回傳與現有 Claude caller 相容的成功狀態、文字、錯誤、tool calls、input/output tokens 與 tool timings，並附加 provider、actual model、route reason 與 provider started metadata。

#### Scenario: Codex 正常完成

- **WHEN** Codex 完成文字與工具呼叫
- **THEN** response MUST 包含完整文字與去重後的 tool calls
- **AND** provider MUST 為 Codex
- **AND** 可取得時 MUST 記錄 actual model 與 token usage

#### Scenario: 重複文字 chunk

- **WHEN** Codex 依序送出內容相同的兩個合法 delta
- **THEN** 系統 MUST 保留兩個 delta 的順序與內容
- **AND** MUST NOT 以 substring 去重而遺失文字

#### Scenario: Codex timeout

- **WHEN** Codex 超過 request timeout
- **THEN** 系統 MUST cancel session 並清理 subprocess
- **AND** response MUST 保留已收到的 partial text 與 completed tool calls

### Requirement: Codex provider 支援 stdio 與 HTTP MCP

Codex provider MUST 保留主系統過濾後的 MCP server 類型與設定。stdio server MUST 保留 command、args、env；HTTP server MUST 保留 URL 與 headers。

#### Scenario: 載入 stdio MCP

- **WHEN** required MCP 包含 stdio server
- **THEN** Codex session MUST 以原 command、args 與 env 建立該 server

#### Scenario: 載入 HTTP MCP

- **WHEN** required MCP 包含 HTTP server
- **THEN** Codex session MUST 以原 URL 與 headers 建立該 server
- **AND** MUST NOT 將它轉成空 command 的 stdio server

#### Scenario: MCP 未在 required set

- **WHEN** MCP server 不在該 Agent 的 required set
- **THEN** Codex session MUST NOT 載入該 server

### Requirement: Codex 工具 permission 必須 fail closed

Codex provider MUST 使用 canonical server/tool identity 與完整 allowlist 比對。模糊、衝突、Unknown 或無法唯一歸因的 permission request MUST 被拒絕。

#### Scenario: 完整名稱在 allowlist

- **GIVEN** permission request 可辨識為 `mcp__ching-tech-os__search_knowledge`
- **AND** 完整名稱在 allowlist
- **WHEN** Codex 請求使用工具
- **THEN** permission guard 可核准該工具

#### Scenario: 不同 server 的同名工具

- **GIVEN** allowlist 只允許 server A 的 `search`
- **WHEN** server B 的 `search` 請求 permission
- **THEN** permission guard MUST 拒絕

#### Scenario: Unknown 且多個工具執行中

- **GIVEN** permission title 為 Unknown
- **AND** 同時有多個 active tools
- **WHEN** permission guard 無法唯一歸因
- **THEN** permission guard MUST 拒絕

#### Scenario: Terminal 或 file-write

- **WHEN** Codex 請求 terminal、shell command 或直接 file-write
- **THEN** provider MUST 拒絕

### Requirement: Codex 必須遵守身份注入與工具次數上限

Codex provider MUST 使用 framework 控制的 `ctos_user_id` 與 Agent scope 環境變數，且 MUST 執行與 Claude 相同的單回合工具呼叫限制。

#### Scenario: LLM 偽造使用者身份

- **GIVEN** framework 注入 `ctos_user_id=123`
- **WHEN** 模型工具輸入嘗試指定其他使用者 ID
- **THEN** MCP server 接收到的有效身份 MUST 為 framework 指定值

#### Scenario: 工具達到上限

- **GIVEN** 某工具單回合上限為 1
- **AND** 該工具已核准並執行一次
- **WHEN** Codex 再次請求相同 canonical tool
- **THEN** permission guard MUST 拒絕第二次呼叫

### Requirement: Codex subprocess 受到資源與錯誤控制

系統 SHALL 限制同時執行的 Codex sessions，為排隊設定 timeout，並在連續啟動或 readiness 失敗時開啟 circuit breaker。

#### Scenario: 達到 concurrency 上限

- **GIVEN** 所有 Codex session slots 已使用
- **WHEN** 新請求等待超過 queue timeout
- **THEN** provider MUST 回傳可分類的 queue timeout
- **AND** MUST NOT 無限制建立新 subprocess

#### Scenario: Circuit open

- **GIVEN** Codex 連續失敗達 circuit threshold
- **WHEN** 新請求原本要選 Codex
- **THEN** 系統 MUST NOT 啟動新的 Codex subprocess
- **AND** router MUST 依 unavailable policy 處理

#### Scenario: Process cleanup

- **WHEN** Codex 成功、失敗、timeout 或被取消
- **THEN** stdin/stdout transport 與 subprocess MUST 被關閉
- **AND** session workdir MUST 被清理

### Requirement: Provider 路由必須可觀測且不洩漏秘密

每個經過 `call_ai()` 的請求 SHALL 記錄 selected provider、actual model、route reason、usage freshness、latency、error category 與 tool execution state。記錄 MUST NOT 包含 OAuth token、Codex auth、MCP secret headers 或敏感 env values。

#### Scenario: 自動切至 Codex

- **WHEN** utilization 達 90% 且請求選擇 Codex
- **THEN** structured log 與 AI log metadata MUST 能辨識 provider、actual model 與 usage threshold route reason

#### Scenario: Usage refresh 失敗

- **WHEN** usage endpoint 回傳含敏感內容的錯誤
- **THEN** log MUST 只保存分類後的 error code/message
- **AND** MUST NOT 保存 Authorization header、access token 或完整 response body

### Requirement: 正式啟用前必須通過分階段 gate

系統 SHALL 在 mock/unit tests、真實唯讀 smoke、入口 canary、部署/load 測試與 rollback 演練完成後，才可逐步擴大 auto mode scope。

#### Scenario: 僅單元測試完成

- **GIVEN** provider/router 單元測試已通過
- **AND** 真實 ACP smoke 尚未通過
- **WHEN** 準備部署
- **THEN** Codex auto routing MUST 保持關閉

#### Scenario: Canary 發現重複副作用

- **WHEN** canary 發現任何工具操作被跨 provider 重複執行
- **THEN** rollout MUST 立即停止
- **AND** kill switch MUST 將後續請求切回 Claude

#### Scenario: Canary gate 全數通過

- **GIVEN** 完整測試、唯讀 smoke、systemd preflight、load test、監控與 rollback 演練皆通過
- **AND** canary 觀察期無安全退化
- **WHEN** operator 核准下一 rollout stage
- **THEN** 系統 MAY 擴大明確指定的 context scope
