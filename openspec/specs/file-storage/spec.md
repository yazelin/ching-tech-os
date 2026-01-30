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

### Requirement: shared zone 多掛載點路徑解析
path_manager SHALL 支援 `shared://` 協議下的多個子來源對應到不同掛載點。

#### Scenario: 解析帶來源前綴的 shared 路徑
- **GIVEN** path_manager 設定了 projects 和 circuits 子來源
- **WHEN** 解析 `shared://circuits/線路圖A/xxx.dwg`
- **THEN** 對應到本機路徑 `/mnt/nas/circuits/線路圖A/xxx.dwg`

#### Scenario: 解析 projects 子來源路徑
- **GIVEN** path_manager 設定了 projects 子來源
- **WHEN** 解析 `shared://projects/亦達光學/layout.pdf`
- **THEN** 對應到本機路徑 `/mnt/nas/projects/亦達光學/layout.pdf`

#### Scenario: 向後相容舊格式
- **GIVEN** 資料庫中存在舊格式 `shared://亦達光學/layout.pdf`（無子來源前綴）
- **WHEN** 解析該路徑
- **THEN** 第一段 `亦達光學` 不是已知子來源名稱
- **AND** fallback 對應到 `/mnt/nas/projects/亦達光學/layout.pdf`

