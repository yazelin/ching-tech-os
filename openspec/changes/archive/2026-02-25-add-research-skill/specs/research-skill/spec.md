## ADDED Requirements

### Requirement: 非同步研究任務啟動
`research-skill` MUST 提供 `start-research` script，以非同步模式啟動外部研究流程並立即回傳任務識別。

#### Scenario: 啟動研究任務立即回傳 job_id
- **WHEN** AI 呼叫 `run_skill_script(skill="research-skill", script="start-research", input='{"query":"..."}')`
- **THEN** 系統在同一回合回傳 `{"success": true, "job_id": "<id>", "status": "started"}`
- **AND** 研究流程在背景繼續執行，不阻塞當前回合

#### Scenario: 缺少 query 參數
- **WHEN** `start-research` 收到的 input 缺少 `query` 或為空字串
- **THEN** 系統回傳 `{"success": false, "error": "缺少 query 參數"}`

### Requirement: 研究進度與結果查詢
`research-skill` MUST 提供 `check-research` script，回傳任務進度、部分成果與最終結果。

#### Scenario: 查詢進行中的任務
- **WHEN** AI 呼叫 `run_skill_script(skill="research-skill", script="check-research", input='{"job_id":"a1b2c3d4"}')`
- **AND** 任務狀態為進行中
- **THEN** 系統回傳 `{"success": true, "status": "<階段>", "progress": <0-100>}`
- **AND** 若已有部分成果，回傳 `partial_results` 與 `sources`

#### Scenario: 查詢已完成任務
- **WHEN** 任務狀態為 `completed`
- **THEN** 系統回傳 `{"success": true, "status": "completed", "final_summary": "...", "sources": [...]}` 
- **AND** `sources` 至少包含來源標題或 URL

#### Scenario: 查詢不存在的 job
- **WHEN** `job_id` 不存在或狀態檔遺失
- **THEN** 系統回傳 `{"success": false, "error": "找不到研究任務"}`

### Requirement: 狀態追蹤與失敗可診斷
研究任務 MUST 以結構化狀態追蹤執行階段，並在失敗時回傳可診斷資訊。

#### Scenario: 狀態階段流轉
- **WHEN** 任務從建立到完成
- **THEN** 狀態依序可觀察為 `starting`、`searching`、`fetching`、`synthesizing`、`completed`（或 `failed`）

#### Scenario: 外部擷取失敗
- **WHEN** 部分來源擷取失敗
- **THEN** 系統仍保留成功來源並持續統整
- **AND** 在結果中標註失敗來源與錯誤摘要

