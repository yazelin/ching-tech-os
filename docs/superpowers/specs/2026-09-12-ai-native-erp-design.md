# CTOS 往來與物料模組（AI native 類 ERP，取代 ERPNext）設計

日期：2026-09-12
狀態：規格草案；設計原則已由管理層定（AI Agent 能操作為第一優先），其餘假設列在第八節
上位規格：`2026-09-10-ctos-web-react-frontend-design.md`（第五節「ERPNext 資料搬出」）、`2026-09-11-project-module-design.md`（專案模組，已上線）

## 一、背景與原則

管理層決定停用 ERPNext，改用自建、不複雜、AI native 的類 ERP 模組管理原本放在 ERPNext 的資訊。盤點（2026-09-12，見 `docs/erpnext-backup.md` 與 ai_logs）顯示 ERPNext 真正在用的只有主檔與少量採購：

| 資料 | 筆數 | bot 半年呼叫 |
|---|---|---|
| Supplier／Customer／Contact／Address | 665／419／951／1041 | 查 90 次、建供應商 17 次 |
| Item／Warehouse／Bin（餘額）／Stock Ledger | 118／5／77／80 | 查物料 62、查庫存 68 |
| Purchase Order | 17 | 查 8（只在 2 月） |
| Project／Task | 10／76 | 已由專案模組取代 |
| 其他單據（SO、DN、發票、報價） | 各 1 或 0 | 無 |

**原則（管理層定）**：使用者透過 LINE 或新前端向 AI Agent 提出需求，功能由 AI 操作為第一優先；新前端的 CRUD 畫面是第二介面。落到設計上：

1. **MCP 工具是主要 API**。每個功能先做成 MCP 工具（bot 與 web 助手共用），REST 端點只服務新前端畫面，兩者呼叫同一層 service。
2. **工具的輸入容忍自然語言**：名稱模糊比對、別名、「上週」「這個月」這類日期，都在 service 層解析，不要求 agent 先查 id。
3. **寫入前確認**：agent 建立或修改主檔、開採購單、調庫存，回覆時附上「我建了／改了什麼」，可逆（有 audit 與軟刪除）。
4. **每筆資料都可被 agent 讀成上下文**：往來對象頁、物料頁提供「AI 摘要」工具，聚合相關專案、採購、知識庫條目。
5. **不做**：會計分錄、發票、稅務、報價／銷售單據、BOM、多公司、多幣別。

## 二、範圍與資料模型

三塊，掛在既有的 `vendor-management`（廠商管理）與 `inventory-management`（物料管理）兩個 app id 下（`DEFAULT_APP_PERMISSIONS` 已有、預設 True）。Alembic migration 030 起，全部 uuid 主鍵、`created_at`／`updated_at`、`created_by`、軟刪除 `deleted_at`。

### 往來對象（vendor-management）

- `parties`：`name`、`short_name`、`aliases text[]`（模糊比對用）、`is_supplier`、`is_customer`、`tax_id`（統編）、`industry`、`payment_terms`、`notes`、`source_ref`（ERPNext 的 Supplier／Customer name，匯入對照）。一家公司同時是供應商與客戶只有一筆。
- `party_contacts`：`party_id`、`name`、`title`、`phone`、`mobile`、`email`、`is_primary`、`notes`。
- `party_addresses`：`party_id`、`label`（公司／工廠／收貨）、`address`、`city`、`is_primary`。
- 搜尋：`name`、`short_name`、`aliases`、聯絡人姓名、電話、統編都進 `pg_trgm` 索引；工具回傳前三個候選讓 agent 挑或問人。

### 物料與庫存（inventory-management）

- `items`：`code`（唯一）、`name`、`spec`、`unit`、`item_group`、`default_supplier_id → parties`、`purchase_price`、`lead_days`、`aliases text[]`、`notes`、`source_ref`。
- `warehouses`：`code`、`name`。
- `stock_balances`：`item_id`、`warehouse_id`、`qty numeric`、unique(item, warehouse)。
- `stock_movements`：`item_id`、`warehouse_id`、`qty_delta`、`reason`（`receipt`、`issue`、`adjust`、`transfer_in`、`transfer_out`、`import`）、`ref_type`／`ref_id`（採購單收貨等）、`note`、`actor_user_id`。**餘額由 movements 累計，同交易更新 balances**；這就是簡化版分類帳，不做成本、不做批號。

