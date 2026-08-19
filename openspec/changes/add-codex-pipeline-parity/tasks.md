# add-codex-pipeline-parity 任務

## 1. Parity test harness 與基線

- [x] 1.1 盤點五個 pipeline 的現行輸出契約（JSON schema、marker、工具序列、錯誤路徑），記錄於 design 附註
- [x] 1.2 建立 provider-neutral parity test fixtures（fake provider 注入 `call_ai()` 邊界）（模式已於第一階段建立，3.x 沿用）
- [x] 1.3 以 characterization tests 鎖住各 pipeline 現行 Claude 行為，全套件維持 90% coverage gate（既有測試已覆蓋，見 design 附註）

## 2. Per-context 工具政策（scheduler/生圖前置）

- [x] 2.1 先寫 tests：未設定時行為與唯讀前綴完全一致、格式錯誤回安全預設、明列工具才放行
- [x] 2.2 實作 `CODEX_CONTEXT_TOOL_ALLOWLIST` 設定解析（驗證 + fail-closed）與 router 過濾整合
- [x] 2.3 更新 `.env.example` 與 `docs/ai-agent-design.md`

## 3. 逐 pipeline 遷移（風險低 → 高，各自獨立 commit 與 canary context）

- [x] 3.1 summary：parity tests → `call_ai()` + RoutingContext，驗證壓縮摘要契約
- [x] 3.2 簡報 JSON：parity tests（含 JSON 修復路徑）→ 遷移 `generate_outline`
- [x] 3.3 research：決定性意圖偵測 → research context 固定 Claude（啟動與查詢皆同，見 design 附註）
- [x] 3.4 生圖：機制就緒（per-context allowlist），預設不放行，由營運以 env 啟用（見 design 附註）
- [x] 3.5 scheduler：結論維持 Claude，阻擋原因記錄於 design 附註

## 4. 驗收

- [x] 4.1 `uv run pytest` 全綠，coverage ≥90%（1618 passed、91.02%）
- [x] 4.2 已遷移 pipeline 的真實 Codex smoke（opt-in env）通過（summary + outline，見 design 附註）
- [x] 4.3 canary 檢查清單納入新 contexts（格式錯誤觀察併入日常 canary 檢查）
- [x] 4.4 `openspec validate add-codex-pipeline-parity --strict --no-interactive` 通過
- [x] 4.5 文件更新（module-index、canary checklist）；version bump 0.10.0 → 0.11.0（MINOR）
