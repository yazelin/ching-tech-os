# 實作任務清單

## 1. 擴展 get_knowledge_item 顯示附件
- [x] 1.1 修改 `mcp_server.py` 的 `get_knowledge_item` 函數
  - 從 `kb_service.get_knowledge()` 取得附件資訊
  - 在輸出中加入附件列表（索引、類型、檔名、描述）

## 2. 新增 get_knowledge_attachments MCP 工具
- [x] 2.1 在 `mcp_server.py` 新增 `get_knowledge_attachments` 工具
  - 參數：`kb_id`（必填）
  - 返回格式化的附件列表

## 3. 新增 update_knowledge_attachment MCP 工具
- [x] 3.1 在 `mcp_server.py` 新增 `update_knowledge_attachment` 工具
  - 參數：`kb_id`（必填）、`attachment_index`（必填）、`description`（選填）
  - 呼叫 `kb_service.update_attachment()` 更新附件

## 4. 更新 Line Bot Prompt
- [x] 4.1 更新 `linebot_agents.py` 中的 prompt
  - 說明 `get_knowledge_attachments` 工具用法
  - 說明 `update_knowledge_attachment` 工具用法
- [x] 4.2 更新 migration 013 保持一致
- [x] 4.3 更新資料庫中現有的 prompt 內容
