## ADDED Requirements

### Requirement: Brave Search Provider
系統 SHALL 提供可被 `research-skill` 呼叫的 Brave Search provider，以取得結構化搜尋結果。

#### Scenario: 使用 Brave API 搜尋
- **WHEN** `research-skill` 執行搜尋且已設定 Brave API key
- **THEN** 系統呼叫 Brave Search API 取得結果
- **AND** 回傳標準化欄位（至少含 title、url、snippet）

#### Scenario: Brave API 認證失敗
- **WHEN** Brave API key 無效或缺失
- **THEN** provider 回傳可診斷錯誤資訊
- **AND** 上層流程可判斷並執行 fallback

### Requirement: Provider Fallback Compatibility
Brave provider SHALL 與既有搜尋 provider 共存，維持研究流程可用性。

#### Scenario: Brave 失敗時回退
- **WHEN** Brave provider 呼叫失敗（配額、網路、5xx、429）
- **THEN** research 流程回退到下一個 provider
- **AND** 任務狀態仍可被 check-research 查詢
