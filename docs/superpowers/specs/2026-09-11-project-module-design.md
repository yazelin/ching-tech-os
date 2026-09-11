# 專案模組（重建）設計

日期：2026-09-11
狀態：已拍板（2026-09-11，五個問題 yazelin 全部採預設），實作中
上位規格：`2026-09-10-ctos-web-react-frontend-design.md` 第三節「專案（重建）」與第四節「專案模組」

## 背景

管理層停用 ERPNext，專案進度要回到自己的系統。舊桌面曾有專案模組（`api/project.py`、`services/project.py`、`frontend/js/project-management.js`），2026-02 改接 ERPNext 時在 commit 64b9c6b 與 0582e05 拆掉，資料表也不在 `clean_schema.sql` 裡。這次是重建，不是搬回來：舊程式從 git 取回當參考，範圍照 9/10 spec 縮成「管理層看進度」。

repo 裡三個地方已經替它定了形狀，是這份規格的硬約束：

| 來源 | 約束 |
|------|------|
| `permissions.py` `DEFAULT_APP_PERMISSIONS["project-management"] = True` | app id 固定是 `project-management`，預設全員可用 |
| 首頁 dashboard README「進行中專案與逾期里程碑待專案模組」 | 專案要有能判「進行中」的狀態；里程碑要有到期日 |
| Bot 管理 README「專案綁定選單待專案模組」 | `bot_groups.project_id uuid` 欄位與 `PUT /api/bot/groups/{id}/bind-project` 已存在，只缺專案清單 |

另外兩個還活著的後端消費者，新表的欄位名必須對上，否則它們一直在查不存在的表：

- `services/permissions.py:is_project_member` 與 `services/mcp/server.py`：`SELECT 1 FROM project_members WHERE project_id = $1 AND user_id = $2`
- 知識庫 `scope = "project"` 的條目帶 `project_id`，寫入權限靠上面那個查詢

## 一、資料模型

四張表，Alembic migration 028，全部 `downgrade` 為 drop table（順序：tasks → milestones → project_members → projects）。`bot_groups.project_id` 與 `knowledge.project_id` 是現有欄位，不加外鍵（專案刪除時把 `bot_groups.project_id` 設回 NULL，知識條目保留）。

### projects

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | uuid pk | |
| name | text not null | |
| customer | text null | 客戶名稱，純文字（見問題 3） |
| status | text not null default 'active' | `planning`、`active`、`on_hold`、`completed`、`cancelled`；「進行中」= `active` |
| owner_id | int null → users.id | 負責人；設定時自動加進成員 |
| start_date / end_date | date null | |
| description | text null | |
| created_by | int null → users.id | |
| created_at / updated_at | timestamptz | |

### project_members

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | uuid pk | |
| project_id | uuid → projects.id on delete cascade | 欄位名不能改，見上 |
| user_id | int → users.id on delete cascade | 同上 |
| role | text not null default 'member' | `owner`、`member`；只做顯示與「負責人」標記，權限不分級 |
| created_at | timestamptz | |
| unique (project_id, user_id) | | |

### milestones

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | uuid pk | |
| project_id | uuid → projects.id cascade | |
| name | text not null | |
| due_date | date not null | 預定日；「逾期」= `due_date < 今天` 且 `status <> 'completed'` 且所屬專案 `status = 'active'` |
| completed_at | date null | 實際完成日 |
| status | text not null default 'pending' | `pending`、`in_progress`、`completed`；不另設 `delayed`，逾期由日期算 |
| sort_order | int not null default 0 | |
| created_at / updated_at | timestamptz | |

### tasks

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | uuid pk | |
| project_id | uuid → projects.id cascade | |
| milestone_id | uuid null → milestones.id on delete set null | 可空 |
| title | text not null | |
| description | text null | |
| assignee_id | int null → users.id on delete set null | 不限成員 |
| status | text not null default 'todo' | `todo`、`doing`、`done` |
| due_date | date null | |
| sort_order | int not null default 0 | |
| created_at / updated_at | timestamptz | |

