## MODIFIED Requirements

### Requirement: 研究任務工具路徑鎖定
Bot 平台在研究類需求中 SHALL 優先走 `research-skill` 的 start/check 流程，避免同主題切回同步 WebSearch/WebFetch。

#### Scenario: 已啟動研究 job 的同主題追問
- **WHEN** 對話已有對應研究 `job_id`
- **THEN** 系統優先引導 `check-research`
- **AND** 不對同主題再發起同步 WebSearch/WebFetch 長回合

### Requirement: 簡短查詢與研究查詢分流
Bot 平台 SHALL 區分簡短單點查詢與多來源研究查詢。

#### Scenario: 單點即時資訊
- **WHEN** 使用者問題屬於簡短單點查詢（例如天氣、單一資訊）
- **THEN** 可使用 WebSearch/WebFetch 直接回覆
- **AND** 不強制轉為背景研究任務

#### Scenario: 多來源研究需求
- **WHEN** 使用者要求完整研究（搜尋 + 擷取 + 統整）
- **THEN** 必須走 `start-research` / `check-research`
- **AND** 先回覆受理與 `job_id`
