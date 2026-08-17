## 0. 決策與基線 Gate

- [x] 0.1 確認並記錄初始路由政策：切入 90%、切回 85%、refresh TTL 60 秒、max-stale 300 秒、Codex unavailable 時回到 Claude
- [x] 0.2 固定第一批 canary 為 internal admin/test-agent，僅允許純文字與唯讀工具，並記錄禁止的副作用能力
- [x] 0.3 對齊本機與 GitHub Actions 的現況防退步 gate 為 85%，新增 86% next 與 canary 前必達的 90% target gate
- [x] 0.4 保存實作前基線：1269 passed、10 skipped、coverage 85.50%、`claude_agent.py` 82%，並盤點目前 AI 入口與 MCP server
- [x] 0.5 確認本 change 的 proposal、design、spec 與 `docs/codex-acp-failover-evaluation.md`

## 1. 測試先行：鎖住現有 Claude 契約

- [x] 1.1 新增 provider contract test fixtures，定義 request kwargs、response metadata、tool event 與 partial result 的共同契約
- [x] 1.2 擴充 Claude characterization tests：所有現行參數、history/system prompt、tool callbacks 與 callback error isolation
- [x] 1.3 擴充 MCP tests：required server filtering、stdio/HTTP config、enabled extends 與敏感 env/header 不進 log
- [x] 1.4 擴充 permission tests：完整白名單、tool-call limit、nanobanana/codex-image 全域限制、身份注入不可偽造
- [x] 1.5 擴充 timeout/cancel tests：partial text、completed/pending tool calls、token/timings 與 workdir/client cleanup
- [x] 1.6 執行完整後端測試並確認 characterization tests 未改變現行行為（1275 passed、10 skipped、coverage 85.70%）

## 2. Provider-neutral 契約與旁路 Router

- [x] 2.1 新增相容的 provider-neutral response/protocol；`ClaudeResponse` 保留向下相容 alias 或介面
- [x] 2.2 新增 `call_ai()` 旁路，保留 `call_claude()` 為純 Claude，尚未遷移的 caller 不變
- [x] 2.3 新增 `routing_context` 與 context/Agent canary allowlist，不將 routing metadata 傳入模型
- [x] 2.4 新增 forced Claude、forced Codex、auto mode 設定驗證；預設 forced Claude（Codex 尚未接入時安全回到 Claude）
- [x] 2.5 先撰寫並通過 router tests：provider sticky、pre-start fallback、執行後禁止跨 provider retry
- [x] 2.6 驗證關閉 feature flag 時，所有既有 AI tests 與 log 行為完全相同

## 3. Claude Usage Monitor（TDD）

- [x] 3.1 先新增 usage payload tests：5h/7d max、0–1/0–100 格式、malformed、out-of-range
- [x] 3.2 新增 unknown/fresh/stale/error snapshot model，保存 fetched time、last error 與 failure count
- [x] 3.3 實作 credentials/HTTP 讀取，確保 token、credentials 與完整錯誤 body 不進 log
- [x] 3.4 實作 single-flight refresh lock、TTL、max-stale 與週期 background task
- [x] 3.5 在 FastAPI lifespan 啟動/關閉 monitor；初次 refresh 有短 timeout 且不阻止服務啟動
- [x] 3.6 先新增並通過 90%/85% hysteresis、unknown/stale 與 concurrency tests
- [x] 3.7 新增 401、429、5xx、network timeout、missing credentials 與 cache recovery tests

## 4. Codex Protocol Compatibility Spike

- [x] 4.1 Pin 一個 `codex-acp` + Codex runtime 組合，保存 adapter/version/protocol fixture
- [x] 4.2 以 fake ACP connection 測試 repeated message chunks、tool progress 去重、token/model metadata 與 cancel
- [x] 4.3 建立真實唯讀 smoke fixture：純文字、重複文字、單一唯讀 MCP 工具、timeout/cancel
- [x] 4.4 驗證 stdio MCP 能完整傳遞 command/args/env
- [x] 4.5 驗證 HTTP MCP 能完整傳遞 URL/headers；若 Generic client 不支援，實作安全 schema conversion 或改走 App Server spike
- [x] 4.6 驗證 permission event 可取得 canonical server/tool identity；若只能模糊比對則停止正式 adapter 開發
- [x] 4.7 記錄 ACP 與直接 Codex App Server stdio 的差異，確認正式 provider protocol

## 5. Codex Provider Adapter（TDD）

