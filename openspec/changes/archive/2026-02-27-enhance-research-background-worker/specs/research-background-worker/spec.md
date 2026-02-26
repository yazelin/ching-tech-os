## ADDED Requirements

### Requirement: Background Research Job Lifecycle
`research-skill` SHALL 以背景 worker 執行研究任務生命週期，狀態至少包含 `queued`、`running`、`completed`、`failed`、`canceled`。

#### Scenario: start-research 快速受理
- **WHEN** 使用者呼叫 `start-research`
- **THEN** 系統立即建立 job 並回傳 `job_id`
- **AND** 初始狀態為 `queued`，不等待完整研究完成

#### Scenario: check-research 反映即時狀態
- **WHEN** 使用者呼叫 `check-research`
- **THEN** 系統回傳目前 job 狀態與進度
- **AND** 不在 `check-research` 同步執行重負載研究流程

### Requirement: Worker 啟動策略
背景研究 worker SHALL 先沿用 `os.fork` 方式啟動，與現有 script 背景執行模式相容。

#### Scenario: 以 os.fork 啟動背景執行
- **WHEN** 任務從 queue 進入執行階段
- **THEN** 系統使用 `os.fork` 建立背景子程序
- **AND** 子程序可獨立更新 job 狀態與產物檔案

### Requirement: Worker 任務治理與清理
研究 job 暫存資料 SHALL 有固定清理機制，行為與現有影片下載/轉字幕 skill 的清理策略一致。

#### Scenario: 清理過期研究暫存
- **WHEN** 任務產物超過保留期限
- **THEN** 系統定期清理過期 job 目錄與暫存檔
- **AND** 保留必要索引資訊以避免 `check-research` 讀取無效路徑
