## ADDED Requirements

### Requirement: 預設 App 權限包含 file-manager
Bot 權限系統在未綁定或未提供個人化權限設定時 SHALL 將 `file-manager` 視為可用。

#### Scenario: 未綁定使用者套用預設權限
- **WHEN** 來源使用者未綁定 CTOS 帳號
- **THEN** 系統使用有效預設 App 權限
- **AND** `file-manager` 權限為啟用狀態

#### Scenario: 使用者紀錄不存在時套用預設權限
- **WHEN** 工具權限檢查找不到使用者紀錄
- **THEN** 系統套用有效預設 App 權限
- **AND** `research-skill` 不因缺少 `file-manager` 預設權限而直接拒絕

### Requirement: 研究型任務優先走 script 路徑
Bot 平台處理外部研究需求時 SHALL 優先走 `run_skill_script` 的 `research-skill`。

#### Scenario: research-skill 可用時不退回舊搜尋路徑
- **WHEN** `research-skill` 可正常執行
- **THEN** 系統優先使用 `start-research` + `check-research`
- **AND** 不主動改走同步 WebSearch/WebFetch 長回合流程
