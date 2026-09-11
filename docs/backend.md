# 後端開發指南

使用 FastAPI + NAS SMB 認證的後端服務。

## 近期重點（2026-09）

- 專案模組重建（migration 028：`projects` / `project_members` / `milestones` / `tasks`）。
  `/api/projects` 全部端點過 `require_app_permission("project-management")`；建立與刪除限管理員，
  編輯類走 `require_project_editor`（admin 或該專案成員）。專案頁的關聯知識條目用既有的
  `GET /api/knowledge?scope=project&project_id=…`。
- AI Log 三個端點（`/api/ai/logs`、`/api/ai/logs/stats`、`/api/ai/logs/{id}`）補上
  `require_app_permission("ai-log")`，`ai-log` 預設權限改為關閉，需管理員逐人開放。
- 排程執行結果可推回 LINE / Telegram：`executor_config.notify` 設定推播目標，失敗訊息帶連續失敗次數
  （`scheduled_tasks.consecutive_failures`，migration 027）。Skill Script 模式也開始寫 `ai_logs`。

## 近期重點（2026-02）

- 引入 `modules.py` 模組 registry，透過 `ENABLED_MODULES` 做條件式路由 / MCP / 排程載入。
- 新增 `GET /api/config/apps`，前端可動態取得啟用 app 清單。
- Skill 系統支援 `contributes`（app / mcp_tools / scheduler）解析與註冊。
- Skills Hub 支援多來源（ClawHub + SkillHub），由 `SKILLHUB_ENABLED` 控制是否啟用 SkillHub。

## 需求

- Python 3.11+
- uv (Python 套件管理)
- Docker & Docker Compose
- 區網 NAS (192.168.11.50) 可連線

## 快速開始

### 1. 啟動 PostgreSQL

```bash
cd docker
docker compose up -d
```

### 2. 安裝依賴

```bash
cd backend
uv sync
```

### 3. 執行資料庫 Migration

```bash
cd backend
uv run alembic upgrade head
```

### 4. 啟動後端服務

```bash
cd backend
uv run uvicorn ching_tech_os.main:socket_app --host 0.0.0.0 --port 8088 --reload
```

服務將在 http://localhost:8088 啟動。

## API 文件

啟動後端後，訪問：
- Swagger UI: http://localhost:8088/docs
- ReDoc: http://localhost:8088/redoc

## 主要 API

### 認證

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/auth/login` | 登入（CTOS 密碼優先，NAS SMB 備用） |
| POST | `/api/auth/logout` | 登出 |
| POST | `/api/auth/change-password` | 變更密碼（一般使用者自行變更） |
| POST | `/api/auth/tokens` | 建立長效 API token（PAT，需 web 登入 session） |
| GET | `/api/auth/tokens` | 列出自己的 API token |
| DELETE | `/api/auth/tokens/{id}` | 撤銷 API token |

#### API Token（PAT）

供 CLI 與自動化工具使用的長效 token，格式 `ctos_pat_xxx`，用法與 session token 相同
（`Authorization: Bearer ctos_pat_xxx`）。安全特性：

- 資料庫僅存 SHA-256 hash，token 只在建立時回傳一次
- `scopes` 限縮可存取的 app（預設 `["knowledge-base"]`），與使用者當下實際權限取交集
- `read_only=true`（預設）時，所有掛 `require_app_permission` 的端點拒絕非 GET 請求
- 驗證後合成的 session 一律 `role="user"`、不帶 SMB 密碼：不可操作 admin 端點與 NAS
- 不可用 PAT 換發或撤銷 PAT（防止外洩 token 自我複製）
- 預設效期 180 天（`expires_days`，`null` 為永久）；使用者停用（`is_active=false`）即全部失效

#### 知識條目層級權限

`scope: personal` 的條目僅 owner（與 admin）可讀，非 owner 透過任何讀取路徑
（單篇 / 版本歷史 / 附件下載 / MCP 工具）一律回 404，與搜尋的過濾語意一致；
寫入與刪除走 `check_knowledge_permission_async`（owner 或 global_write / global_delete）。

#### 登入方式（2026-09）

`POST /api/auth/login` 的 `method` 欄位：

- `auto`（預設，舊前端不帶此欄位時就是這個）：沿用舊邏輯。依 `username` 查使用者，有 `password_hash` 就走 `local`，否則走 `nas`。
- `nas`：以 NAS 帳密做 SMB 驗證，依 `users.nas_username` 找平台帳號，找不到就自動建立並綁定。session 保留 SMB 密碼供檔案操作。停用帳號不論從哪條路找到都會被擋。
- `local`：平台帳號密碼，只驗 `password_hash`，不 fallback 到 NAS。session 不存密碼，檔案功能要另外連線 NAS。

平台帳號可在 `POST /api/user/me/nas-binding` 以 NAS 帳密驗證後綁定 NAS 帳號，`DELETE` 解綁。`GET /api/user/me` 回 `nas_username`。唯讀 PAT 對綁定與解綁端點回 403。

### 使用者

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/user/me` | 取得目前登入使用者資訊 |
| PATCH | `/api/user/me` | 更新目前登入使用者資訊 |
| GET | `/api/user/preferences` | 取得偏好設定 |
| PUT | `/api/user/preferences` | 更新偏好設定 |
| GET | `/api/user/list` | 取得使用者簡化列表（下拉選單用） |

