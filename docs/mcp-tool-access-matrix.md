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

共 38 支工具：未綁定可呼叫 27 支、寫入類 24 支。

| 工具 | 模組 | App 權限 | 未綁定可呼叫 | 寫入 | 身分來源 |
|------|------|----------|--------------|------|----------|
| `codex_image_tool` | `codex_image_tools` | —（未登錄） | 是（未檢查） | 是 | 無 |
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
| `list_scheduled_tasks` | `scheduler_tools` | —（未登錄） | 是（未檢查） | 否 | `ctos_user_id` |
| `manage_scheduled_task` | `scheduler_tools` | —（未登錄） | 是（未檢查） | 是 | `ctos_user_id` |
| `create_share_link` | `share_tools` | —（無需權限） | 是（未檢查） | 是 | 無 |
| `share_knowledge_attachment` | `share_tools` | —（無需權限） | 是（未檢查） | 是 | 無 |
| `run_skill_script` | `skill_script_tools` | —（未登錄） | 是（未檢查） | 否 | `ctos_user_id` |
| `text_to_speech` | `voice_tools` | —（未登錄） | 是（未檢查） | 是 | `ctos_user_id` |
| `browse_webpage` | `web_tools` | —（未登錄） | 是（未檢查） | 否 | `ctos_user_id` |

## 已知缺口（本次未修）

**沒有工具層權限檢查的 18 支**：`codex_image_tool`、`download_web_image`、`add_memory`、`delete_memory`、`get_memories`、`update_memory`、`get_message_attachments`、`summarize_chat`、`generate_md2doc`、`generate_md2ppt`、`generate_presentation`、`list_scheduled_tasks`、`manage_scheduled_task`、`create_share_link`、`share_knowledge_attachment`、`run_skill_script`、`text_to_speech`、`browse_webpage`。這些工具連 `check_mcp_tool_permission()` 都沒呼叫，`TOOL_APP_MAPPING` 的對應只是裝飾，未綁定者只要模型肯呼叫就跑得動。#205 處理分享那兩支，其餘尚未有 issue。

**完全不在 `TOOL_APP_MAPPING` 的模組（5 個）**：`codex_image_tools`、`scheduler_tools`、`skill_script_tools`、`voice_tools`、`web_tools`。新增工具沒登錄 registry 就等於不檢查，預設是開的。

**未綁定可呼叫又會寫入／送出的 17 支**：`codex_image_tool`、`download_web_image`、`add_memory`、`delete_memory`、`update_memory`、`generate_md2doc`、`generate_md2ppt`、`generate_presentation`、`prepare_print_file`、`manage_scheduled_task`、`create_share_link`、`share_knowledge_attachment`、`text_to_speech` 沒有第二道關卡（例如 `prepare_print_file` 會把檔案送進印表機佇列）；`add_attachments_to_knowledge`、`delete_knowledge_item`、`update_knowledge_attachment`、`update_knowledge_item` 還有條目層級 `_check_item_access()` 擋著，未綁定實際上寫不進去。

**bot 身分還是模型說了算的 6 支**：`add_note`、`add_note_with_attachments`、`search_knowledge`、`get_message_attachments`、`summarize_chat`、`send_nas_file`。這些工具收 `line_group_id`／`line_user_id` 但沒接 `resolve_bot_identity()`，已綁定的使用者可以宣稱別的群組，把筆記寫進別的專案範圍或讀到別的群組的訊息附件。修法與 #204 相同，不在這支 PR 的範圍。

**網頁聊天不注入身分**：`api/ai.py` 的 Socket.IO `ai_message` 走 `call_ai()` 時沒有帶 `ctos_user_id` 也沒有帶 `extra_mcp_env`（雖然 session 裡就有 `user_id`），那條路會起一個沒有任何身分環境變數的 MCP 子行程：工具的 `ctos_user_id` 由模型參數決定、記憶工具吃模型帶的 id、`update_memory`／`delete_memory` 沒有擁有者範圍。進 socket 之前有 session 認證，所以不是匿名者能打的路，但同一個登入者可以指定別人的 id。
