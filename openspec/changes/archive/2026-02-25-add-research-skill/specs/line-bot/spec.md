## ADDED Requirements

### Requirement: 長時研究任務採兩段式互動
Line Bot 在處理外部研究任務時 SHALL 採用 start/check 兩段式回覆，先回覆受理資訊，再由使用者查詢進度。

#### Scenario: 群組對話啟動研究任務
- **WHEN** 群組內使用者觸發 AI 研究請求且 `start-research` 成功
- **THEN** Bot 回覆「已受理」訊息並包含 `job_id` 與查詢方式
- **AND** 回覆需維持群組既有 mention 規則

#### Scenario: 個人對話啟動研究任務
- **WHEN** 個人對話觸發研究請求且 `start-research` 成功
- **THEN** Bot 回覆「已受理」訊息並包含 `job_id` 與查詢方式
- **AND** 不使用群組 mention 格式

### Requirement: 研究進度查詢回覆
Line Bot MUST 支援使用者以 `job_id` 查詢研究任務，並根據任務狀態回覆進度、部分結果或最終統整。

#### Scenario: 查詢進行中任務
- **WHEN** 使用者提供 `job_id` 並呼叫 `check-research` 回傳進行中
- **THEN** Bot 回覆目前階段與進度
- **AND** 若有部分來源結果，回覆可讀的部分摘要

#### Scenario: 查詢已完成任務
- **WHEN** `check-research` 回傳 `status="completed"`
- **THEN** Bot 回覆最終統整內容
- **AND** 回覆包含來源列表或可檢視來源資訊

#### Scenario: 查詢失敗任務
- **WHEN** `check-research` 回傳 `status="failed"` 或錯誤
- **THEN** Bot 回覆失敗原因與下一步建議（重試或縮小查詢範圍）

