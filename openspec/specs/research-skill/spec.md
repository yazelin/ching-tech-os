## MODIFIED Requirements

### Requirement: start/check 兩段式改為控制平面
`research-skill` SHALL 將 `start-research` / `check-research` 作為任務控制平面，不在主回合同步執行完整研究。

#### Scenario: start-research 只負責建立任務
- **WHEN** 使用者啟動研究
- **THEN** `start-research` 建立 job 並回傳 `job_id`
- **AND** 不等待 search/fetch/synthesis 全部完成

#### Scenario: check-research 回傳進度與結果
- **WHEN** 使用者查詢任務進度
- **THEN** `check-research` 回傳狀態、進度、錯誤與結果路徑
- **AND** 可重複查詢直到任務完成或失敗

### Requirement: 失敗後重啟策略
`check-research` 若回報失敗，系統 SHALL 引導同主題重新 `start-research`，而非回退為同步長回合抓取。

#### Scenario: 任務失敗時給出正確下一步
- **WHEN** `check-research` 回傳 `failed`
- **THEN** 回應內容包含可執行的重啟建議（重新 start）
- **AND** 不建議直接改用同步 WebSearch/WebFetch 重做同主題