### 採購（inventory-management）

- `purchase_orders`：`po_no`（`PO-YYYYMM-NNN` 自動）、`supplier_id → parties`、`project_id → projects` 可空、`status`（`draft`、`ordered`、`partial`、`received`、`cancelled`）、`order_date`、`expected_date`、`notes`。
- `purchase_order_lines`：`po_id`、`item_id`、`description`、`qty`、`unit_price`、`received_qty`。
- 收貨：對某幾行填 `received_qty` → 產生 `stock_movements(reason=receipt)` → 更新餘額 → 全收改 `received`、部分改 `partial`。

### 稽核

- `erp_audit`：`entity_type`、`entity_id`、`action`、`diff jsonb`、`actor_user_id`、`via`（`mcp`／`rest`）、`agent_name`、`created_at`。所有寫入 service 一律寫一筆；agent 寫入的 `actor_user_id` 來自 bot 綁定或 socket 身分（#189 的機制）。

## 三、MCP 工具（主要 API，`services/mcp/erp_tools.py`，註冊在 ching-tech-os 自己的 MCP server）

工具名稱短、動詞開頭、參數用自然欄位。全部經 `TOOL_APP_MAPPING` 掛到對應 app id。

**往來對象**
- `find_party(query, role?)`：模糊找（名稱、別名、聯絡人、電話、統編），回候選清單（id、名稱、角色、主要聯絡人）。
- `get_party(party_id | name)`：完整資料＋聯絡人＋地址＋近期採購單＋相關專案（bot_groups／projects 的關聯）＋知識庫條目數。
- `create_party(name, is_supplier?, is_customer?, contacts?, addresses?, ...)`、`update_party(party_id, fields)`、`add_party_contact(...)`、`add_party_address(...)`、`merge_parties(keep_id, drop_id)`（重複主檔合併，17 次 bot 建檔多半會撞重複）。

**物料與庫存**
- `find_item(query)`：料號、品名、別名、規格模糊找。
- `get_item(item_id | code)`：主檔＋各倉餘額＋最近異動＋預設供應商。
- `create_item(...)`、`update_item(...)`。
- `get_stock(item | code, warehouse?)`：餘額；`adjust_stock(item, warehouse, qty_delta, reason, note)`；`transfer_stock(item, from, to, qty)`。

**採購**
- `create_purchase_order(supplier, lines[{item, qty, unit_price?}], project?, expected_date?)`：supplier／item 都吃名稱，解析不到就回候選要 agent 確認。
- `get_purchase_order(po_no | id)`、`list_purchase_orders(supplier?, status?, project?, since?)`。
- `receive_purchase_order(po, lines[{item, qty}] | all=true, warehouse?)`：收貨入庫。
- `cancel_purchase_order(po, reason)`。

**文件擷取（AI native 的核心）**
- `extract_party_from_document(file_path)`、`extract_purchase_order_from_document(file_path)`：bot 收到名片照片、詢價單／報價單 PDF 時，agent 先用既有的讀圖／`convert_pdf_to_images` 看內容，再呼叫這兩個工具把結構化欄位丟進來做「草稿」（回傳含候選重複主檔的比對結果），人確認後 agent 再呼叫 `create_*`。工具本身不呼叫模型，擷取由 agent 完成；這樣不多一條模型呼叫鏈，也讓 AI Log 看得到擷取過程。

**摘要**
- `summarize_party(party_id)`、`summarize_item(item_id)`：把關聯資料組成一段給 agent 的上下文（不是模型生成，是聚合），供 agent 回答「鴻佰最近有什麼往來」。

每個工具回傳都含 `audit_id`，agent 回覆可引用。

## 四、REST（只服務新前端）

`/api/parties`、`/api/items`、`/api/warehouses`、`/api/stock`、`/api/purchase-orders`，清單／明細／建立／更新／軟刪除，與 MCP 工具共用 service。權限：讀要對應 app 權限；寫入同樣（管理層要「AI 操控第一」，所以不再細分成員制，app 權限開了就能寫；admin 一律過）。

## 五、新前端（ctos-web）

