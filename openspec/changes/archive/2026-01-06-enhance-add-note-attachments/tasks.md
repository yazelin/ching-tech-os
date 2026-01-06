# 實作任務清單

## 1. 新增 MCP 工具 `get_message_attachments`
- [x] 1.1 在 `mcp_server.py` 新增 `get_message_attachments` 工具函數
  - 參數：line_user_id、line_group_id、days、file_type、limit
  - 查詢 `line_files` 表取得附件記錄
- [x] 1.2 格式化返回結果（序號、類型、時間、NAS 路徑）

## 2. 新增 MCP 工具 `add_note_with_attachments`
- [x] 2.1 在 `mcp_server.py` 新增 `add_note_with_attachments` 工具函數
  - 參數：title、content、attachments（NAS 路徑列表）、category、topics、project
- [x] 2.2 在 `knowledge.py` 新增 `copy_linebot_attachment_to_knowledge` 函數
  - 從 Line Bot NAS 讀取檔案
  - 依大小存到本機或知識庫 NAS
  - 返回 KnowledgeAttachment
- [x] 2.3 整合建立知識庫與附件流程
  - 先建立知識庫筆記
  - 依序處理附件
  - 處理部分失敗的情況

## 3. 新增 MCP 工具 `add_attachments_to_knowledge`
- [x] 3.1 在 `mcp_server.py` 新增 `add_attachments_to_knowledge` 工具函數
  - 參數：kb_id、attachments（NAS 路徑列表）
  - 複用 `copy_linebot_attachment_to_knowledge` 函數