進度百分比 = `done` 任務數 ÷ 任務總數，四捨五入到整數；沒有任務時為 0。不存欄位，查詢時算。

## 二、權限

- 讀：登入且有 `project-management` app 權限的人看得到全部專案與明細（9/10 spec 已定「所有登入者可讀」；admin 一律過）。
- 建立專案：admin（見問題 1）。
- 編輯專案主檔、成員、里程碑、任務：admin 或該專案成員（負責人必為成員）。
- 刪除專案：admin。
- 全部走既有 `require_app_permission("project-management")` 加一個 `require_project_editor(project_id)` 依賴，403 訊息「只有專案成員能編輯」。

## 三、API（`/api/projects`，全部 JSON）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/projects` | 清單。query：`status`、`q`（名稱／客戶模糊）、`page`、`page_size`（預設 20，上限 100）。回 `{items, total}`，item 含 `progress`、`member_count`、`overdue_milestones`（數） |
| POST | `/api/projects` | 建立 |
| GET | `/api/projects/summary` | dashboard 用：`{active_count, overdue_milestones: [{project_id, project_name, milestone_id, name, due_date, days_overdue}]}`，逾期清單依到期日升冪，最多 20 筆 |
| GET | `/api/projects/{id}` | 明細：主檔＋`progress`＋`members`（含 username／display_name）＋`milestones`（各帶 `is_overdue`）＋`tasks`＋`bot_groups`（綁定的群組 id／名稱／平台）＋`knowledge_count` |
| PUT | `/api/projects/{id}` | 更新主檔；改 `owner_id` 時自動補成員 |
| DELETE | `/api/projects/{id}` | 刪除；先把 `bot_groups.project_id` 設 NULL |
| POST | `/api/projects/{id}/members` | `{user_id}` |
| DELETE | `/api/projects/{id}/members/{user_id}` | 負責人不能移除 |
| POST / PUT / DELETE | `/api/projects/{id}/milestones[/{mid}]` | |
| POST / PUT / DELETE | `/api/projects/{id}/tasks[/{tid}]` | |

既有端點的小改動：

- `GET /api/knowledge` 加 `project_id` query 參數（配合 `scope=project`），專案頁列相關知識條目用。
- `GET /api/user/list` 已存在且登入即可用，成員與負責人選單用它，不另開端點。

## 四、畫面（ctos-web）

路由 `/projects`，側邊欄項目已存在，加 `app: "project-management"` 門檻，與其他模組一致。

- **清單** `/projects`：表格（名稱、客戶、狀態 tint badge、負責人、進度條、迄日、逾期里程碑數），狀態篩選與搜尋；admin 有「新增專案」。手機寬度改卡片。
- **新增／編輯** `/projects/new`、`/projects/:id/edit`：主檔表單；負責人用 `/api/user/list` 的選單。
- **明細** `/projects/:id`：頂部主檔與進度條；分頁：
  - 總覽：里程碑清單（逾期標紅、可勾完成）、最近任務。
  - 任務：清單依狀態分組，行內改狀態，新增任務對話框（標題、負責人、里程碑、到期日）。
  - 成員：清單與新增（選單）、移除。
  - 知識庫：`GET /api/knowledge?scope=project&project_id=…`，連到既有 `/kb/:id`；「新增條目」連到 `/kb/new?scope=project&project_id=…`（知識庫編輯器要認這兩個 query 參數並鎖定 scope）。
  - 群組：綁定的 LINE／Telegram 群組，連到 `/bot/groups/:id`。
  - 編輯類操作只在 admin 或成員時顯示；後端 403 時照既有 `role="alert"` 顯示。
- 空狀態與各分頁的 skeleton／錯誤照既有模組樣式。

## 五、專案模組之後要收掉的三件（各一支 PR）

