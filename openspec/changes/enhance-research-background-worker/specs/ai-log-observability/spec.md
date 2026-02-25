## MODIFIED Requirements

### Requirement: 研究 job 可觀測性增強
AI 日誌與任務狀態 SHALL 可追蹤背景研究 job 的主要階段與關鍵欄位。

#### Scenario: 記錄 job 與階段狀態
- **WHEN** job 進入 `queued`、`running`、`completed`、`failed` 或 `canceled`
- **THEN** 系統記錄對應時間點與狀態
- **AND** 可由 `check-research` 與 ai logs 對照追查

### Requirement: 子流程工具軌跡可追查
worker 內 Claude 子流程 SHALL 保留工具呼叫摘要，供除錯與成效分析。

#### Scenario: 研究任務完成或失敗
- **WHEN** 任務結束
- **THEN** 系統保存工具軌跡摘要（包含 search/fetch/synthesis 階段）
- **AND** 重要失敗原因可在查詢結果中呈現
