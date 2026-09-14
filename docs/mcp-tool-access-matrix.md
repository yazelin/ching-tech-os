# MCP 工具存取矩陣

> 本檔由 `backend/scripts/gen_tool_access_matrix.py` 從程式內省產生，**不要手改**。
> 改了工具或權限 registry 之後重跑一次；
> `backend/tests/test_mcp_tool_access_matrix.py` 會比對逐字相同，漂移就紅。

## 共同根因

這套權限設計假設呼叫者是已綁定的自己人，但 bot 對外開放，未綁定者一路走得進來。
下面這些 issue 都是同一個根因的不同出口：

| Issue | 出口 | 狀態 |
|-------|------|------|
| #201 | 未綁定者可查專案／往來對象／物料／NAS 檔案（app 預設開放） | 已修（PR #206，`APPS_REQUIRE_BOUND_USER`） |
| #207 | 未綁定者可用 `add_note`／`add_note_with_attachments` 寫進全域知識庫 | 已修（工具內部自檢 `TOOLS_REQUIRE_BOUND_USER`） |
| #204 | 記憶工具直接吃模型帶的 `line_group_id`／`line_user_id`，可冒充別的群組／別人 | 已修（`resolve_bot_identity`，伺服器注入優先） |
| #205 | 分享工具（`create_share_link`／`share_knowledge_attachment`）可把任何知識條目／NAS 檔案變成公開連結 | 已修（`share-manager` 進 `APPS_REQUIRE_BOUND_USER` ＋ `share.check_resource_access()`） |
| #209 | 知識庫／NAS／訊息工具還吃模型帶的 `line_group_id`／`line_user_id`，可寫進別的專案範圍、把檔案推到別的群組、讀別的群組的對話 | 已修（`resolve_bot_identity()` ＋ 讀對話類走 `resolve_conversation_scope()`） |
| #210 | 十幾支工具連 `check_mcp_tool_permission()` 都沒呼叫，`TOOL_APP_MAPPING` 只是裝飾 | 已修（逐支對到 app，或登記進 `TOOLS_INTENTIONALLY_OPEN` 並寫明理由） |

四道關卡各擋不同的東西，缺一不可：

1. **app 權限**（`check_mcp_tool_permission`）：擋「這個人有沒有這個功能」。
2. **條目層級**（知識庫的 `_check_item_access`、記憶的擁有者條件）：擋「這一筆是不是你的」。
3. **工具內部自檢**（`require_bound_user`）：擋「憑空建立新資料」——沒有既有條目可比對的寫入。
4. **資源存取檢查**（`share.check_resource_access`）：擋「把讀不到的東西送出去」——
   建立公開連結前，knowledge 走 `check_knowledge_permission_async(..., action="read")`、
   nas_file 走帶 `source_permissions` 的 `validate_nas_file_path()`，與讀取工具同一條路。

## 欄位說明

- **App 權限**：`TOOL_APP_MAPPING` 的對應。`—（無需權限）` 表示 registry 明確標成
  不需要特定權限；`—（未登錄）` 表示這支工具根本不在 registry 裡，等同不檢查。
- **未綁定可呼叫**：LINE／Telegram 使用者沒有綁定 CTOS 帳號（`ctos_user_id is None`）時的結果。
  `否` 表示被擋在工具層；`是` 表示 app 權限這一關放行——知識庫工具還有條目層級
  （`_check_item_access`）在後面擋：未綁定只讀得到 `scope=global` 且 `is_public`
  的條目，對既有條目的寫入一律拒絕。`是（未檢查）` 表示這支工具連
  `check_mcp_tool_permission` 都沒呼叫，app 對應只是裝飾（issue #210 之後應該是空的）；
  `是（登記開放）` 表示這支工具登記在 `permissions.TOOLS_INTENTIONALLY_OPEN`，
  是刻意對未綁定者開放的基礎功能，理由列在表格下方。
- **寫入**：會建立／修改／刪除資料，或產生檔案、對外送出內容。
- **身分來源**：`ctos_user_id` ＝ 伺服器用 `CTOS_USER_ID` 環境變數注入（`mcp.tool`
  包裝層強制，模型帶什麼都會被覆蓋）；`bot 身分（注入）` ＝ 走 `resolve_bot_identity()`，
  以 `CTOS_BOT_GROUP_ID`／`CTOS_BOT_USER_ID` 為準；`bot 身分（模型參數）` ＝ 工具收
  `line_group_id`／`line_user_id` 但還沒接上注入，模型帶進來的值會被採用（殘留風險，
  見下方「已知缺口」）；`無` ＝ 工具不帶身分。

共 74 支工具：未綁定可呼叫 17 支、寫入類 45 支。

