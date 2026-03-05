## MODIFIED Requirements

### Requirement: start/check 兩段式改為控制平面
`research-skill` SHALL 將 `start-research` / `check-research` 作為任務控制平面，不在主回合同步執行完整研究。start script SHALL 接受並持久化 `caller_context`，供主動推送使用。

#### Scenario: start-research 只負責建立任務
- **WHEN** 使用者啟動研究
- **THEN** `start-research` 建立 job 並回傳 `job_id`
- **AND** 不等待 search/fetch/synthesis 全部完成

#### Scenario: check-research 回傳進度與結果
- **WHEN** 使用者查詢任務進度
- **THEN** `check-research` 回傳狀態、進度、錯誤與結果路徑
- **AND** 可重複查詢直到任務完成或失敗

#### Scenario: start-research 接受 caller_context
- **WHEN** AI 呼叫 `start-research` 時 input 包含 `caller_context` 欄位
- **THEN** script SHALL 將 `caller_context` 原樣寫入 `status.json`
- **AND** 背景研究完成後，子行程 SHALL 呼叫 `/api/internal/proactive-push` 觸發通知

#### Scenario: 研究完成後觸發推送通知
- **WHEN** 背景研究子行程寫入 `status: "completed"`
- **THEN** 子行程 SHALL POST 至 `/api/internal/proactive-push`，帶入 `job_id` 與 `skill="research-skill"`
- **AND** 推送訊息包含研究摘要（前 500 字）與查詢原文

## MODIFIED Requirements

### Requirement: 失敗後重啟策略
`check-research` 若回報失敗，系統 SHALL 引導同主題重新 `start-research`，而非回退為同步長回合抓取。

#### Scenario: 任務失敗時給出正確下一步
- **WHEN** `check-research` 回傳 `failed`
- **THEN** 回應內容包含可執行的重啟建議（重新 start）
- **AND** 不建議直接改用同步 WebSearch/WebFetch 重做同主題
