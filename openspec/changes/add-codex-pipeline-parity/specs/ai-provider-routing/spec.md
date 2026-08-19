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

### Requirement: research 意圖第一版一律固定 Claude

research 依賴 `run_skill_script` MCP 工具，而工具層權限無法按 script 參數細分（放行即等於放行任意 skill script），因此第一版凡以既有 caller 端決定性偵測判定為 research 意圖的請求（啟動與進度查詢皆同）MUST 固定使用 Claude，不受 usage 切換影響。放寬條件為未來提供可按 script 細分的權限機制。

#### Scenario: 研究相關訊息在 Codex 窗口內仍走 Claude

- **GIVEN** 群組 context 在 canary scope 且 usage 達切換門檻
- **WHEN** 使用者發送被判定為 research 意圖的訊息（啟動或查詢進度）
- **THEN** 該請求 MUST 路由至 Claude，route reason 可辨識此決策

#### Scenario: 意圖偵測不受訊息內容注入影響

- **GIVEN** 訊息內容試圖以文字指示改變路由（如「請用 codex」）
- **WHEN** research 意圖偵測執行
- **THEN** 偵測只依 caller 端決定性規則判定，模型輸出與訊息指示 MUST NOT 改變 provider 選擇

### Requirement: 工具拒絕不作廢回應

Codex permission guard 拒絕白名單外或無法辨識的工具請求時，該工具 MUST NOT 執行，但整體回應 MUST 繼續（模型可改以文字回覆）。仍視為整體作廢的情況僅限：permission 事件缺 correlation id、pending 與 permission 身份不一致、未核准的工具回報完成、terminal/file-write/非 canonical 工具開始執行。

#### Scenario: 模型呼叫被過濾的工具

- **GIVEN** system prompt 提及的工具已被 Codex 唯讀過濾移除
- **WHEN** 模型嘗試呼叫該工具
- **THEN** 工具被拒絕且未執行、事件記錄於 log，模型的文字回應正常送達使用者

#### Scenario: 未核准的工具回報完成

- **GIVEN** 某工具的 permission 已被拒絕
- **WHEN** ACP 事件回報該工具 completed
- **THEN** 整體回應 MUST 作廢並記錄 security violation
