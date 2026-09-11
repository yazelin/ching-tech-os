# MCP 工具存取矩陣

> 本檔由 `backend/scripts/gen_tool_access_matrix.py` 從程式內省產生，**不要手改**。
> 改了工具或權限 registry 之後重跑一次；
> `backend/tests/test_mcp_tool_access_matrix.py` 會比對逐字相同，漂移就紅。

## 共同根因

這套權限設計假設呼叫者是已綁定的自己人，但 bot 對外開放，未綁定者一路走得進來。
四個 issue 都是同一個根因的不同出口：

| Issue | 出口 | 狀態 |
|-------|------|------|
| #201 | 未綁定者可查專案／往來對象／物料／NAS 檔案（app 預設開放） | 已修（PR #206，`APPS_REQUIRE_BOUND_USER`） |
| #207 | 未綁定者可用 `add_note`／`add_note_with_attachments` 寫進全域知識庫 | 已修（工具內部自檢 `TOOLS_REQUIRE_BOUND_USER`） |
| #204 | 記憶工具直接吃模型帶的 `line_group_id`／`line_user_id`，可冒充別的群組／別人 | 已修（`resolve_bot_identity`，伺服器注入優先） |
| #205 | 分享工具（`create_share_link`／`share_knowledge_attachment`）的範圍 | 未處理，另一支 PR |

三道關卡各擋不同的東西，缺一不可：

1. **app 權限**（`check_mcp_tool_permission`）：擋「這個人有沒有這個功能」。
2. **條目層級**（知識庫的 `_check_item_access`、記憶的擁有者條件）：擋「這一筆是不是你的」。
3. **工具內部自檢**（`require_bound_user`）：擋「憑空建立新資料」——沒有既有條目可比對的寫入。

## 欄位說明

- **App 權限**：`TOOL_APP_MAPPING` 的對應。`—（無需權限）` 表示 registry 明確標成
  不需要特定權限；`—（未登錄）` 表示這支工具根本不在 registry 裡，等同不檢查。
- **未綁定可呼叫**：LINE／Telegram 使用者沒有綁定 CTOS 帳號（`ctos_user_id is None`）時的結果。
  `否` 表示被擋在工具層；`是` 表示 app 權限這一關放行——知識庫工具還有條目層級
  （`_check_item_access`）在後面擋：未綁定只讀得到 `scope=global` 且 `is_public`
  的條目，對既有條目的寫入一律拒絕。`是（未檢查）` 表示這支工具連
  `check_mcp_tool_permission` 都沒呼叫，app 對應只是裝飾。
- **寫入**：會建立／修改／刪除資料，或產生檔案、對外送出內容。
- **身分來源**：`ctos_user_id` ＝ 伺服器用 `CTOS_USER_ID` 環境變數注入（`mcp.tool`
  包裝層強制，模型帶什麼都會被覆蓋）；`bot 身分（注入）` ＝ 走 `resolve_bot_identity()`，
  以 `CTOS_BOT_GROUP_ID`／`CTOS_BOT_USER_ID` 為準；`bot 身分（模型參數）` ＝ 工具收
  `line_group_id`／`line_user_id` 但還沒接上注入，模型帶進來的值會被採用（殘留風險，
  見下方「已知缺口」）；`無` ＝ 工具不帶身分。

## 已知缺口（本次未修）

- `bot 身分（模型參數）` 的工具（`add_note`／`add_note_with_attachments`／
  `search_knowledge`／`send_nas_file`／`get_message_attachments`／`summarize_chat`）
  仍以模型帶的 `line_group_id`／`line_user_id` 決定範圍。已綁定的使用者可以宣稱
  別的群組，藉此把筆記寫進別的專案範圍或讀到別的群組的訊息。修法與 #204 相同
  （接 `resolve_bot_identity()`），但不在這支 PR 的範圍。
- `是（未檢查）` 的工具（分享、排程、語音、生圖、`download_web_image`、
  `generate_*`）連 app 權限都沒檢查，未綁定者只要模型肯呼叫就跑得動。#205 處理
  分享那兩支，其餘尚未有 issue。

共 74 支工具：未綁定可呼叫 27 支、寫入類 45 支。

