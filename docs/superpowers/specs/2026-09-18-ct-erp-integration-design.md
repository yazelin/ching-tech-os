# CTOS 接上 ct_erp（取代 ERPNext）設計

日期：2026-09-18
狀態：設計完成，等實作計劃
推翻：`2026-09-12-ai-native-erp-design.md`（CTOS 自建類 ERP 模組）
相關知識庫：kb-232（ct_erp OpenAPI 規格）、kb-233（ct_erp 實測狀態）、kb-230（域名與 IP 對照）

## 一、背景

### 現況盤點（2026-09-18 實測，不是推論）

公司有兩套要取代 ERPNext 的東西：

**ct_erp**（`http://ct.erp`，實際位址 192.168.11.6:8000）是自製的進銷存與會計系統，FastAPI、HTTP Basic、OpenAPI 0.1.0、36 條路徑 61 個操作。它是會計正在用的活系統：

| 資料 | 筆數 |
|---|---|
| 傳票 | 118,951 |
| 進貨單 | 48,518 |
| 銷貨單 | 17,744 |
| 付款單 | 12,210 |
| 收款單 | 5,662 |

使用者 5 個：`AI_agent`、`CH2001`、`CH3001`、`CH5002`、`CT`。

**CTOS 自建的類 ERP 模組**（`parties`／`items`／`purchase_orders`，migration 030–033）已經部署在 192.168.11.11，六張表全部 0 筆，匯入腳本（#197）從未執行。

### 目前壞在哪

migration 032 已經把 bot 提示詞從 ERPNext 切到那個空模組，repo 的 CLI `erp find` 也已改打 `/api/items`。所以：

- LINE bot 被問「某某料還有幾個」「某廠商電話」時，會去查空表然後回查不到。
- `ctos erp` 子命令同理（目前只有裝了舊版 CLI 的人還查得到東西，那是意外不是設計）。
- `linebot-personal` 提示詞裡還留著沒改到的舊句「專案任務/採購/庫存/廠商客戶 → ERPNext」，與前半段自相矛盾，而 ERPNext 的 MCP 工具在提示詞裡已不存在。

這個狀態從 2026-09-15 之前就開始了。

### 三個已拍板的前提

1. **ct_erp 是 ERP 的唯一事實來源**，CTOS 自建的三組表與對應 MCP 工具退場。
2. **61 個操作全部包裝**，不在 CTOS 這層挑。
3. **權限分兩層**：進銷存沿用既有的 `inventory-management`／`vendor-management`（預設開），錢帳另開 `ct-erp-finance`（預設關，管理員逐人開）。

## 二、架構

沿用 `extends/erpnext` 已經證明可行的形狀：憑證只放伺服器端，CTOS 負責認證與分人授權，對外只暴露自己的端點。

```
LINE / Telegram bot ─┐
ctos-web AI 助手 ────┼─→ MCP 工具（ct_erp_tools.py）─┐
                     │                                │
ctos CLI ────────────┼─→ REST（/api/ct-erp/*）────────┼─→ ct_erp client
ctos-web 畫面 ───────┘                                │   （httpx + HTTP Basic）
                                                      │            │
                                          CTOS 權限閘門             ↓
                                      （require_app_permission）  http://ct.erp
```

四個層次，各自一個清楚的職責：

| 層 | 檔案 | 負責 |
|---|---|---|
| client | `extends/ct_erp/client.py` | 只管 HTTP：base URL、Basic 認證、逾時、錯誤碼翻譯。不認識 CTOS。 |
| service | `extends/ct_erp/service.py` | 自然語言容忍（名稱模糊解析、日期詞）、回應瘦身、稽核寫入。 |
| MCP 工具 | `extends/ct_erp/mcp_tools.py` | agent 介面，61 個操作對應的工具。 |
| REST | `extends/ct_erp/router.py` | CLI 與前端畫面用，掛 `/api/ct-erp`。 |

**做成 `extends/ct_erp` submodule**，與 `extends/erpnext` 平行，理由是 ERPNext 退場時整包移除比較乾淨，而且 ct_erp 是擎添特有的系統，不該進通用 core。

### 憑證

