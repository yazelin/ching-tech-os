## ADDED Requirements

### Requirement: 特殊 pipeline 必須先通過 parity gate 才可遷移

簡報 JSON、生圖、research、scheduler、summary 等特殊 pipeline MUST 先具備 provider-neutral parity tests（涵蓋輸出格式、marker、工具序列與錯誤路徑），且測試通過後才可將該 pipeline 的 caller 改用 `call_ai()`。未通過者 MUST 維持 `call_claude()`，並記錄阻擋原因。

#### Scenario: parity 未通過的 pipeline

- **GIVEN** 某 pipeline 的 parity tests 尚未全部通過
- **WHEN** 開發者嘗試將該 pipeline 遷移至 `call_ai()`
- **THEN** 該遷移 MUST NOT 合併，pipeline 維持純 Claude 行為

#### Scenario: summary pipeline 遷移

- **GIVEN** summary parity tests 通過（純文字摘要契約）
- **WHEN** 對話壓縮以 `call_ai()` 執行且 provider 為 Codex
- **THEN** 回傳文字摘要格式與 Claude 契約一致，routing metadata 記錄實際 provider

#### Scenario: 結構化 JSON 輸出偏差

- **GIVEN** 簡報 outline 由 Codex 產生且 JSON 格式偏差
- **WHEN** 既有 JSON 解析/修復路徑無法修復
- **THEN** 該請求以既有錯誤流程失敗，MUST NOT 產生格式錯誤的簡報

### Requirement: Router 支援 per-context 額外工具 allowlist 且預設不變

Codex 工具過濾 MUST 維持唯讀前綴 fail-closed 為預設。系統 MAY 依 routing context 設定「明確列舉的額外工具 allowlist」；未設定時行為 MUST 與現行完全相同。任何額外放行的副作用工具 MUST 有對應測試。

#### Scenario: 未設定額外 allowlist

- **GIVEN** 未設定任何 per-context 工具 allowlist
- **WHEN** 任一請求路由至 Codex
- **THEN** 工具過濾行為與唯讀前綴規則完全一致

#### Scenario: scheduler context 放行特定工具

- **GIVEN** scheduler context 設定了明確的額外工具 allowlist
- **WHEN** scheduler 任務路由至 Codex
- **THEN** 只有唯讀前綴工具與該 allowlist 明列的工具會暴露給 Codex，其餘一律過濾

#### Scenario: allowlist 設定格式錯誤

- **GIVEN** per-context allowlist 環境設定格式無效
- **WHEN** 設定載入
- **THEN** 系統記錄錯誤並回到預設唯讀行為，MUST NOT 部分套用

### Requirement: research 遷移第一版僅限唯讀查詢路徑

research pipeline 的 Codex 路由第一版 MUST 僅涵蓋 job 狀態查詢等唯讀路徑；啟動新研究（需 WebSearch/WebFetch）MUST 維持 Claude。

#### Scenario: 研究進度查詢走 Codex

- **GIVEN** research 查詢 context 在 canary scope 且 usage 達切換門檻
- **WHEN** 使用者查詢研究進度
- **THEN** Codex 以唯讀工具回覆 job 狀態，格式與 Claude 契約一致

#### Scenario: 啟動新研究維持 Claude

- **GIVEN** 使用者要求啟動新研究
- **WHEN** 請求進入路由
- **THEN** 該請求 MUST 使用 Claude，不受 usage 切換影響