1. **AI 助手頁**（`/assistant`）：新前端目前沒有對話介面，「透過 web UI 向 AI Agent 請求」需要它。用既有 Socket.IO `ai_chat_event`（#186 後帶 token 握手）、既有 chats 資料表；畫面照 AI Log 明細的工具時間軸顯示 agent 做了什麼。這是本 spec 的一部分，排在往來對象之前做。
2. **往來對象** `/parties`：清單（搜尋、供應商／客戶篩選）、明細（聯絡人、地址、採購單、相關專案、知識庫、AI 摘要）、新增／編輯、合併。
3. **物料與庫存** `/items`：清單、明細（各倉餘額、異動紀錄、預設供應商）、新增／編輯、調整庫存對話框。
4. **採購單** `/purchase-orders`：清單（狀態、供應商、專案篩選）、明細（行項、收貨）、新增。
5. 首頁 dashboard 加一張「採購待收貨」卡（ordered／partial 的單數與最近到期）。
6. 每頁右上「問 AI」按鈕帶著當前實體開 AI 助手（例如「這家供應商最近的採購」）。

## 六、從 ERPNext 遷移

- 來源：`/mnt/nas/ctos/erpnext-backup/<日期>/doctypes/*.json`（每日備份已上線）。
- `scripts/erpnext_import.py`：Supplier＋Customer → parties（同名合併、`source_ref` 記來源）；Contact／Address 依 Dynamic Link 掛到 party；Item → items（Item Default 的預設供應商、Item Price 的採購價）；Warehouse → warehouses；Bin → `stock_movements(reason=import)` 產生初始餘額；Purchase Order（未完成的）→ purchase_orders；Project／Task 已在專案模組，若尚未匯入一併做。冪等：以 `source_ref` 為 key，可重跑。
- 匯入在正式機執行一次，之後 ERPNext 只讀，過渡期兩週。

## 七、bot 與舊程式的切換

- `linebot_agents.py` 與正式庫 `ai_prompts`（linebot-group、linebot-personal）三段 ERPNext 指引改成新工具指引（migration 改 DB prompt）。
- `skills/inventory`、`skills/project`（core）與 `extends/erpnext/skills/*` 改為新工具或移除；`extends/erpnext` 整個 submodule 在停用後移除，`/api/erp` proxy 與 ctos CLI `erp` 子命令改打新端點（`ctos erp find/item/stock` 語意保留）。
- 舊桌面 ERPNext 圖示移除；`.env` 三個 ERPNEXT 變數與 MCP server 註冊在停用時拿掉。
- 停用步驟：匯入完成並核對 → bot 切新工具 → 觀察兩週 → 停 ERPNext 容器（volume 保留四週）→ 刪。

## 八、假設（換一種就會做出不同東西的已列成問題）

- 供應商與客戶合併成一張 parties。
- 庫存做簡化分類帳（movements 累計餘額），不做成本與批號。
- 採購單第一版就做（agent 開單、收貨入庫），但不做請購、詢價比價、發票。
- 文件擷取由 agent 自己讀圖，工具只收結構化結果做草稿與去重。
- 寫入權限＝app 權限，不做成員制。
- 專案與採購單的關聯用 `project_id`，不反向在專案頁做採購分頁（第一版只在採購單列專案名）。
- 新前端 AI 助手頁沿用既有 chats 與 socket 事件，不另做後端。

## 九、待 yazelin 拍板

1. **採購單狀態要不要「請購／核准」**？預設不做核准流程，agent 建了就是 ordered。
2. **庫存要不要金額**（平均成本）？預設不做，只有數量與採購價參考。
3. **AI 助手頁要不要對所有人開**？預設跟舊桌面 `ai-assistant` app 權限（預設開放）。

## 十、PR 切法（每支 implement → review → fix → re-review，後端合併即停不部署）

1. 後端：migration 030（parties／items／warehouses／stock／purchase／audit）＋ service ＋ MCP 工具 ＋ REST ＋ 測試。
2. `scripts/erpnext_import.py` ＋ 在本機用備份 JSON 驗證匯入。
3. ctos-web：AI 助手頁。
4. ctos-web：往來對象。
5. ctos-web：物料與庫存。
6. ctos-web：採購單 ＋ 首頁待收貨卡。
7. bot prompt／skills 切換 ＋ CLI ＋ 舊桌面圖示 ＋ 文件（含正式庫 prompt migration）。
8. 停用 ERPNext（部署與資料匯入要 yazelin 授權）。
