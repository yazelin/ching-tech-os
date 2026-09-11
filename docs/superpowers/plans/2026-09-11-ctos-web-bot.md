# ctos-web Bot 管理模組實作計劃（照舊桌面）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把舊桌面 `frontend/js/linebot.js` 的 Bot 管理搬進 ctos-web：六個分頁（綁定、群組含明細與訊息、使用者、黑名單、訊息、檔案），同樣的功能範圍，不重新設計資訊架構、不加舊版沒有的功能。後端零改動。

**Architecture:** 路由 `/bot`（分頁用 `?tab=binding|groups|users|blocklist|messages|files`，預設 binding）與 `/bot/groups/:id`（群組明細）。資料層 `src/lib/bot.ts`（TanStack Query）。平台篩選（全部／Line／Telegram）是舊版的全域狀態，新版放 URL `?platform=`，六個分頁共用。分頁用舊版的每頁筆數（群組／使用者／黑名單 20、訊息 50、檔案 30）。路由守衛 `RequireApp app="linebot"`（第 3 段的機制）。

**Tech Stack:** 既有骨架與依賴，不加新依賴。

**Spec:** spec 第三節「Bot 管理」；yazelin 2026-09-11 拍板「照舊」。

## Global Constraints（API 契約，已對照 `api/linebot_router.py` 與 `models/linebot.py`）

所有端點掛在 `/api/bot`（`modules.py:115`），全部 `get_current_session`（登入即可）。`platform_type` 值為 `line`／`telegram`。

- 綁定（目前登入者自己的）：`GET /api/bot/binding/status` → `{ is_bound, line_display_name, line_picture_url, bound_at, line: PlatformBindingStatus|null, telegram: PlatformBindingStatus|null }`，`PlatformBindingStatus = { is_bound, display_name, picture_url, bound_at }`；`POST /api/bot/binding/generate-code?platform_type=line|telegram` → `{ code, expires_at }`；`DELETE /api/bot/binding?platform_type=…`。
- 群組：`GET /api/bot/groups?limit=20&offset=N&platform_type=&is_active=` → `{ items: LineGroupResponse[], total }`；`LineGroupResponse = { id, platform_type, platform_group_id, name, picture_url, member_count, project_id, project_name, is_active, allow_ai_response, joined_at, left_at, created_at, updated_at }`；`GET /api/bot/groups/{id}`；`PATCH /api/bot/groups/{id}` body `{ allow_ai_response?: boolean, name?, is_active?, project_id? }`；`DELETE /api/bot/groups/{id}`（連同訊息一起刪）。**專案綁定**：舊版用 `/api/projects` 列專案，該端點已於二月移除（404），所以新版只顯示 `project_name`（有就顯示），不提供綁定選單，留到專案模組。
- 使用者：`GET /api/bot/users-with-binding?limit=20&offset=&platform_type=` → `{ items: LineUserResponse[], total }`；`LineUserResponse = { id, platform_type, platform_user_id, display_name, picture_url, status_message, language, user_id, is_friend, created_at, updated_at, bound_username, bound_display_name, is_blocked, blocked_at, blocked_reason }`；封鎖 `PATCH /api/bot/users/{id}/block` body `{ reason: string|null }`；解封 `PATCH /api/bot/users/{id}/unblock`。
- 黑名單：`GET /api/bot/users?blocked=true&limit=20&offset=&platform_type=` → 同 `LineUserResponse[]`。
- 訊息：`GET /api/bot/messages?page=&page_size=50&platform_type=&group_id=&user_id=` → `{ items: LineMessageResponse[], total, page, page_size }`；`LineMessageResponse = { id, message_id, bot_user_id, user_display_name, user_picture_url, bot_group_id, message_type, content, file_id, file_info, is_from_bot, ai_processed, created_at }`。群組明細的「最近訊息」＝`GET /api/bot/messages?group_id={id}&page=1&page_size=20`。
- 檔案：`GET /api/bot/files?page=&page_size=30&platform_type=&file_type=` → `{ items: LineFileResponse[], total }`；`LineFileResponse = { id, message_id, file_type, file_name, file_size, mime_type, nas_path, thumbnail_path, duration, created_at, bot_group_id, bot_user_id, user_display_name, group_name }`；下載 `GET /api/bot/files/{id}/download`（**實作者要查** `api_download_file` 的 dependency：若是 `get_session_from_token_or_query` 就用 `?token=` 的 `<a>`；否則用 `apiFetch` 取 blob 再 `URL.createObjectURL` 觸發下載）；刪除 `DELETE /api/bot/files/{id}`。
- 顯示字典：platform `line`→「Line」、`telegram`→「Telegram」；message_type 非 `text` 顯示 `[類型]`；file_type 原樣。
- UI 正體中文、全形標點、不用 emoji；頁首照第二段的樣式（左計數、右主要動作）；表格放 `overflow-x-auto`；手機一欄。
- e2e 用 `page.route` 攔 `/api/bot/*`；任何落到首頁的測試掛 `mockApi`＋`mockKb`；`userFixture.permissions.apps.linebot` 已是 true。
- 每 task 一個 commit，branch `feat/bot`，最後一個 PR；trailer 附實際模型。