1. **首頁 dashboard**：「進行中專案」卡（`active_count` 與最近迄日的前五個）與「逾期里程碑」卡（`summary.overdue_milestones`），只在有 `project-management` 權限時顯示。
2. **Bot 管理群組明細**：「綁定專案」下拉，來源 `GET /api/projects?page_size=100`，送既有 `bind-project` API；解除綁定送 `project_id: null`。
3. **AI Log 依用戶篩選**：`ai_logs` 加 `user_id int null → users.id on delete set null`（migration 029，downgrade drop column）；`create_log` 從 chat／session／排程的 `created_by` 帶入；`GET /api/ai/logs` 與 `/stats` 加 `user_id` 參數；前端篩選列加使用者選單。舊資料維持 NULL，篩選時顯示「未記錄使用者」的筆數。

## 六、假設（換一種就會做出不同東西的，列在問題；其餘自己定）

- 客戶是純文字欄位，不做客戶主檔。
- 專案狀態手動改，任務全完成不會自動完成專案。
- 里程碑不再有 `delayed` 狀態，逾期純由日期與狀態算。
- 任務負責人可以是非成員。
- 不做通知：里程碑逾期不推 LINE（見問題 4）。
- 不做 ERPNext 匯入（見問題 2）。
- 不做附件上傳；附件走知識庫條目。
- 舊桌面不加專案 app，只有新前端有。

## 七、已拍板的問題（2026-09-11，全部採預設）

1. **誰能建立專案？** 9/10 spec 寫「建立與編輯限 admin 與專案成員」，但建立時還沒有成員。預設：只有 admin 能建，建好指定負責人與成員。另一種：任何人都能建、建立者自動成負責人，管理層只看不管。
2. **ERPNext 現有 Project 要不要匯入當種子？** 預設不匯，第一版從空的開始，ERPNext 資料另外匯出備份。要匯的話我需要 ERPNext 的欄位對照與存取方式，會多一支匯入腳本與一輪資料核對。
3. **客戶要不要主檔？** 預設純文字。要主檔的話清單篩選與報表才能按客戶分，但廠商／客戶主檔 9/10 spec 明確排除在第一版。
   > **已推翻（2026-09-12）**：管理層決定自建 AI native 類 ERP 取代 ERPNext，廠商／客戶主檔（往來對象）由 `2026-09-12-ai-native-erp-design.md` 定義並實作（PR #192）。原話（監督 session 轉達 yazelin，2026-09-12）：「管理層的要求是 自建一個不要那麼複雜的AI native 的類erp 的系統來管理這些本來在nexterp內的資訊」。專案的 `customer` 純文字欄位維持不變，之後可選擇性關聯 `parties`。
4. **里程碑逾期要不要推 LINE 通知？** 預設不推，只在 dashboard 顯示。要推的話接 #182 的排程推播機制，每天早上推給負責人，會多一支排程與一個「通知對象」設定。
5. **非成員看得到任務與成員清單嗎？** 9/10 spec 說所有登入者可讀，預設整個明細都可讀（含任務、成員）。若要「非成員只看主檔與進度」，明細 API 要分兩種回應。

不依賴答案的部分先做：migration、後端 CRUD 與 summary、前端清單與明細（讀）。依賴答案的部分：建立入口誰看得到（問題 1，前端只差一個判斷）、匯入腳本（2）、客戶主檔（3）、推播排程（4）、明細分級（5）。

## 八、PR 切法與順序

1. `feat(projects)`：後端 migration 028、models、service、router、summary、KB `project_id` 篩選、測試（ching-tech-os）。
2. `feat(projects)`：ctos-web 清單、新增／編輯、明細五分頁、e2e。
3. 首頁兩張卡（ctos-web）。
4. Bot 群組綁定專案（ctos-web）。
5. AI Log 依用戶篩選：後端 migration 029 與 API（ching-tech-os）→ 前端（ctos-web）。

每支 PR 走 implement → review → fix → re-review，CI 綠才合併；後端合併到 main 即停，不部署 .11。動 schema 的 PR 描述寫明 downgrade。
