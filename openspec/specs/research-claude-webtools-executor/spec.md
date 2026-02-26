## ADDED Requirements

### Requirement: Worker 內受控 Claude Web Tools 執行
背景研究 worker SHALL 能在獨立執行流程中呼叫 Claude，並使用 WebSearch/WebFetch 完成多來源研究。

#### Scenario: 不阻塞主對話回合
- **WHEN** 研究任務需要多輪搜尋與抓取
- **THEN** worker 在背景呼叫 Claude + Web tools 執行
- **AND** 使用者主回合只收到受理訊息與 `job_id`

### Requirement: 研究模型預設
worker 內研究模型 SHALL 預設使用 Sonnet（`claude-sonnet`），以平衡品質與成本。

#### Scenario: 未指定模型時
- **WHEN** 研究任務未提供模型覆寫參數
- **THEN** worker 使用 Sonnet 作為預設模型
- **AND** 任務追蹤資訊記錄實際使用模型

### Requirement: Web Tools 失敗容忍
worker SHALL 在 WebSearch/WebFetch 局部失敗時保留可用結果，避免整個任務直接失敗。

#### Scenario: 部分來源 fetch 失敗
- **WHEN** 任一來源抓取失敗或超時
- **THEN** worker 繼續處理其他可用來源並產生部分成果
- **AND** `check-research` 可回傳失敗來源摘要與可用結果
