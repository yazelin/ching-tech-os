# Change: 強化 add_note MCP 工具支援附件

## Why
目前 Line Bot AI 透過 `add_note` MCP 工具新增知識庫筆記時，只能加入純文字內容。當用戶傳送圖片並要求儲存到知識庫時，AI 無法將這些圖片一併加入附件區。例如 KB002 筆記提到多張圖片，但這些圖片未被正確附加。

此外，用戶也需要能夠更新現有知識庫的附件（例如為既有知識補充圖片），目前的 `update_knowledge_item` 工具也不支援此功能。

## What Changes
- 新增 `get_message_attachments` MCP 工具，讓 AI 能查詢訊息的附件資訊
- 新增 `add_note_with_attachments` MCP 工具，支援同時傳入附件列表
- 新增 `add_attachments_to_knowledge` MCP 工具，支援為現有知識新增附件
- 附件來源為 Line Bot 已儲存的 NAS 檔案路徑（從 `line_files` 表取得）

## Impact
- Affected specs: `knowledge-base`
- Affected code:
  - `backend/src/ching_tech_os/services/mcp_server.py` - 新增/修改 MCP 工具
  - `backend/src/ching_tech_os/services/knowledge.py` - 新增從 NAS 複製附件功能
  - `backend/src/ching_tech_os/services/linebot.py` - 新增查詢訊息附件功能