`.env` 加三個變數，只有伺服器端讀得到：

```
CT_ERP_URL=http://ct.erp
CT_ERP_USER=AI_agent
CT_ERP_PASSWORD=<略>
```

`AI_agent` 是共用服務帳號，ct_erp 那側不分人。**誰做了什麼由 CTOS 這側記**（見第四節稽核）。

`CT_ERP_PASSWORD` 目前與 .11 的 sudo 密碼是同一串，實作前應先換掉其中一組。

## 三、權限模型

### app id 與對應

| app id | 預設 | 涵蓋的 ct_erp 資源 |
|---|---|---|
| `inventory-management` | True | 庫存單、品號目錄、進貨單、銷貨單 |
| `vendor-management` | True | 廠商客戶、聯絡人 |
| `ct-erp-finance` | **False** | 傳票、收款單、付款單、開戶帳號、使用者、操作記錄 |

`ct-erp-finance` 加進 `DEFAULT_APP_PERMISSIONS`（False）與後台使用者管理的開關清單，做法與既有的 `prompt-editor`／`ai-log`／`share-manager` 相同。

### 未綁定者

三個 app id 全部加進 `APPS_REQUIRE_BOUND_USER`。未綁定 CTOS 帳號的 LINE／Telegram 使用者一律拒絕，不做「只讀公開欄位」的折衷——ct_erp 的每一張表都含實名廠商、電話、金額或銀行帳號。

`inventory-management` 與 `vendor-management` 已在該集合內；`ct-erp-finance` 要一起加。

### 刪除類操作

61 個操作含 7 支 DELETE。全部包裝，但：

- 傳票、收付款、開戶帳號的 DELETE 落在 `ct-erp-finance`（預設關），預設沒有人碰得到。
- 進貨單、銷貨單、聯絡人的 DELETE 落在預設開的 app。**MCP 工具層要求二階段確認**：`delete_purchase_order(order_id, confirm_token)`，第一次呼叫不帶 token 時回傳單據摘要與一個一次性 token，agent 必須把摘要講給人看、拿到回覆後才第二次呼叫。ct_erp 沒有這個能力，二階段確認由 CTOS 這層加。

REST 端點不做二階段（前端畫面自己有確認對話框），但同樣掛 app 權限。

## 四、稽核與身分

ct_erp 的 `activity-log` 只記得到 `AI_agent`，對「誰改的」沒有幫助（而且 `AI_agent` 讀不到那支，回 403）。

所有經過 CTOS 的寫入，在 CTOS 這側寫一筆 `erp_audit`（migration 030 已經有這張表，沿用）：`entity_type`、`entity_id`、`action`、`diff jsonb`、`actor_user_id`、`via`（`mcp`／`rest`）、`agent_name`。`actor_user_id` 來自 bot 綁定或 socket 身分，不信模型帶進來的值。

**`erp_audit` 是 migration 030 那批唯一保留的東西**，其餘表在退場段落處理。

## 五、對外介面

### MCP 工具（agent 的主要介面）

工具名沿用 ct_erp 的資源語彙，動詞開頭。與退場的舊模組同名的工具（`find_item`、`get_stock`、`find_party`、`create_purchase_order` 等）**沿用同名**，因為 bot 提示詞已經寫成那樣，換實作不換名字可以讓提示詞少改一輪。

| 群組 | 工具 |
|---|---|
| 品號 | `find_item`、`get_item`、`resync_item_catalog` |
| 庫存 | `get_stock`、`list_stock_entries`、`create_stock_entry`、`update_stock_entry`、`delete_stock_entry` |
| 廠商客戶 | `find_party`、`get_party`、`create_party`、`update_party`、`list_party_contacts`、`add_party_contact`、`delete_party_contact` |
| 進貨 | `list_purchase_orders`、`get_purchase_order`、`create_purchase_order`、`update_purchase_order`、`delete_purchase_order`、`mark_purchase_order_paid`、`suggest_purchase_items` |
| 銷貨 | `list_sales_orders`、`get_sales_order`、`create_sales_order`、`update_sales_order`、`delete_sales_order`、`mark_sales_order_collected`、`suggest_sales_items` |
| 傳票 | `list_vouchers`、`get_voucher`、`create_voucher`、`update_voucher`、`delete_voucher`、`list_accounts` |
| 收付款 | `list_receipts`、`get_receipt`、`create_receipt`、`update_receipt`、`delete_receipt`、`list_banks`、`list_payments`、`get_payment`、`create_payment`、`update_payment`、`delete_payment`、`list_bank_accounts_lookup` |
| 開戶帳號 | `list_bank_accounts`、`create_bank_account`、`update_bank_account`、`delete_bank_account` |
| 使用者與紀錄 | `list_erp_users`、`get_erp_me`、`create_erp_user`、`update_erp_user`、`list_erp_activity` |

