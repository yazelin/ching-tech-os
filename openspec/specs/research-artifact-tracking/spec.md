## ADDED Requirements

### Requirement: 標準化研究產物落盤
每個研究 job SHALL 產生標準化產物，至少包含 `status.json`、`result.md`、`sources.json`、`tool_trace.json`。

#### Scenario: 任務完成時保存完整產物
- **WHEN** 研究任務狀態變為 `completed`
- **THEN** 系統保存最終摘要、來源清單與工具軌跡檔
- **AND** `check-research` 可回傳 `result_ctos_path` 與來源資訊

### Requirement: 產物可供後續知識流程使用
研究產物 SHALL 可被後續工具流程引用，讓使用者可要求「將完成結果存入知識庫」。

#### Scenario: 使用者要求歸檔研究成果
- **WHEN** 任務已完成且使用者要求保存成果
- **THEN** 系統可使用研究產物路徑作為後續知識庫/歸檔工具輸入
- **AND** 不需要重新執行整個研究流程

### Requirement: 產物保留與清理策略
研究產物 SHALL 有保留期限與清理策略，避免長期堆積。

#### Scenario: 超過保留期限
- **WHEN** 研究產物超過保留天數
- **THEN** 系統清理過期產物
- **AND** 保留必要的失敗/完成摘要以供日誌稽核
