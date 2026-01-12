# MCP Tools Spec Delta: 專案附件與連結

## ADDED Requirements

### Requirement: add_project_link
系統 SHALL 提供 MCP 工具讓 AI 新增專案連結。

#### Scenario: 新增專案連結
Given AI 收到用戶要求新增連結
When AI 呼叫 add_project_link(project_id, title, url, description?)
Then 系統在 project_links 表建立記錄
And 回傳成功訊息包含連結標題

### Requirement: get_project_links
系統 SHALL 提供 MCP 工具讓 AI 查詢專案連結列表。

#### Scenario: 查詢專案連結
Given 專案有連結記錄
When AI 呼叫 get_project_links(project_id)
Then 系統回傳連結列表（標題、URL、描述）

### Requirement: update_project_link
系統 SHALL 提供 MCP 工具讓 AI 更新專案連結資訊。

#### Scenario: 更新連結標題
Given 專案有一個連結
When AI 呼叫 update_project_link(link_id, title="新標題")
Then 系統更新連結標題
And 回傳成功訊息

### Requirement: delete_project_link
系統 SHALL 提供 MCP 工具讓 AI 刪除專案連結。

#### Scenario: 刪除連結
Given 專案有一個連結
When AI 呼叫 delete_project_link(link_id)
Then 系統刪除連結記錄
And 回傳成功訊息

### Requirement: add_project_attachment
系統 SHALL 提供 MCP 工具讓 AI 從 NAS 路徑添加附件到專案。

#### Scenario: 從 Line 附件添加
Given 用戶在 Line 發送了圖片
And AI 用 get_message_attachments 取得 NAS 路徑
When AI 呼叫 add_project_attachment(project_id, nas_path, description?)
Then 系統建立附件記錄（storage_path 使用 nas:// 格式）
And 回傳成功訊息包含檔案名稱

#### Scenario: 從 NAS 檔案添加
Given NAS 上有檔案
And AI 用 search_nas_files 取得路徑
When AI 呼叫 add_project_attachment(project_id, nas_path)
Then 系統建立附件記錄
And 回傳成功訊息

### Requirement: get_project_attachments
系統 SHALL 提供 MCP 工具讓 AI 查詢專案附件列表。

#### Scenario: 查詢專案附件
Given 專案有附件記錄
When AI 呼叫 get_project_attachments(project_id)
Then 系統回傳附件列表（檔名、類型、大小、描述）

### Requirement: update_project_attachment
系統 SHALL 提供 MCP 工具讓 AI 更新專案附件描述。

#### Scenario: 更新附件描述
Given 專案有一個附件
When AI 呼叫 update_project_attachment(attachment_id, description="新描述")
Then 系統更新附件描述
And 回傳成功訊息

### Requirement: delete_project_attachment
系統 SHALL 提供 MCP 工具讓 AI 刪除專案附件。

#### Scenario: 刪除附件
Given 專案有一個附件
When AI 呼叫 delete_project_attachment(attachment_id)
Then 系統刪除附件記錄
And 回傳成功訊息

## MODIFIED Requirements

### Requirement: 擴充分享連結支援 NAS 檔案
現有的 `create_share_link` MCP 工具 SHALL 擴充支援 `project_attachment` resource_type，讓 AI 助手產生專案附件的暫時下載連結。

#### Scenario: 為專案附件建立分享連結
- **GIVEN** 專案有一個附件
- **WHEN** 呼叫 `create_share_link(resource_type="project_attachment", resource_id=附件UUID)`
- **THEN** 系統建立公開分享連結
- **AND** 回傳包含下載 URL 的連結資訊

#### Scenario: 透過分享連結下載專案附件
- **GIVEN** 存在一個 `project_attachment` 類型的分享連結
- **WHEN** 使用者訪問 `/s/{token}` 或 `/api/public/{token}/download`
- **THEN** 系統讀取附件內容並回傳檔案

#### Scenario: 專案附件路徑解析
- **GIVEN** 附件 storage_path 為 `nas://linebot/files/...` 或 `nas://projects/...`
- **WHEN** 系統讀取附件內容
- **THEN** 根據路徑前綴選擇對應的檔案服務讀取
