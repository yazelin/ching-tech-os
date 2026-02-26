## ADDED Requirements

### Requirement: Script 化後的 MCP 預設載入最小化
系統部署設定 SHALL 支援在 script-first 場景下降低預設外部 MCP server 載入數量。

#### Scenario: script-first 低依賴部署
- **WHEN** 部署以 `base`、`file-manager` script 化能力為主
- **THEN** 系統 SHALL 可在不啟用 `erpnext`、`printer`、`nanobanana` 的情況下維持 base/file-manager 主要能力可用

#### Scenario: 設定文件同步
- **WHEN** script 化能力上線
- **THEN** README 與運維文件 SHALL 提供 MCP 載入最小化建議
- **AND** 指出哪些 skills 仍依賴外部 MCP server