### 管理員 - 使用者管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/admin/users` | 使用者列表（含認證方式） |
| POST | `/api/admin/users` | 建立使用者 |
| PATCH | `/api/admin/users/{user_id}` | 編輯使用者資訊 |
| PATCH | `/api/admin/users/{user_id}/permissions` | 更新使用者權限 |
| POST | `/api/admin/users/{user_id}/reset-password` | 重設密碼 |
| POST | `/api/admin/users/{user_id}/clear-password` | 清除密碼（恢復 NAS 認證） |
| PATCH | `/api/admin/users/{user_id}/status` | 停用/啟用帳號 |
| DELETE | `/api/admin/users/{user_id}` | 永久刪除使用者 |
| GET | `/api/admin/default-permissions` | 取得預設權限設定 |

### NAS 檔案操作

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/nas/shares` | 列出共享資料夾 |
| GET | `/api/nas/browse?path=/share_name` | 瀏覽資料夾 |
| POST | `/api/nas/upload` | 上傳檔案 |
| GET | `/api/nas/download` | 下載檔案 |
| DELETE | `/api/nas/delete` | 刪除檔案 |

### 知識庫

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/knowledge` | 搜尋/列表知識（`project_id` 過濾專案關聯條目，`project` 是 tags 裡的專案名稱） |
| GET | `/api/knowledge/{id}` | 取得單一知識 |
| POST | `/api/knowledge` | 新增知識 |
| PUT | `/api/knowledge/{id}` | 更新知識 |
| DELETE | `/api/knowledge/{id}` | 刪除知識 |
| GET | `/api/knowledge/tags` | 取得所有標籤 |
| GET | `/api/knowledge/{id}/history` | 取得版本歷史 |

### 專案管理

全部端點需要 `project-management` app 權限。編輯類（PUT 專案、成員、里程碑、任務的寫入）
走 `require_project_editor`：admin 直接過，否則要是 `project_members` 裡的成員，
不是成員回 403「只有專案成員能編輯」，專案不存在回 404。

| 方法 | 端點 | 額外權限 | 說明 |
|------|------|----------|------|
| GET | `/api/projects` | — | 清單。query：`status`、`q`（名稱／客戶模糊）、`page`、`page_size`（預設 20，上限 100）。item 帶 `progress`、`member_count`、`overdue_milestones` |
| POST | `/api/projects` | 管理員 | 建立專案；指定 `owner_id` 時自動補成員 |
| GET | `/api/projects/summary` | — | dashboard：`active_count` 與逾期里程碑清單（依到期日升冪，最多 20 筆） |
| GET | `/api/projects/{id}` | — | 明細：主檔＋`progress`＋`member_count`＋`overdue_milestones`（數）＋`members`＋`milestones`（各帶 `is_overdue`）＋`tasks`＋`bot_groups`＋`knowledge_count` |
| PUT | `/api/projects/{id}` | 成員 | 更新主檔；改 `owner_id` 時自動補成員，原負責人降成一般成員 |
| DELETE | `/api/projects/{id}` | 管理員 | 刪除；先把 `bot_groups.project_id` 設回 NULL |
| POST | `/api/projects/{id}/members` | 成員 | `{user_id}` |
| DELETE | `/api/projects/{id}/members/{user_id}` | 成員 | 負責人不能移除（400） |
| POST | `/api/projects/{id}/milestones` | 成員 | 建立里程碑 |
| PUT | `/api/projects/{id}/milestones/{mid}` | 成員 | 更新里程碑 |
| DELETE | `/api/projects/{id}/milestones/{mid}` | 成員 | 刪除里程碑 |
| POST | `/api/projects/{id}/tasks` | 成員 | 建立任務 |
| PUT | `/api/projects/{id}/tasks/{tid}` | 成員 | 更新任務 |
| DELETE | `/api/projects/{id}/tasks/{tid}` | 成員 | 刪除任務 |

進度百分比 = `done` 任務數 ÷ 任務總數，四捨五入到整數，沒有任務時為 0，不存欄位、查詢時算。
逾期里程碑 = `due_date < CURRENT_DATE` 且 `status <> 'completed'` 且所屬專案 `status = 'active'`。
清單的計數、明細的 `is_overdue` 與 `/summary` 三處用同一套定義：結案或取消的專案不會一直紅著。

