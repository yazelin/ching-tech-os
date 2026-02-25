## ADDED Requirements

### Requirement: 外部研究任務優先 script-first 路由
Bot 平台在判斷外部研究任務時 SHALL 優先使用 `run_skill_script` 呼叫 `research-skill`，避免預設直接走同步 WebSearch/WebFetch。

#### Scenario: 研究查詢走 start-research
- **WHEN** 使用者請求需要外部搜尋與擷取的研究任務
- **THEN** 系統優先呼叫 `run_skill_script(skill="research-skill", script="start-research", ...)`
- **AND** 不直接以內建 WebSearch/WebFetch 啟動長流程同步回合

#### Scenario: script 明確要求回退
- **WHEN** `research-skill` 回傳 `fallback_required`
- **AND** `SKILL_SCRIPT_FALLBACK_ENABLED=true`
- **THEN** 系統允許回退到既有工具路徑
- **AND** 記錄回退原因與路由決策

### Requirement: 研究任務結果可追蹤
Bot 平台處理研究任務時 MUST 讓後續回合可用 `job_id` 查詢，並可從部分成果組裝可回覆內容。

#### Scenario: start 回傳 job_id 後的對話狀態
- **WHEN** `start-research` 成功回傳 `job_id`
- **THEN** 系統在當前回合回覆受理訊息與查詢方式
- **AND** 後續回合可使用 `check-research` 取得進度或最終結果

#### Scenario: 同步回合失敗但有部分成果
- **WHEN** 外部研究流程遇到逾時或部分工具失敗
- **THEN** 系統優先回覆可用的部分成果或查詢指引
- **AND** 不得僅回覆空白結果