| 工具 | 模組 | App 權限 | 未綁定可呼叫 | 寫入 | 身分來源 |
|------|------|----------|--------------|------|----------|
| `codex_image_tool` | `codex_image_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` |
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
| `add_note` | `knowledge_tools` | `knowledge-base`（知識庫） | 否（工具自檢） | 是 | `ctos_user_id` ＋ bot 身分（注入） |
| `add_note_with_attachments` | `knowledge_tools` | `knowledge-base`（知識庫） | 否（工具自檢） | 是 | `ctos_user_id` ＋ bot 身分（注入） |
| `delete_knowledge_item` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 是 | `ctos_user_id` |
| `get_knowledge_attachments` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 否 | `ctos_user_id` |
| `get_knowledge_item` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 否 | `ctos_user_id` |
| `read_knowledge_attachment` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 否 | `ctos_user_id` |
| `search_knowledge` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 否 | `ctos_user_id` ＋ bot 身分（注入） |
| `update_knowledge_attachment` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 是 | `ctos_user_id` |
| `update_knowledge_item` | `knowledge_tools` | `knowledge-base`（知識庫） | 是 | 是 | `ctos_user_id` |
| `convert_pdf_to_images` | `media_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `download_web_file` | `media_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `download_web_image` | `media_tools` | —（無需權限） | 是（登記開放） | 是 | `ctos_user_id` |
| `add_memory` | `memory_tools` | `memory-manager`（記憶管理） | 是（登記開放） | 是 | bot 身分（注入） |
| `delete_memory` | `memory_tools` | `memory-manager`（記憶管理） | 是（登記開放） | 是 | bot 身分（注入） |
| `get_memories` | `memory_tools` | `memory-manager`（記憶管理） | 是（登記開放） | 否 | bot 身分（注入） |
| `update_memory` | `memory_tools` | `memory-manager`（記憶管理） | 是（登記開放） | 是 | bot 身分（注入） |
| `get_message_attachments` | `message_tools` | —（無需權限） | 是（登記開放） | 否 | `ctos_user_id` ＋ bot 身分（注入） |
| `summarize_chat` | `message_tools` | —（無需權限） | 是（登記開放） | 否 | `ctos_user_id` ＋ bot 身分（注入） |
| `archive_to_library` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `get_nas_file_info` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `list_library_folders` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `prepare_file_message` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `read_document` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `search_nas_files` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `send_nas_file` | `nas_tools` | `file-manager`（檔案管理） | 否（需綁定） | 是 | `ctos_user_id` ＋ bot 身分（注入） |
| `generate_md2doc` | `presentation_tools` | `md2doc`（文件生成） | 否（工具自檢） | 是 | `ctos_user_id` |
| `generate_md2ppt` | `presentation_tools` | `md2ppt`（簡報生成） | 否（工具自檢） | 是 | `ctos_user_id` |
| `generate_presentation` | `presentation_tools` | `md2ppt`（簡報生成） | 否（工具自檢） | 是 | `ctos_user_id` |
| `prepare_print_file` | `presentation_tools` | `printer`（列印） | 否（需綁定） | 是 | `ctos_user_id` |
| `add_project_member` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `complete_milestone` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `create_milestone` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `create_task` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `find_project` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `get_project` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `list_overdue_milestones` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `list_tasks` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `update_task` | `project_tools` | `project-management`（專案管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `list_scheduled_tasks` | `scheduler_tools` | `task-scheduler`（排程管理） | 否（需綁定） | 否 | `ctos_user_id` |
| `manage_scheduled_task` | `scheduler_tools` | `task-scheduler`（排程管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `create_share_link` | `share_tools` | `share-manager`（分享管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `share_knowledge_attachment` | `share_tools` | `share-manager`（分享管理） | 否（需綁定） | 是 | `ctos_user_id` |
| `run_skill_script` | `skill_script_tools` | `ai-assistant`（AI 助手） | 否（工具自檢） | 否 | `ctos_user_id` |
| `text_to_speech` | `voice_tools` | —（無需權限） | 是（登記開放） | 是 | `ctos_user_id` |
| `browse_webpage` | `web_tools` | —（無需權限） | 是（登記開放） | 否 | `ctos_user_id` |

## 有意對未綁定開放的工具（issue #210）

來源：`services/permissions.py` 的 `TOOLS_INTENTIONALLY_OPEN`。這裡列的是「看過、決定要開」，不是「還沒看」——沒登記又沒呼叫 `check_mcp_tool_permission()` 的工具，矩陣測試會紅。

