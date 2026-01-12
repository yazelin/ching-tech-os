# Tasks: 專案附件與連結 MCP 工具

## Phase 1: 連結管理 MCP 工具

- [x] 1.1 在 `mcp_server.py` 新增 `add_project_link` 工具
- [x] 1.2 在 `mcp_server.py` 新增 `get_project_links` 工具
- [x] 1.3 在 `mcp_server.py` 新增 `update_project_link` 工具
- [x] 1.4 在 `mcp_server.py` 新增 `delete_project_link` 工具

## Phase 2: 附件管理 MCP 工具

- [x] 2.1 在 `mcp_server.py` 新增 `add_project_attachment` 工具
  - 從 NAS 路徑取得檔案資訊
  - 建立附件記錄（使用 nas:// 路徑格式）
- [x] 2.2 在 `mcp_server.py` 新增 `get_project_attachments` 工具
- [x] 2.3 在 `mcp_server.py` 新增 `update_project_attachment` 工具
- [x] 2.4 在 `mcp_server.py` 新增 `delete_project_attachment` 工具

## Phase 3: AI Prompt 更新

- [x] 3.1 更新 `linebot_agents.py` 中的 LINEBOT_PERSONAL_PROMPT
- [x] 3.2 更新 `linebot_agents.py` 中的 LINEBOT_GROUP_PROMPT
- [x] 3.3 建立 migration 028 更新資料庫中的 prompt

## Phase 4: 分享連結支援

- [x] 4.1 在 `models/share.py` 新增 `project_attachment` 到 `ShareLinkCreate.resource_type`
- [x] 4.2 在 `models/share.py` 新增 `project_attachment` 到 `PublicResourceResponse.type`
- [x] 4.3 在 `mcp_server.py` 的 `create_share_link` 工具新增 `project_attachment` 支援
- [x] 4.4 在 `services/share.py` 新增 `get_project_attachment_info` 函數
- [x] 4.5 在 `services/share.py` 的 `get_resource_title` 新增 `project_attachment` 處理
- [x] 4.6 在 `services/share.py` 的 `get_public_resource` 新增 `project_attachment` 處理
- [x] 4.7 在 `api/share.py` 的 `download_shared_file` 新增 `project_attachment` 下載支援
- [x] 4.8 在 `frontend/js/public.js` 新增 `project_attachment` 頁面渲染

## Phase 5: 路徑修正

- [x] 5.1 修正 `add_project_attachment` 使用 `settings.linebot_local_path` 而非硬編碼路徑
- [x] 5.2 修正 `services/project.py` 的 `get_attachment_content` 支援多種 NAS 路徑格式
  - `nas://projects/...` → 使用 project_file_service
  - `nas://linebot/files/...` → 使用 linebot_file_service
- [x] 5.3 修正 `.env` 中 `LINEBOT_NAS_PATH` 路徑設定

## Phase 6: 測試驗證

- [x] 6.1 透過 Line Bot 測試連結功能
  - 「幫我在專案加一個連結」
  - 「查詢專案的連結」
- [x] 6.2 透過 Line Bot 測試附件功能
  - 發送圖片後「把這張圖加到專案附件」
  - 「查詢專案的附件」
- [x] 6.3 測試專案附件分享連結
  - AI 產生附件分享連結
  - 公開頁面正確顯示附件資訊
  - 下載功能正常運作
