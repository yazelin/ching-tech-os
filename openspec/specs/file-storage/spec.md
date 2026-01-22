# file-storage Specification

## Purpose
TBD - created by archiving change tenant-nas-isolation. Update Purpose after archive.
## Requirements
### Requirement: 租戶檔案隔離
系統 SHALL 將不同租戶的檔案儲存在隔離的目錄中，確保租戶間的檔案無法互相存取。

#### Scenario: 知識庫附件使用租戶路徑
- **WHEN** 使用者上傳知識庫附件
- **AND** 租戶 ID 已知
- **THEN** 附件 SHALL 儲存在 `/mnt/nas/ctos/tenants/{tenant_id}/knowledge/` 目錄下

#### Scenario: Line Bot 檔案使用租戶路徑
- **WHEN** Line Bot 儲存使用者上傳的檔案
- **AND** 租戶 ID 已知
- **THEN** 檔案 SHALL 儲存在 `/mnt/nas/ctos/tenants/{tenant_id}/linebot/` 目錄下

#### Scenario: 向後相容性
- **WHEN** 租戶 ID 未指定（單租戶模式）
- **THEN** 系統 SHALL 使用預設的舊路徑以保持向後相容

### Requirement: 跨租戶存取防護
系統 SHALL 在資料庫查詢中加入租戶 ID 過濾，防止跨租戶的資料存取。

#### Scenario: Line 群組查詢包含租戶過濾
- **WHEN** MCP 工具查詢 Line 群組資訊
- **THEN** 查詢 SHALL 包含 `tenant_id` 條件以確保只回傳該租戶的群組

