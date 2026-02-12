## MODIFIED Requirements

### Requirement: 動態工具白名單生成
系統在組裝 AI 工具白名單時 SHALL 支援 script-first 路由策略。

#### Scenario: script 與 MCP 能力重疊
- **WHEN** 同一能力同時由 script tool 與 MCP tool 提供
- **THEN** 白名單預設優先暴露 script tool
- **AND** MCP tool 僅作為回退或系統整合用途

#### Scenario: script 執行失敗回退
- **WHEN** AI 呼叫 script tool 失敗且符合回退條件
- **THEN** 系統允許回退對應 MCP tool
- **AND** 記錄此次回退決策與錯誤原因
