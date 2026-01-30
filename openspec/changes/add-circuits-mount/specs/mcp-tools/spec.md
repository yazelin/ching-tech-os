# mcp-tools spec delta

## MODIFIED Requirements

### Requirement: 搜尋 NAS 共享檔案 MCP 工具
MCP Server SHALL 提供 `search_nas_files` 工具搜尋多個 NAS 共享掛載點中的檔案。

#### Scenario: 搜尋範圍包含多來源
- **GIVEN** 系統掛載了 projects 和 circuits 兩個共享區
- **WHEN** 呼叫 `search_nas_files(keywords="layout")`
- **THEN** 系統同時搜尋 `/mnt/nas/projects` 和 `/mnt/nas/circuits`
- **AND** 結果路徑帶來源前綴（如 `shared://projects/...`、`shared://circuits/...`）

#### Scenario: 結果路徑格式
- **GIVEN** 在 circuits 掛載點找到檔案 `線路圖A/xxx.dwg`
- **WHEN** 搜尋結果回傳
- **THEN** 路徑為 `shared://circuits/線路圖A/xxx.dwg`

#### Scenario: 單一來源不可用
- **GIVEN** circuits 掛載點不存在或未掛載
- **WHEN** 呼叫 `search_nas_files`
- **THEN** 系統跳過該來源，僅搜尋可用的掛載點
- **AND** 不回傳錯誤

#### Scenario: 權限擴充預留
- **GIVEN** 搜尋來源定義為字典結構
- **WHEN** 未來實作權限控制
- **THEN** 可依使用者權限過濾搜尋來源字典
- **AND** 不需修改搜尋邏輯本身