清單的 `q` 會跳脫 `%` 與 `_` 後才進 `ILIKE`。收貨行項的 key 是 `line_id`（同一張單可以有兩行同一個物料）。只給 `item_id` 時，
該物料只出現在一行才算指定，出現多行會回 409 並附上行候選，要呼叫端指定 `line_id`
（行項的 `id` 就在採購單明細的 `lines` 裡）。

建立與更新端點的回應 body 帶 `audit_id`（就是這次寫入的 `erp_audit.id`）；
GET 明細的 `audit_id` 是 `null`。

更新請求對資料表 NOT NULL 的欄位
（專案 `name`／`status`，里程碑 `name`／`due_date`／`status`／`sort_order`，任務 `title`／`status`／`sort_order`）
明確送 `null` 會被擋在 422；`owner_id`、`assignee_id`、`milestone_id`、日期欄位送 `null` 是清空，放行。
`owner_id`／`assignee_id` 指到不存在的使用者回 404「使用者不存在」，`milestone_id` 不屬於該專案回
400「里程碑不屬於此專案」。

### 往來與物料（往來對象、物料庫存、採購）

`/api/parties` 需要 `vendor-management` app 權限，`/api/items`、`/api/warehouses`、
`/api/stock`、`/api/purchase-orders` 需要 `inventory-management`。讀寫都只看 app 權限，
不做成員制（規格第四節：管理層要「AI 操控第一」），admin 一律過。
與 MCP 工具共用同一層 service（`services/erp*.py`），寫入端點回傳的 body 都帶 `audit_id`。

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/parties` | 清單。query：`q`（名稱／簡稱／別名／統編／聯絡人姓名或電話）、`role`（supplier／customer／both）、`page`、`page_size` |
| POST | `/api/parties` | 建立；可一次帶 `contacts`、`addresses` |
| POST | `/api/parties/merge` | 合併重複主檔。body `{keep_id, drop_id}`。宣告在 `/{party_id}` 之前 |
| GET | `/api/parties/{id}` | 明細：主檔＋聯絡人＋地址＋近期採購單＋相關專案＋`knowledge_count` |
| PUT | `/api/parties/{id}` | 更新主檔 |
| DELETE | `/api/parties/{id}` | 軟刪除（寫 `deleted_at`），之後不進清單也不進模糊解析 |
| POST | `/api/parties/{id}/contacts` | 新增聯絡人；`is_primary` 會把原本的主要聯絡人取消 |
| POST | `/api/parties/{id}/addresses` | 新增地址 |
| PUT | `/api/parties/{id}/contacts/{cid}` | 更新聯絡人；`is_primary=true` 會把同一家其他聯絡人降級；`cid` 不屬於該 party 回 404 |
| DELETE | `/api/parties/{id}/contacts/{cid}` | 刪除聯絡人；刪掉主要那筆不自動指派新主要 |
| PUT | `/api/parties/{id}/addresses/{aid}` | 更新地址；`is_primary=true` 會把同一家其他地址降級；`aid` 不屬於該 party 回 404 |
| DELETE | `/api/parties/{id}/addresses/{aid}` | 刪除地址；刪掉主要那筆不自動指派新主要 |
| GET | `/api/items` | 清單。query：`q`（料號／品名／規格／別名）、`item_group`、`page`、`page_size`。item 帶 `total_qty` |
| POST | `/api/items` | 建立；料號重複回 400 |
| GET | `/api/items/{id}` | 明細：主檔＋各倉餘額＋最近異動＋預設供應商 |
| PUT | `/api/items/{id}` | 更新 |
| DELETE | `/api/items/{id}` | 軟刪除；庫存異動紀錄保留 |
| GET | `/api/warehouses` | 倉庫清單 |
| POST | `/api/warehouses` | 建立；代碼重複回 400 |
| PUT | `/api/warehouses/{id}` | 更新；代碼撞到別的倉回 400 |
| DELETE | `/api/warehouses/{id}` | 軟刪除；還有餘額回 400 |
| GET | `/api/stock` | 庫存查詢（item × warehouse 一列）。query：`item_id`、`warehouse_id` |
| POST | `/api/stock/adjust` | 調整庫存。`{item_id, warehouse_id, qty_delta, reason, note}`；異動後為負回 400 |
| POST | `/api/stock/transfer` | 倉別調撥。`{item_id, from_warehouse_id, to_warehouse_id, qty}` |
| GET | `/api/purchase-orders` | 清單。query：`supplier_id`、`status`、`project_id`、`since`（訂購日起始）、`page`、`page_size` |
| POST | `/api/purchase-orders` | 建立；單號 `PO-YYYYMM-NNN` 在同一交易產生 |
| GET | `/api/purchase-orders/{id}` | 明細（含行項與金額合計） |
| PUT | `/api/purchase-orders/{id}` | 更新單頭；`status` 只收 `draft`／`ordered`（其餘 422），已收貨或已取消的單回 400 |
| POST | `/api/purchase-orders/{id}/receive` | 收貨入庫。`{lines:[{line_id, qty}], all, warehouse_id}`；超收回 400，只給 `item_id` 而該物料有兩行以上回 409 |
| POST | `/api/purchase-orders/{id}/cancel` | 取消（不是刪除）；已收過貨回 400 |

庫存是簡化分類帳：每次異動寫一筆 `stock_movements`，同一交易用
`INSERT ... ON CONFLICT (item_id, warehouse_id) DO UPDATE SET qty = qty + delta` 累計
`stock_balances`；餘額不可為負，違反時整個交易回滾（異動紀錄也不會留下）。
收貨全收改 `received`、部分改 `partial`。

更新請求對資料表 NOT NULL 的欄位（`parties.name`／`aliases`／`is_supplier`／`is_customer`、
`party_contacts.name`／`is_primary`、`party_addresses.address`／`is_primary`、
`items.code`／`name`／`aliases`、`warehouses.code`／`name`、`purchase_orders.supplier_id`／`status`）
明確送 `null` 會被擋在 422。清單的 `q` 會跳脫 `%` 與 `_` 後才進 `ILIKE`；`q` 同時比對聯絡人
姓名（模糊）與電話／手機（等值，避免片段號碼誤中）。
每筆寫入都在同一交易寫 `erp_audit`（`entity_type`、`action`、`diff`、`actor_user_id`、
`via`＝`rest`／`mcp`／`import`（`scripts/erpnext_import.py` 用）、`agent_name`）。

### AI 對話

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/ai/chats` | 列表對話 |
| POST | `/api/ai/chats` | 新增對話 |
| GET | `/api/ai/chats/{id}` | 取得對話 |
| DELETE | `/api/ai/chats/{id}` | 刪除對話 |
| PATCH | `/api/ai/chats/{id}` | 更新對話 |