全部登記進 `TOOL_APP_MAPPING`。

### 自然語言容忍（service 層，不是工具層）

ct_erp 的查詢參數只有 `keyword` 與代號，agent 不該被迫先查 id：

- **對象解析**：`vendor`／`customer` 參數吃名稱或代號，service 先打 `/api/vendors?keyword=`，唯一命中就用，多筆回候選讓 agent 問人，零筆明說查無此廠商。品號同理走 `/api/item-catalog`。
- **日期詞**：`上週`、`這個月`、`今年`、`最近三個月` 在 service 解析成 `date_from`／`date_to`。時區 Asia/Taipei。
- **分頁**：`limit` 一律夾在 1–100（ct_erp 的 `limit` 沒有上限保護，而傳票有十一萬筆，agent 一個手滑就會把整包拉進 context）。回應帶 `total`，超出時明說「共 N 筆，只列出 M 筆」。

### REST（`/api/ct-erp/*`）

路徑與 ct_erp 一對一（`/api/ct-erp/purchase-orders` 對 `/api/purchase-orders`），差別只在認證換成 CTOS 的 session／PAT，外加 app 權限依賴。前端畫面與 CLI 共用。

PAT 的 scope 表要加 `ct-erp-finance`。

### CLI

現有的 `ctos erp` 三支子命令（`find`／`item`／`stock`）維持指令名不變，改打 `/api/ct-erp/*`。新增：

```
ctos erp po list [--vendor X] [--unpaid] [--from 2026-09-01] [--to 2026-09-30]
ctos erp po get <單號>
ctos erp so list / get          # 銷貨
ctos erp party find <關鍵字>
ctos erp party get <代號>
ctos erp voucher list           # 需 ct-erp-finance
ctos erp receipt list / payment list
```

寫入類不進 CLI 第一版。理由：CLI 的使用者是開發者與 AI agent，寫入走 MCP 工具有二階段確認與稽核，CLI 再開一條平行的寫入路徑只是多一個要顧的地方。要的話之後補。

### Skills

`extends/ct_erp/skills/` 三支，取代 `extends/erpnext/skills/` 的三支：

| skill | requires_app | 內容 |
|---|---|---|
| `inventory` | `inventory-management` | 品號、庫存、進貨、銷貨的工具清單與用法，含「查庫存先找品號」的流程 |
| `vendor` | `vendor-management` | 廠商客戶與聯絡人 |
| `finance` | `ct-erp-finance` | 傳票、收付款、開戶帳號；開頭明寫這是會計資料、寫入前必須複述給人確認 |

`project-mgmt` 那支直接刪除：專案已經由 CTOS 自己的專案模組接手（`2026-09-11-project-module-design.md`，已上線），它現在指著 ERPNext 是舊帳。

## 六、錯誤處理

沿用 `erp_router.py` 的翻譯規則，加兩條：

| ct_erp 回應 | CTOS 對外 | 訊息 |
|---|---|---|
| 連線失敗 | 502 | ct_erp 連線失敗 |
| 401／403 | 502 | ct_erp 憑證無效（伺服器端設定問題） |
| 403「只有超級使用者」 | 403 | 這項操作 AI 帳號沒有權限，請在 ct_erp 網頁操作 |
| 404 | 404 | ct_erp 查無資料 |
| 422 | 400 | 帶上 ct_erp 的欄位驗證訊息，不要吞掉 |