| 工具 | 理由 |
|------|------|
| `add_memory` | 記憶是 bot 的基礎功能；範圍由伺服器注入的連線身分決定（issue #204），未綁定者只寫得到自己這條對話的記憶。 |
| `browse_webpage` | 只讀公開的 HTTPS 網頁並回傳文字。`web_tools.check_public_http_target()` 會拒絕 loopback／私有／link-local／CGNAT／unique-local 位址、無點主機名稱與 .local／.internal／.lan 這類內網後綴（DNS 解析結果有任何一個非公開就拒絕），並套在三個地方：最初的 URL、`page.route()` 攔到的每一個 request URL（擋重新導向與 subresource）、以及 `page.goto()` 之後真正落地的 `page.url`。未封死：本地檢查與瀏覽器是兩次獨立 DNS 解析，中間換答案（DNS rebinding）仍有空隙。 |
| `delete_memory` | 記憶是 bot 的基礎功能；SQL 帶注入身分的擁有者條件，刪不到別人的記憶（issue #204）。 |
| `download_web_image` | 只把外部 URL 的圖片抓進 /tmp 暫存區回給同一條對話，不讀也不寫 NAS、知識庫或使用者資料。 |
| `get_memories` | 記憶是 bot 的基礎功能；只讀得到注入身分底下的記憶（issue #204）。 |
| `get_message_attachments` | 附件查詢是 bot 的基礎功能；與 summarize_chat 同一條身分解析，bot 路徑靠 `CTOS_BOT_*` 注入、網頁路徑靠 `CTOS_USER_ID` 注入＋驗群組關聯（issue #209、#231）。 |
| `summarize_chat` | 群組摘要是 bot 的基礎功能；bot 路徑有身分注入，只讀得到自己這個群組。網頁聊天沒有 bot 注入，改要求伺服器注入的 `ctos_user_id`（issue #231 起由 `api/ai.py` 從 session 帶入）並驗群組關聯才放行（issue #209）。 |
| `text_to_speech` | 語音回覆是基礎對話功能；語音設定用伺服器注入的 CTOS_USER_ID／CTOS_GROUP_ID 查，模型參數影響不到，輸出只有音檔。 |
| `update_memory` | 記憶是 bot 的基礎功能；SQL 帶注入身分的擁有者條件，改不到別人的記憶（issue #204）。 |

## 已知缺口

**沒有工具層權限檢查、也沒登記開放的工具**：無（issue #210）。每一支不呼叫 `check_mcp_tool_permission()` 的工具都登記在 `TOOLS_INTENTIONALLY_OPEN`，理由見上一節。

**完全不在 `TOOL_APP_MAPPING` 的模組**：無。但新增工具沒登錄 registry 還是等於不檢查，預設是開的——加工具時要一起決定。

**未綁定可呼叫又會寫入／送出的 9 支**：`download_web_image`、`add_memory`、`delete_memory`、`update_memory`、`text_to_speech` 沒有 app 權限這一關（都登記在 `TOOLS_INTENTIONALLY_OPEN`：記憶靠注入身分分範圍，其餘只寫得到 `/tmp` 暫存區）；`add_attachments_to_knowledge`、`delete_knowledge_item`、`update_knowledge_attachment`、`update_knowledge_item` 還有條目層級 `_check_item_access()` 擋著，未綁定實際上寫不進去。

**bot 身分還是模型說了算的工具**：無（issue #209）。收 `line_group_id`／`line_user_id` 的工具都先過 `resolve_bot_identity()`，**有注入時**（LINE／Telegram）模型帶的 id 一律被覆蓋。讀群組對話／附件的兩支再多一層 `resolve_conversation_scope()`：沒有 bot 注入時要有 `ctos_user_id` 且與該群組有既有關聯才放行。網頁聊天的 `CTOS_USER_ID` 自 issue #231 起由 `api/ai.py` 從 session 注入，所以這一關在網頁端拿到的是伺服器驗過的身分，不是模型帶的值（見下方「網頁聊天的身分注入」）。

**`send_nas_file` 的 `telegram_chat_id` 不在注入範圍**（issue #232）：`build_bot_mcp_env()` 注入的是 `CTOS_BOT_GROUP_ID`／`CTOS_BOT_USER_ID`／`CTOS_BOT_PLATFORM`，Telegram 的 chat id 本身仍由模型參數決定。跨平台那一半已經擋掉（連線不是 Telegram 對話時模型帶的 chat id 一律忽略），剩下的是 Telegram 對話裡模型仍可指定同平台的別的 chat id。

**網頁聊天的身分注入**（issue #231 已修）：`api/ai.py` 的 Socket.IO `ai_chat_event`／`compress_chat` 走 `call_ai()` 時帶 `ctos_user_id=session.user_id`，值取自進入事件時重新驗過的 session，不從 request body 也不從模型參數取；`call_ai()` 把它變成 MCP 子行程的 `CTOS_USER_ID`，`resolve_ctos_user_id()` 只認這個環境變數，模型在工具參數裡宣稱別人的 id 不算數。bot 專屬的 `CTOS_BOT_PLATFORM`／`CTOS_BOT_GROUP_ID`／`CTOS_BOT_USER_ID` 不注入網頁端（網頁聊天沒有對應的對話身分）。剩下的是記憶工具：`add_memory`／`get_memories`／`update_memory`／`delete_memory` 的範圍是 bot 對話身分，網頁端沒有可注入的值，仍然吃模型帶的 `line_group_id`／`line_user_id`，不在 issue #231 的範圍內。