### AI 管理

#### Prompts

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/ai/prompts` | 列表 Prompts（支援 category 過濾）|
| POST | `/api/ai/prompts` | 新增 Prompt |
| GET | `/api/ai/prompts/{id}` | 取得 Prompt 詳情 |
| PUT | `/api/ai/prompts/{id}` | 更新 Prompt |
| DELETE | `/api/ai/prompts/{id}` | 刪除 Prompt |

#### Agents

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/ai/agents` | 列表 Agents |
| POST | `/api/ai/agents` | 新增 Agent |
| GET | `/api/ai/agents/{id}` | 取得 Agent 詳情（含 Prompt）|
| GET | `/api/ai/agents/by-name/{name}` | 依名稱取得 Agent |
| PUT | `/api/ai/agents/{id}` | 更新 Agent |
| DELETE | `/api/ai/agents/{id}` | 刪除 Agent |
| POST | `/api/ai/test` | 測試 Agent |
| GET | `/api/ai/providers/status` | AI provider readiness、circuit 與 usage 快照（admin）|

#### AI Logs

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/ai/logs` | 列表 Logs（分頁、過濾）|
| GET | `/api/ai/logs/{id}` | 取得 Log 詳情 |
| GET | `/api/ai/logs/stats` | 取得統計資料 |

`/api/ai/logs` 的過濾參數：`agent_id`、`context_type`、`success`、`start_date`、
`end_date`、`user_id`、`page`、`page_size`。`/api/ai/logs/stats` 吃
`agent_id`、`start_date`、`end_date`、`user_id`。

**`user_id` 的 0 是特殊值**：代表「未記錄使用者」，查的是 `user_id IS NULL`，
包含 migration 029 之前的舊資料、未綁定 CTOS 帳號的 bot 對話，以及排程建立者被刪掉
的紀錄。不帶 `user_id` 則完全不過濾。合法值是 `>= 0` 的整數，負數回 422。

列表與詳情都會 LEFT JOIN `users` 帶出 `username`（`user_id` 為 NULL 時是 `null`）。
`ai_logs.user_id` 是 `REFERENCES users(id) ON DELETE SET NULL`：使用者被刪除時
那些 log 的 `user_id` 直接變成 NULL，**「使用者已刪除」等同「未記錄使用者」**，
前端只需要處理 NULL 一種情形，不會出現查不到名字的孤兒 ID。

寫入端各自的 `user_id` 來源：web-chat 與 compress 用 Socket.IO 連線身分、
`POST /api/ai/test` 用呼叫者 session、排程用 `executor_config.ctos_user_id`
或 `scheduled_tasks.created_by`、Line／Telegram 用已綁定的 `bot_users.user_id`、
skill script 用 framework 注入的 `ctos_user_id`。取不到的一律留 NULL。

以上三個端點套用 `require_app_permission("ai-log")`：舊桌面原本靠前端 `openApp` 擋住點擊，
後端端點從未套用權限檢查，任何登入者直接呼叫 API 就讀得到全部 AI log（含 system prompt）；
新前端沒有那道客戶端防護，問題因此浮上檯面，修法是把防護移到後端。這是既有的客戶端防護
缺口，不是新功能。`ai-log` 預設權限已改為關閉，需管理員逐人開放；`GET /api/ai/agents` 只含
名稱與模型、不敏感，維持原本的一般登入即可存取。

### Line Bot

#### Webhook

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/bot/line/webhook` | Line Webhook 接收端點 |

