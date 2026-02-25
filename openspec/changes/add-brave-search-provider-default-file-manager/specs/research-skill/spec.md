## ADDED Requirements

### Requirement: 研究搜尋 Provider 優先序
`research-skill` 在執行搜尋時 MUST 支援 provider 優先序，並優先使用 Brave provider。

#### Scenario: Brave 可用時優先使用
- **WHEN** 啟動 `start-research` 且 Brave API key 已配置
- **THEN** 系統先使用 Brave provider 取得候選來源
- **AND** 來源清單交由既有抓取/統整流程處理

#### Scenario: Brave 不可用時自動回退
- **WHEN** Brave provider 失敗或回傳空結果
- **THEN** 系統自動回退到既有 provider（例如 DDG Instant）
- **AND** 任務不因單一 provider 失敗而直接中止

### Requirement: Provider 診斷資訊可追蹤
`research-skill` MUST 在任務狀態中保留 provider 使用與失敗資訊，供後續除錯與觀察。

#### Scenario: 狀態檔記錄 provider
- **WHEN** `start-research` 建立或更新 status.json
- **THEN** 系統記錄當前使用的 provider 名稱
- **AND** 若發生回退，記錄失敗原因摘要

#### Scenario: check-research 回傳 provider 狀態
- **WHEN** 使用者呼叫 `check-research`
- **THEN** 回傳內容包含 provider 狀態資訊（成功 provider 或 fallback 訊息）
