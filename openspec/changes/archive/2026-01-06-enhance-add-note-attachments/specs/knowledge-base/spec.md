## ADDED Requirements

### Requirement: MCP 工具新增筆記含附件
知識庫 MCP 服務 SHALL 提供 `add_note_with_attachments` 工具，支援新增筆記時一併加入附件。

#### Scenario: AI 新增筆記含單一附件
- **WHEN** AI 呼叫 `add_note_with_attachments` 工具
- **AND** 提供 title、content 及一個 NAS 路徑附件
- **THEN** 系統建立知識庫筆記
- **AND** 將附件從 Line Bot NAS 複製到知識庫儲存區
- **AND** 附件記錄於知識元資料的 attachments 欄位
- **AND** 返回成功訊息包含知識 ID

#### Scenario: AI 新增筆記含多個附件
- **WHEN** AI 呼叫 `add_note_with_attachments` 工具
- **AND** 提供多個 NAS 路徑附件（最多 10 個）
- **THEN** 系統建立知識庫筆記
- **AND** 依序處理所有附件
- **AND** 每個附件依大小決定儲存位置（<1MB 本機，>=1MB NAS）

#### Scenario: 附件路徑無效
- **WHEN** AI 呼叫 `add_note_with_attachments` 工具
- **AND** 提供的附件路徑不存在於 NAS
- **THEN** 系統仍建立知識庫筆記
- **AND** 返回警告訊息說明哪些附件無法加入

---

### Requirement: MCP 工具查詢訊息附件
知識庫 MCP 服務 SHALL 提供 `get_message_attachments` 工具，讓 AI 查詢對話中的附件資訊。

#### Scenario: 查詢群組最近附件
- **WHEN** AI 呼叫 `get_message_attachments` 工具
- **AND** 提供 line_group_id 參數
- **THEN** 系統查詢該群組最近 7 天內的附件
- **AND** 返回附件列表包含 NAS 路徑、檔案類型、上傳時間

#### Scenario: 查詢個人聊天附件
- **WHEN** AI 呼叫 `get_message_attachments` 工具
- **AND** 提供 line_user_id 參數
- **THEN** 系統查詢該用戶個人聊天最近 7 天內的附件
- **AND** 返回附件列表

#### Scenario: 自訂查詢時間範圍
- **WHEN** AI 呼叫 `get_message_attachments` 工具
- **AND** 提供 days 參數（如 30）
- **THEN** 系統查詢指定天數範圍內的附件

#### Scenario: 按檔案類型過濾
- **WHEN** AI 呼叫 `get_message_attachments` 工具
- **AND** 提供 file_type 參數（如 "image"）
- **THEN** 系統只返回指定類型的附件

#### Scenario: 附件列表格式
- **WHEN** 系統返回附件列表
- **THEN** 每個附件包含：序號、檔案類型、上傳時間、NAS 路徑
- **AND** 列表按時間由新到舊排序
- **AND** AI 可使用 NAS 路徑作為 `add_note_with_attachments` 的輸入

---

### Requirement: MCP 工具為現有知識新增附件
知識庫 MCP 服務 SHALL 提供 `add_attachments_to_knowledge` 工具，支援為現有知識新增附件。

#### Scenario: 為現有知識新增附件
- **WHEN** AI 呼叫 `add_attachments_to_knowledge` 工具
- **AND** 提供 kb_id 及 attachments 參數（NAS 路徑列表）
- **THEN** 系統將附件從 Line Bot NAS 複製到知識庫儲存區
- **AND** 附件加入該知識的 attachments 欄位
- **AND** 更新 updated_at 時間戳

#### Scenario: 知識不存在
- **WHEN** AI 呼叫 `add_attachments_to_knowledge` 工具
- **AND** 提供的 kb_id 不存在
- **THEN** 系統返回錯誤訊息「找不到知識」

#### Scenario: 部分附件失敗
- **WHEN** AI 呼叫 `add_attachments_to_knowledge` 工具
- **AND** 部分附件路徑無效
- **THEN** 系統仍加入有效的附件
- **AND** 返回警告訊息說明哪些附件無法加入