第三條要與第二條分開，因為它是**預期內**的權限邊界（`/api/users`、`/api/activity-log` 現在就是這樣），回 502 會讓人以為系統壞了。

## 七、測試

- **client 層**：httpx mock，逐一驗錯誤碼翻譯表。
- **service 層**：名稱解析（唯一命中／多筆／零筆）、日期詞、`limit` 夾擠。
- **權限**：每支工具與每條 REST 路由都要有「無權限回 403」與「未綁定回 BOUND_USER_REQUIRED_MESSAGE」的案例；沿用既有的路由守衛回歸測試（#267）把新路由納入。
- **契約**：從 ct_erp 的 `/openapi.json` 產生 fixture，不手寫。手寫 fixture 與真實欄位對不上是既有的踩雷點。
- **二階段刪除**：不帶 token 不會真的刪、token 一次性、token 過期。

不做整合測試打真的 ct_erp：那是會計的活帳本。

## 八、實作順序

每段一支 PR，本機真後端端到端驗過才開 PR。

1. **client＋service＋錯誤翻譯**，唯讀端點先通（品號、庫存、廠商、進貨、銷貨）。
2. **REST `/api/ct-erp/*` 唯讀＋權限**，CLI 三支子命令改指過來。這一段做完，`ctos erp` 就從空表恢復成真資料。
3. **MCP 唯讀工具**＋提示詞改寫（`linebot-group`／`linebot-personal`），bot 恢復查得到東西。同時清掉那段自相矛盾的舊指引。
4. **`ct-erp-finance` app id**＋錢帳類唯讀（傳票、收付款、開戶帳號）。
5. **寫入工具**（廠商、庫存單、進貨單、銷貨單）＋`erp_audit`＋二階段刪除。
6. **錢帳類寫入**。
7. **CLI 新增子命令**。
8. **ERPNext 退場**（見下節）。

第 2、3 段是止血，優先。

## 九、ERPNext 退場

在第 1 到 7 段完成並觀察兩週之後，才動這一段：

1. 移除 `extends/erpnext` submodule（含 `erp_router.py`、三支 skill、MCP server 宣告）。
2. `.env` 移除 `ERPNEXT_URL`／`ERPNEXT_API_KEY`／`ERPNEXT_API_SECRET`。
3. 停用 .11 上的 erpnext docker compose（8 個容器），保留資料庫磁碟區與既有的每日備份（#190）至少半年。
4. nginx 移除 `next.erp` server block，dnsmasq 移除該筆 `address=`。
5. 刪除 migration 030–033 建立的 CTOS 自建 ERP 表（`items`、`parties`、`purchase_orders`、`purchase_order_lines`、`stock_balances`、`stock_movements`、`warehouses`、`party_contacts`、`party_addresses`），**保留 `erp_audit`**。用新的 migration，不改舊的。
6. ctos-web 的往來對象與物料畫面改打 `/api/ct-erp/*`。

kb-231 那份 76 筆 ERPNext 庫存匯出，是在 ct_erp 已有資料的前提下準備的，匯入與否要先跟會計確認會不會與 ct_erp 現有庫存重複，**不要因為檔案已經備好就灌**。

## 十、未決事項

1. **`AI_agent` 的寫入權限範圍未知。** `GET /api/users/me` 回 `permissions: {}`、`is_superuser: false`，實測讀取不受限、`users` 與 `activity-log` 回 403。寫入端點一律沒有測（不用寫入型動詞探測正在用的帳）。實作第 5 段之前必須跟 ct_erp 作者確認：`permissions` 的值域、AI_agent 放行哪些寫入、能不能降成唯讀或限定資源。
2. **`ct_erp` 的 `limit` 上限與效能**：傳票十一萬筆，list 端點沒看到上限保護，大範圍查詢的回應時間未測。
3. **收付款單出現 2027 年的日期**（`receipt_no 20270520000001`、`payment_no 20270701000001`），可能是票據到期日或編號規則，影響日期篩選的語意，要問清楚。
4. **bot 提示詞的止血要不要現在做**：第 3 段完成前，可以先把提示詞退回 ERPNext 版本讓同仁問得到東西（migration 032 的 downgrade），或維持現狀等 ct_erp 接好。