#### 群組管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/bot/groups` | 列表群組 |
| GET | `/api/bot/groups/{id}` | 取得群組詳情 |
| POST | `/api/bot/groups/{id}/bind-project` | 綁定專案 |
| DELETE | `/api/bot/groups/{id}/bind-project` | 解除專案綁定 |
| GET | `/api/bot/groups/{id}/files` | 列出群組檔案 |

#### 用戶管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/bot/users` | 列表用戶 |
| GET | `/api/bot/users/{id}` | 取得用戶詳情 |

#### 訊息管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/bot/messages` | 列表訊息（支援過濾）|

#### 檔案管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/bot/files` | 列表檔案（支援過濾）|
| GET | `/api/bot/files/{id}` | 取得檔案詳情 |
| GET | `/api/bot/files/{id}/download` | 下載檔案 |

### 物料/庫存管理

#### 物料

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/inventory/items` | 列表物料（支援 keyword、category、low_stock 過濾） |
| GET | `/api/inventory/items/{id}` | 取得物料詳情（含進出貨記錄） |
| POST | `/api/inventory/items` | 新增物料 |
| PUT | `/api/inventory/items/{id}` | 更新物料 |
| DELETE | `/api/inventory/items/{id}` | 刪除物料 |
| GET | `/api/inventory/categories` | 取得物料類別列表 |
| GET | `/api/inventory/low-stock-count` | 取得庫存不足物料數量 |

#### 進出貨記錄

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/inventory/transactions` | 列表進出貨記錄（支援 item_id、type、project_id 過濾） |
| POST | `/api/inventory/transactions` | 新增進出貨記錄 |
| GET | `/api/inventory/transactions/{id}` | 取得記錄詳情 |
| DELETE | `/api/inventory/transactions/{id}` | 刪除記錄 |

### 廠商主檔

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/vendors` | 列表廠商（支援 keyword、category 過濾） |
| GET | `/api/vendors/{id}` | 取得廠商詳情 |
| POST | `/api/vendors` | 新增廠商 |
| PUT | `/api/vendors/{id}` | 更新廠商 |
| DELETE | `/api/vendors/{id}` | 刪除廠商 |
| GET | `/api/vendors/categories` | 取得廠商類別列表 |

### Bot 設定管理（管理員）

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/admin/bot-settings/{platform}` | 取得憑證狀態（遮罩顯示） |
| PUT | `/api/admin/bot-settings/{platform}` | 更新 Bot 憑證 |
| DELETE | `/api/admin/bot-settings/{platform}` | 清除憑證（回退至環境變數） |
| POST | `/api/admin/bot-settings/{platform}/test` | 測試連線 |

> `platform` 支援 `line` 和 `telegram`。憑證使用 AES-256-GCM 加密儲存，詳見 [安全機制](security.md)。