| 工具 | 模組 | App 權限 | 未綁定可呼叫 | 寫入 | 身分來源 |
|------|------|----------|--------------|------|----------|
| `codex_image_tool` | `codex_image_tools` | —（未登錄） | 是（未檢查） | 是 | 無 |
| `add_party_address` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `add_party_contact` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `adjust_stock` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `cancel_purchase_order` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `create_item` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `create_party` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `create_purchase_order` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `delete_party_address` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `delete_party_contact` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `extract_party_from_document` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `extract_purchase_order_from_document` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `find_item` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `find_party` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `get_item` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `get_party` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `get_purchase_order` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `get_stock` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `list_purchase_orders` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `merge_parties` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `receive_purchase_order` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `summarize_item` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `summarize_party` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `transfer_stock` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `update_item` | `erp_tools` | `inventory-management`（物料管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `update_party` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `update_party_address` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `update_party_contact` | `erp_tools` | `vendor-management`（廠商管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `add_attachments_to_knowledge` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 是 | `ctos_user_id` |
| `add_note` | `knowledge_tools` | `knowledge-base`（知識庫） | 否（工具自檢） | 是 | `ctos_user_id` ＋ bot 身分（模型參數） |
| `add_note_with_attachments` | `knowledge_tools` | `knowledge-base`（知識庫） | 否（工具自檢） | 是 | `ctos_user_id` ＋ bot 身分（模型參數） |
| `delete_knowledge_item` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 是 | `ctos_user_id` |
| `get_knowledge_attachments` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 否 | `ctos_user_id` |
| `get_knowledge_item` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 否 | `ctos_user_id` |
| `read_knowledge_attachment` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 否 | `ctos_user_id` |
| `search_knowledge` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 否 | `ctos_user_id` ＋ bot 身分（模型參數） |
| `update_knowledge_attachment` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 是 | `ctos_user_id` |
| `update_knowledge_item` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 是 | `ctos_user_id` |
| `convert_pdf_to_images` | `media_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `download_web_file` | `media_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `download_web_image` | `media_tools` | —（無需權限） | 是（未檢查） | 是 | `ctos_user_id` |
| `add_memory` | `memory_tools` | `memory-manager`（記憶管理） | 是（未檢查） | 是 | bot 身分（注入） |
| `delete_memory` | `memory_tools` | `memory-manager`（記憶管理） | 是（未檢查） | 是 | bot 身分（注入） |
| `get_memories` | `memory_tools` | `memory-manager`（記憶管理） | 是（未檢查） | 否 | bot 身分（注入） |
| `update_memory` | `memory_tools` | `memory-manager`（記憶管理） | 是（未檢查） | 是 | bot 身分（注入） |
| `get_message_attachments` | `message_tools` | —（無需權限） | 是（未檢查） | 否 | bot 身分（模型參數） |
| `summarize_chat` | `message_tools` | —（無需權限） | 是（未檢查） | 否 | bot 身分（模型參數） |
| `archive_to_library` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `get_nas_file_info` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `list_library_folders` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `prepare_file_message` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `read_document` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `search_nas_files` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `send_nas_file` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` ＋ bot 身分（模型參數） |
| `generate_md2doc` | `presentation_tools` | `md2doc`（文件生成） | 是（未檢查） | 是 | `ctos_user_id` |
| `generate_md2ppt` | `presentation_tools` | `md2ppt`（簡報生成） | 是（未檢查） | 是 | `ctos_user_id` |
| `generate_presentation` | `presentation_tools` | `md2ppt`（簡報生成） | 是（未檢查） | 是 | 無 |
| `prepare_print_file` | `presentation_tools` | `printer`（列印） | 是 | 是 | `ctos_user_id` |
| `add_project_member` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `complete_milestone` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `create_milestone` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `create_task` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `find_project` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `get_project` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `list_overdue_milestones` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `list_tasks` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `update_task` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `list_scheduled_tasks` | `scheduler_tools` | —（未登錄） | 是（未檢查） | 否 | `ctos_user_id` |
| `manage_scheduled_task` | `scheduler_tools` | —（未登錄） | 是（未檢查） | 是 | `ctos_user_id` |
| `create_share_link` | `share_tools` | —（無需權限） | 是（未檢查） | 是 | 無 |
| `share_knowledge_attachment` | `share_tools` | —（無需權限） | 是（未檢查） | 是 | 無 |
| `run_skill_script` | `skill_script_tools` | —（未登錄） | 是（未檢查） | 否 | `ctos_user_id` |
| `text_to_speech` | `voice_tools` | —（未登錄） | 是（未檢查） | 是 | `ctos_user_id` |
| `browse_webpage` | `web_tools` | —（未登錄） | 是（未檢查） | 否 | `ctos_user_id` |