## 檔案地圖

```
src/lib/bot.ts, bot.test.ts             # 型別、query/mutation 函式、botKeys、PLATFORM_LABEL、分頁工具
src/pages/bot/index.tsx                 # /bot：平台篩選 + 六個 Tabs（URL ?tab= ?platform= ?page=）
src/pages/bot/tabs/binding.tsx          # 綁定
src/pages/bot/tabs/groups.tsx           # 群組清單
src/pages/bot/group-detail.tsx          # /bot/groups/:id
src/pages/bot/tabs/users.tsx            # 使用者
src/pages/bot/tabs/blocklist.tsx        # 黑名單
src/pages/bot/tabs/messages.tsx         # 訊息
src/pages/bot/tabs/files.tsx            # 檔案
src/components/bot/platform-badge.tsx, pagination.tsx（若 ai-log 的分頁可抽共用就抽，否則複製）
e2e/helpers.ts  mockBot(page, fixtures)
e2e/bot-*.spec.ts
```

---

### Task 1: 資料層 `src/lib/bot.ts`（Vitest）＋ `mockBot`

- 型別照上面契約；函式：`getBindingStatus`、`generateBindingCode(platform)`、`unbind(platform)`、`listGroups({platform, page})`、`getGroup(id)`、`updateGroup(id, patch)`、`deleteGroup(id)`、`listUsersWithBinding({platform, page})`、`listBlockedUsers({platform, page})`、`blockUser(id, reason)`、`unblockUser(id)`、`listMessages({platform, page, groupId?, userId?})`、`listFiles({platform, page, fileType?})`、`deleteFile(id)`、`fileDownloadUrl(id)`（依實作者查到的 download 認證方式）。`botKeys` 一組。`PLATFORM_LABEL`。分頁：offset 型（groups／users／blocklist：`limit`＋`offset=(page-1)*limit`）與 page 型（messages／files）兩種 helper。
- Vitest：URL 組裝（offset 計算、platform 空值略過、group_id）與 `blockUser` body。
- `e2e/helpers.ts` 加 `mockBot(page, opts)`：fixtures 兩個群組（line／telegram，一個 `allow_ai_response` true，一個 `is_active` false 有 `left_at`）、三個使用者（一個已綁定 CTOS 帳號、一個未綁定、一個已封鎖有 `blocked_reason`「洗版」）、六則訊息（含 `is_from_bot` 與非 text 類型）、兩個檔案（image 與 document，`file_size`）；binding status：line 已綁定、telegram 未綁定。mutation mock 改 fixture 副本（封鎖／解封、allow_ai、刪群組、刪檔案、generate-code 回 `{code:"123456", expires_at}`、unbind）。exact-pathname predicates，注意 `/users-with-binding` 與 `/users`、`/groups/{id}` 與 `/groups/{id}/…` 不互吃。