### Telegram Bot

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/bot/telegram/webhook` | Telegram Webhook 接收端點 |

> Telegram 群組、用戶、訊息管理共用 Line Bot 的 `/api/bot/*` API，透過 `platform_type=telegram` 參數篩選。

### AI Skills

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/skills` | 列出可用 Skills（含 `has_module`） |
| GET | `/api/skills/{name}` | 取得 Skill 詳情（含 scripts / contributes） |
| GET | `/api/skills/{name}/meta` | 取得 Skill `_meta.json` |
| PUT | `/api/skills/{name}` | 更新 Skill metadata |
| DELETE | `/api/skills/{name}` | 移除 Skill |
| POST | `/api/skills/reload` | 重載 Skills |
| GET | `/api/skills/hub/sources` | 取得 Hub 來源列表 |
| POST | `/api/skills/hub/search` | 搜尋 Hub Skills |
| POST | `/api/skills/hub/inspect` | 預覽 Hub Skill |
| POST | `/api/skills/hub/install` | 安裝 Hub Skill |
| GET | `/api/skills/{name}/frontend/{file_path}` | 提供 Skill 前端靜態資源（含路徑防護） |
| GET | `/api/skills/{name}/files/{file_path}` | 讀取 Skill 檔案 |

### 排程任務

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/scheduler/tasks` | 列出排程（動態 + 靜態），`include_static` 控制是否含系統排程 |
| POST | `/api/scheduler/tasks` | 建立動態排程 |
| GET | `/api/scheduler/tasks/{task_id}` | 取得單一排程 |
| PUT | `/api/scheduler/tasks/{task_id}` | 更新排程 |
| DELETE | `/api/scheduler/tasks/{task_id}` | 刪除排程 |
| PATCH | `/api/scheduler/tasks/{task_id}/toggle` | 啟用 / 停用 |
| POST | `/api/scheduler/tasks/{task_id}/run` | 手動觸發立即執行一次 |

> 排程管理端點皆需管理員權限。

#### 執行結果推播（executor_config.notify）

排程跑完之後預設只寫 `ai_logs`。要把結果推回原本的 LINE / Telegram 對話，在 `executor_config`
加一段 `notify`，Agent 與 Skill Script 兩種 `executor_type` 都適用：

```jsonc
{
  "agent_name": "system-scheduler",
  "prompt": "整理今天的庫存異動",
  "notify": {
    "platform": "telegram",   // "line" 或 "telegram"
    "target_id": "123456789", // Line user ID 或 Telegram chat_id
    "is_group": false,        // 群組對話填 true
    "group_id": null          // 群組對話填群組 ID
  }
}
```

- 沒有 `notify`、缺 `platform`、或 `target_id` 與 `group_id` 都空，就維持不推播。
- 推播走 `proactive_push_service.notify_job_complete()`，仍受 `bot_settings.proactive_push_enabled`
  平台開關管制（LINE 預設關、Telegram 預設開）。
- 成功訊息：`【排程】{排程名稱} 完成\n{結果內容}`；失敗訊息：`【排程失敗】{排程名稱}（連續第 N 次）\n{錯誤}`。
  訊息截斷到 4000 字（LINE 單則上限 5000 字）。
- 推播失敗只寫 warning，不影響排程執行結果，也不影響 `ai_logs` 寫入。
- `platform` 不是 `line` / `telegram`，或 `target_id` 與 `group_id` 都空，會寫一則帶排程名稱的
  warning 後略過推播。

> **目前只能透過 API 或資料庫設定；從舊桌面的排程 UI 編輯該排程會清掉 notify 設定。**
> 舊桌面的 `frontend/js/task-scheduler.js` 存檔時是用表單欄位重新組一份 `executor_config`
> 送 PUT，而 PUT 會整包覆寫該 JSONB 欄位，表單上沒有的 `notify` 就這樣被靜默丟掉。
> 設過 `notify` 的排程，請改用 `PUT /api/scheduler/tasks/{task_id}`（帶完整 `executor_config`）
> 或直接改資料庫。

#### 連續失敗計數

`scheduled_tasks.consecutive_failures`（migration 027）由 `update_task_run_result()` 一併更新：
成功歸零、失敗 +1，並用 `RETURNING` 取回更新後的值給失敗訊息用。`last_run_error` 維持截斷 1000 字。

### 公開配置

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/config/health` | 配置 API 健康檢查 |
| GET | `/api/config/apps` | 回傳啟用模組的桌面 app 清單 |

### 終端機 (WebSocket)

| 端點 | 說明 |
|------|------|
| `ws://host/terminal/{session_id}` | PTY shell session |

## 環境變數

完整環境變數定義在 `config.py`，範例檔為 `.env.example`。

### 資料庫

| 變數 | 預設值 | 說明 |
|------|--------|------|
| DB_HOST | localhost | 資料庫主機 |
| DB_PORT | 5432 | 資料庫埠號 |
| DB_USER | ching_tech | 資料庫使用者 |
| DB_PASSWORD | （必填） | 資料庫密碼 |
| DB_NAME | ching_tech_os | 資料庫名稱 |

### NAS / SMB

| 變數 | 預設值 | 說明 |
|------|--------|------|
| NAS_HOST | 192.168.11.50 | NAS 主機位址 |
| NAS_PORT | 445 | SMB 埠號 |
| NAS_USER | （必填） | NAS 帳號 |
| NAS_PASSWORD | （必填） | NAS 密碼 |
| NAS_SHARE | 擎添開發 | NAS 共享名稱 |
| NAS_MOUNT_PATH | /mnt/nas | NAS 掛載根路徑 |
| CTOS_MOUNT_PATH | /mnt/nas/ctos | CTOS 掛載路徑（讀寫） |
| PROJECTS_MOUNT_PATH | /mnt/nas/projects | 專案掛載路徑（唯讀） |
| CIRCUITS_MOUNT_PATH | /mnt/nas/circuits | 線路圖掛載路徑（唯讀） |
| LIBRARY_MOUNT_PATH | /mnt/nas/library | 圖書館掛載路徑（讀寫） |
| LIBRARY_PUBLIC_FOLDERS | 產品資料,教育訓練 | 公開資料夾列表（逗號分隔） |
| SMB_CONNECT_TIMEOUT | 10 | SMB 連線逾時（秒） |
| ENABLE_NAS_AUTH | true | 是否啟用 NAS SMB 認證 |
| CORS_EXTRA_ORIGINS | （空） | 額外允許的 CORS origin，逗號分隔（新前端 os.ching-tech.com） |

### 路徑

| 變數 | 預設值 | 說明 |
|------|--------|------|
| FRONTEND_DIR | ~/SDD/ching-tech-os/frontend | 前端靜態檔案目錄 |
| PROJECT_ROOT | （自動偵測） | 專案根目錄 |
| KNOWLEDGE_NAS_PATH | knowledge | 知識庫 NAS 相對路徑 |
| PROJECT_NAS_PATH | projects | 專案 NAS 相對路徑 |
| LINEBOT_NAS_PATH | linebot/files | Line Bot 檔案 NAS 相對路徑 |
| PROJECT_ATTACHMENTS_PATH | data/projects/attachments | 專案附件本機路徑 |
| KNOWLEDGE_DATA_PATH | data/knowledge | 知識庫本機路徑 |

### Session / 系統

| 變數 | 預設值 | 說明 |
|------|--------|------|
| SESSION_TTL_HOURS | 8 | Session 有效時間（小時） |
| PUBLIC_URL | https://ching-tech.ddns.net/ctos | 公開 URL（分享連結、Webhook） |
| ENABLED_MODULES | `*` | 啟用模組清單（`*`=全開，逗號分隔，見下表） |

**可用模組：**

| 模組 ID | 說明 | 備註 |
|---------|------|------|
| `core` | 核心功能 | 永遠啟用，不需列入 |
| `knowledge-base` | 知識庫 | |
| `project-management` | 專案管理 | |
| `file-manager` | 檔案管理器 | |
| `ai-agent` | AI Agent（Claude 對話） | |
| `line-bot` | Line Bot 整合 | |
| `telegram-bot` | Telegram Bot 整合 | |
| `public-share` | 公開分享連結 / 檔案下載 | Line Bot 圖片傳送需要 |
| `docs-tools` | 文件工具（簡報/文件生成） | |
| `skills` | Skills 系統 | 必要模組 |
| `terminal` | Web 終端機 | |
| `code-editor` | 程式碼編輯器 | |
| `task-scheduler` | 任務排程 | |
| `his-integration` | HIS 整合 | 需搭配 extends/his |
| `ct-his` | 展望 HIS 叫號 | 需搭配 extends/his |
| `printer` | 列印功能 | 需搭配 extends/printer |
| `erpnext` | ERPNext ERP 整合 | 需搭配 extends/erpnext |

### Bot 設定

| 變數 | 預設值 | 說明 |
|------|--------|------|
| BOT_SECRET_KEY | （無預設） | Bot 憑證加密金鑰（AES-256-GCM） |
| BOT_UNBOUND_USER_POLICY | reject | 未綁定用戶策略（reject / restricted） |
| BOT_RESTRICTED_MODEL | haiku | 受限模式使用的 AI 模型 |
| BOT_DEFAULT_RESTRICTED_AGENT | （空） | 預設受限 Agent ID |
| BOT_DEBUG_MODEL | sonnet | /debug 指令使用的模型 |
| BOT_CMD_DISABLED | （空） | 停用指令（逗號分隔） |
| INTENT_GUARD_ENABLED | false | Intent Guard 意圖守門員全域開關 |
| ANTHROPIC_API_KEY | （空） | Anthropic API Key（Intent Guard 用，無則 fallback 到 CLI） |
| BOT_RATE_LIMIT_ENABLED | false | 受限模式頻率限制開關 |
| BOT_RATE_LIMIT_HOURLY | 10 | 每小時上限 |
| BOT_RATE_LIMIT_DAILY | 50 | 每日上限 |

### Line Bot

| 變數 | 預設值 | 說明 |
|------|--------|------|
| LINE_CHANNEL_SECRET | （必填） | Line Channel Secret |
| LINE_CHANNEL_ACCESS_TOKEN | （必填） | Line Channel Access Token |

### Telegram Bot

| 變數 | 預設值 | 說明 |
|------|--------|------|
| TELEGRAM_BOT_TOKEN | （空） | Telegram Bot Token |
| TELEGRAM_WEBHOOK_SECRET | （空） | Webhook 驗證密鑰 |
| TELEGRAM_ADMIN_CHAT_ID | （空） | 管理員 Telegram ID（上線通知） |
| TELEGRAM_API_ID | （空） | Telegram API ID（Local Bot API 用，從 my.telegram.org 取得） |
| TELEGRAM_API_HASH | （空） | Telegram API Hash（Local Bot API 用） |
| TELEGRAM_LOCAL_API_URL | （空） | Local Bot API Server URL（如 `http://localhost:8081`，突破 20MB 限制） |
| TELEGRAM_LOCAL_API_DATA_DIR | （空） | Local API 資料目錄（如 `/tmp/telegram-bot-api`） |

### Skill 系統

| 變數 | 預設值 | 說明 |
|------|--------|------|
| SKILL_EXTERNAL_ROOT | ~/SDD/external-skills | 外部 skills 目錄（external-first 載入） |
| SKILL_ROUTE_POLICY | script-first | 工具路由策略（script-first / mcp-first） |
| SKILL_SCRIPT_FALLBACK_ENABLED | true | script 失敗時 fallback 到對應 MCP tool |

### Research Skill

| 變數 | 預設值 | 說明 |
|------|--------|------|
| BRAVE_SEARCH_API_KEY | （空） | Brave Search API 金鑰（留空 fallback 到公開搜尋） |
| RESEARCH_CLAUDE_MODEL | claude-opus | research worker 使用的模型 |
| RESEARCH_CLAUDE_TIMEOUT_SEC | 300 | Claude 背景研究 timeout（秒） |
| RESEARCH_STALE_TIMEOUT_MINUTES | 15 | 研究逾時判定（分鐘） |

### 文件轉換

| 變數 | 預設值 | 說明 |
|------|--------|------|
| MD2PPT_URL | https://md-2-ppt-evolution.vercel.app | MD2PPT 服務 URL |
| MD2DOC_URL | https://md-2-doc-evolution.vercel.app | MD2DOC 服務 URL |

## 專案結構

```
backend/
├── pyproject.toml
├── alembic.ini
├── migrations/
│   └── versions/           # Migration 檔案（001-007）
├── src/ching_tech_os/
│   ├── main.py             # FastAPI 入口（含 Socket.IO）
│   ├── config.py           # 設定檔
│   ├── database.py         # 資料庫連線
│   ├── mcp_cli.py          # MCP CLI 入口
│   ├── api/
│   │   ├── auth.py           # 認證 API
│   │   ├── user.py           # 使用者管理 API（含管理員端點）
│   │   ├── nas.py            # NAS 操作 API
│   │   ├── knowledge.py      # 知識庫 API
│   │   ├── ai_router.py      # AI 對話 API
│   │   ├── ai_management.py  # AI 管理 API (Prompts/Agents/Logs)
│   │   ├── linebot_router.py # Line Bot API
│   │   ├── telegram_router.py # Telegram Bot API
│   │   ├── inventory.py      # 物料/庫存 API
│   │   ├── vendor.py         # 廠商主檔 API
│   │   ├── bot_settings.py   # Bot 設定管理 API
│   │   ├── skills.py         # AI Skills API
│   │   ├── share.py          # 公開分享 API
│   │   ├── messages.py       # 訊息中心 API
│   │   └── config_public.py  # 公開設定 API
│   ├── services/
│   │   ├── session.py        # Session 管理
│   │   ├── smb.py            # SMB 連線服務
│   │   ├── user.py           # 使用者服務（CRUD、密碼管理）
│   │   ├── password.py       # 密碼雜湊與驗證
│   │   ├── permissions.py    # 權限管理
│   │   ├── terminal.py       # 終端機服務
│   │   ├── claude_agent.py   # Claude API 服務
│   │   ├── ai_chat.py        # AI 對話服務
│   │   ├── ai_manager.py     # AI 管理服務
│   │   ├── linebot.py        # Line Bot 服務
│   │   ├── linebot_ai.py     # Line Bot AI 處理
│   │   ├── linebot_agents.py # Line Bot Agent 定義
│   │   ├── bot_telegram/     # Telegram Bot 服務
│   │   ├── mcp_server.py     # MCP Server（FastMCP）
│   │   ├── inventory.py      # 物料/庫存服務
│   │   ├── vendor.py         # 廠商主檔服務
│   │   ├── bot_settings.py   # Bot 憑證管理服務
│   │   ├── presentation.py   # 簡報生成服務
│   │   ├── share.py          # 分享服務
│   │   ├── document_reader.py # 文件讀取（Word/Excel/PDF）
│   │   └── scheduler.py      # 排程任務
│   ├── skills/               # AI Skills 系統
│   │   ├── base/               # 內建：基礎工具（script-first）
│   │   ├── file-manager/       # 內建：檔案管理（script-first）
│   │   ├── script_runner.py    # Skill 腳本運行器
│   │   ├── media-downloader/   # 影片/音訊下載
│   │   └── media-transcription/ # 逐字稿轉錄
│   ├── utils/
│   │   └── crypto.py         # AES-256-GCM 加密
│   └── models/
│       ├── auth.py           # 認證模型
│       ├── user.py           # 使用者模型（含管理員操作）
│       ├── nas.py            # NAS 模型
│       ├── ai.py             # AI 相關模型
│       ├── linebot.py        # Line Bot 模型
│       ├── inventory.py      # 物料/庫存模型
│       ├── vendor.py         # 廠商主檔模型
│       └── share.py          # 分享模型
└── tests/
```

## 資料庫 Migration

所有資料庫 schema 變更都必須透過 Alembic migration：

```bash
# 建立新 migration
cd backend
uv run alembic revision -m "description"

# 執行 migration
uv run alembic upgrade head

# 回滾 migration
uv run alembic downgrade -1
```

Migration 檔案命名格式：`00X_description.py`（遞增編號）