- [x] 5.1 先新增 Codex provider contract tests，涵蓋完整 `call_ai()` kwargs
- [x] 5.2 實作 per-request session workdir，沿用主系統 MCP merge/filter 與 env injection 規則
- [x] 5.3 實作 canonical permission guard；同名、Unknown、concurrent 或缺少 namespace 時 fail closed
- [x] 5.4 實作 terminal/file-write/native image deny，圖片必須走允許的 CTOS MCP 工具
- [x] 5.5 實作 tool-call limit、全域生圖上限、callbacks、tool timings 與 callback error isolation
- [x] 5.6 實作 message/tool event 去重、partial result、token、actual model 與 bounded stderr diagnostics
- [x] 5.7 實作 timeout cancel、disconnect、process terminate/kill 與所有路徑 cleanup tests
- [x] 5.8 實作 concurrency semaphore、queue timeout 與 provider circuit breaker
- [x] 5.9 新增 binary missing、auth expired、protocol mismatch、MCP startup failure、overload tests
- [x] 5.10 確認 Codex provider 核心安全分支皆有明確測試，不能只依 aggregate coverage

## 6. 部署與 Readiness

- [x] 6.1 將 adapter/runtime 以 exact version 納入可重現的 package lock 或部署 artifact
- [x] 6.2 更新部署 preflight：binary path、version、service user、auth storage、`NO_BROWSER=1`、最小 handshake
- [x] 6.3 確認 systemd 使用 `ct` credentials，不依賴 root 或互動 login
- [x] 6.4 實作 provider readiness 與 circuit 狀態輸出，錯誤不得包含 token
- [ ] 6.5 在 staging 驗證服務重啟、登入過期、adapter 缺失與 forced Claude rollback

## 7. 可觀測性

- [x] 7.1 將 requested role、selected provider、actual model、route reason 與 usage snapshot 加入 response metadata
- [x] 7.2 將 routing metadata 寫入 structured log 與 `ai_logs.parsed_response`，保留既有 `model` 統計相容性
- [x] 7.3 記錄 provider latency、queue latency、error category、tool started/completed 與 circuit 狀態
- [x] 7.4 新增 log tests，確認敏感 credentials、MCP headers/env 與 stderr token 不會被記錄
- [x] 7.5 建立 canary 查詢與人工檢查清單；確認無法辨識 provider 的請求視為驗收失敗

## 8. 分階段 Caller 整合

- [x] 8.1 internal admin/test-agent 改用 `call_ai()`，限制唯讀/無副作用工具，完成第一階段 canary
- [x] 8.2 Web Chat allowlist Agent 改用 `call_ai()`，驗證 history、system prompt、tool results 與 AI log
- [x] 8.3 Line/Telegram allowlist 使用者或群組 canary，驗證文字、圖片、語音、progress callback 與 partial result
- [x] 8.4 驗證任何 provider failure 都不會重複執行 side-effect tool
- [ ] 8.5 canary 穩定後才評估一般 Line/Telegram 對話啟用 auto mode
- [x] 8.6 restricted mode 通過身份、權限與成本測試後獨立遷移
- [ ] 8.7 簡報 JSON、生圖、research、scheduler、summary 各自新增 parity tests 後才逐一遷移；未完成者維持 Claude

## 9. 驗收與 Rollout Gate

- [x] 9.1 `uv run pytest` 全數通過，無既有測試回歸
- [x] 9.2 `npm run ci:check` 與 `npm run test:backend:cov:target` 通過，整體 coverage 不低於 90%
- [x] 9.3 `openspec validate add-codex-acp-failover --strict --no-interactive` 通過
- [ ] 9.4 真實 ACP 唯讀 smoke matrix 全數通過，stdio/HTTP MCP 無缺漏
- [ ] 9.5 bounded concurrency/load test 通過，無 zombie process、無無限制記憶體成長
- [ ] 9.6 演練 forced Claude kill switch、清空 canary、Codex auth 過期與 circuit open
- [ ] 9.7 canary 連續觀察至少 24–72 小時，無重複副作用、安全退化或不可追查請求
- [ ] 9.8 記錄 Go/No-Go 結論；只有 Go 才能擴大 auto mode scope

## 10. 文件與版本

- [x] 10.1 更新 `docs/ai-agent-design.md`、`docs/backend.md` 與 `.env.example`
- [x] 10.2 更新 `docs/module-index.md` 加入 provider router、usage monitor 與 Codex adapter
- [x] 10.3 更新部署文件，記錄 Codex 認證、pin 版本、preflight、監控與 rollback
- [ ] 10.4 功能完成後依專案規則確認是否進行 MINOR version bump，並同步三個版本位置