### Task 2: `/bot` 殼＋綁定分頁＋群組清單

- `index.tsx`：頁首左「Bot 管理」小字＋平台 Select（全部／Line／Telegram，寫 `?platform=`），`Tabs` 六個（value 寫 `?tab=`，切分頁把 `page` 清掉）。路由 `bot` → `BotPage`（`RequireApp app="linebot"`），`bot/groups/:id` 先佔位。
- 綁定分頁：兩張卡「Line」「Telegram」：已綁定顯示頭像、名稱、綁定時間、「解除綁定」（AlertDialog 確認）；未綁定顯示「產生驗證碼」→ 顯示驗證碼（大字）、到期時間、「複製」（clipboard，成功「已複製」）、說明文字「在 Bot 對話輸入此驗證碼完成綁定」。
- 群組分頁：表格欄 群組名（連到明細）、平台、成員數、狀態（使用中／已離開）、AI 回覆（Switch，切換即 PATCH `allow_ai_response`）、專案（`project_name` 或「—」）；分頁「上一頁／下一頁／第 p／P 頁」與「共 N 個群組」。
- e2e `bot-binding-groups.spec.ts`：綁定卡狀態、產生驗證碼顯示 123456、解除綁定送 DELETE 帶 `platform_type`；群組清單列出兩筆、平台篩選送 `platform_type=telegram` 後剩一筆、AI 回覆 Switch 送 PATCH `{allow_ai_response:false}`。

### Task 3: 群組明細 `/bot/groups/:id`

- 標題（名稱或「未命名群組」）、平台、成員數、狀態、加入／離開時間、AI 回覆 Switch、專案（唯讀 `project_name`；沒有顯示「未綁定專案，綁定功能待專案模組」）、「最近訊息」（`messages?group_id=&page_size=20`，每則：發送者（bot 顯示「Bot」）、時間、內容或 `[類型]`）、「刪除群組」（AlertDialog：「刪除群組將同時刪除所有訊息記錄」）→ 成功回 `/bot?tab=groups`。404 提示。
- e2e：明細欄位、最近訊息列出、刪除確認後回清單且清單少一筆。

### Task 4: 使用者分頁＋黑名單分頁

- 使用者：表格欄 頭像＋名稱、平台、CTOS 綁定（`bound_display_name || bound_username` 或「未綁定」）、好友（是／否）、動作「封鎖」（Dialog 輸入封鎖原因，可留空 → PATCH block）；已封鎖者顯示「已封鎖」不給按鈕。分頁、共 N 位。
- 黑名單：表格欄 名稱、平台、封鎖時間、原因、動作「解除封鎖」（AlertDialog）；分頁。
- e2e：封鎖送 `{reason:"洗版"}`、黑名單列出並解封後少一筆。

### Task 5: 訊息分頁＋檔案分頁

- 訊息：列表每則：發送者（bot→「Bot」，否則 `user_display_name`）、平台、時間、內容（text）或 `[message_type]`、`ai_processed` 小標；分頁 50。
- 檔案：表格欄 檔名（無則 `類型_id前8`）、類型、大小（KB／MB）、來源（`group_name` 或 `user_display_name`）、時間、動作「下載」「刪除」（AlertDialog）；`file_type` 篩選 Select（全部／image／video／audio／file 依 fixture）；分頁 30。
- e2e：訊息列出與翻頁送 `page=2`、檔案刪除後少一筆、下載連結或 blob 行為（依實作方式斷言）。

### Task 6: README、PR

- README 模組現況：Bot 管理 → 已完成（六個分頁，專案綁定待專案模組）；目錄結構、e2e 清單。`speak-tw`。推 branch、開 PR（控制端）。

## 明確不做
- 專案綁定選單（`/api/projects` 已不存在）。
- 記憶管理（`/groups/{id}/memories` 等）：舊版是另一個 app「記憶管理」，不在 Bot 管理內。
- Bot 憑證設定（`/api/admin/bot-settings`）：舊版在系統設定，不在此。
- 任何舊版沒有的功能。
