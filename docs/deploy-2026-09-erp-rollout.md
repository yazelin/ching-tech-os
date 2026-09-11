# 2026-09 一次授權全套：往來與物料模組（取代 ERPNext）部署清單

給 yazelin 回來一眼決定用。整理日期 2026-09-12；**在他點頭前 .11 完全不動**。

## 0. 現況（2026-09-12 查證）

| 項目 | .11 正式機 | main |
|---|---|---|
| HEAD | `0b982f1`（#189，2026-09-11 22:2x 部署） | `#202` 合併後 |
| alembic | `029 (head)` | 033 |
| 已上線 | #186 授權缺口、#188 專案模組後端、#189 ai_logs.user_id | — |
| 另外裝好的 | ERPNext 每日備份腳本與 `backup-erpnext.timer`（#190，不經部署流程） | — |

專案頁（os.ching-tech.com/projects）後端已在線上，`/api/projects` 回 401 不是 404。

## 1. 待部署 PR 與對使用者可見的影響

| PR | 做了什麼 | 使用者看得到的 |
|---|---|---|
| #192 | 往來與物料模組後端：十張表、23 支 MCP 工具、REST `/api/parties`、`/api/items`、`/api/warehouses`、`/api/stock`、`/api/purchase-orders` | 新前端往來對象、物料庫存、採購單、首頁待收貨卡從「連線失敗」變可用（表是空的，要等匯入） |
| #194 | web 聊天 `ai_response` 帶 `toolCalls`／`toolTimings`，訊息存 `tool_calls`，`prompt_name` 預設對齊 | 新前端 AI 助手頁看得到「agent 做了什麼」的時間軸；舊桌面 AI 助手不受影響（只讀 `message`） |
| #196 | 往來對象聯絡人／地址編輯刪除端點、搜尋含聯絡人電話、role=both | 往來對象頁的編輯／刪除／設主要可用 |
| #198 | bot prompt、skills、CLI、舊桌面切到新模組；`requires_app` 支援清單 | **LINE／Telegram bot 開始用新工具**回答廠商／物料／庫存／採購問題；舊桌面少了 ERPNext 圖示；CLI 0.2.0 |
| #202 | 專案模組 MCP 工具九支，bot prompt 專案段改工具指引 | bot 能代查專案、開任務、完成里程碑（成員才能寫） |
| #206 | 未綁定 CTOS 帳號的 bot 使用者不得使用專案、往來對象、物料庫存、檔案工具（issue #201，既有缺口） | LINE／Telegram 未綁定者問專案／廠商／NAS 檔案會得到「請先綁定」；已綁定者不變。**無 migration，建議與這批一起上，且不要晚於 #192／#202** |
| #197 | ERPNext 匯入腳本 | 不影響服務；匯入是**另一次授權**（見第 6 節） |
| #191／#193／#195／#190 | 規格與備份文件、備份腳本 | 無 |

## 2. Migration

順序 `030 → 031 → 032 → 033`，一次 `alembic upgrade head`。四支互不相依。

| 版本 | 動了什麼 | downgrade | 退的代價 |
|---|---|---|---|
| 030 | `CREATE EXTENSION IF NOT EXISTS pg_trgm`；建 `parties`、`party_contacts`、`party_addresses`、`items`、`warehouses`、`stock_balances`、`stock_movements`、`purchase_orders`、`purchase_order_lines`、`erp_audit` 與索引、CHECK | `alembic downgrade 029`：反序 drop 十張表，extension 保留 | **匯入前退沒有損失；匯入後退會刪掉匯入資料** |
| 031 | `ai_chats.prompt_name` 欄位預設 `'default'`→`'web-chat-default'`，回填殘留列 | `alembic downgrade 030`：還原欄位預設；回填的列不還原 | 無害 |
| 032 | `ai_prompts` 的 linebot-group／linebot-personal 三段 ERPNext 指引逐段 `replace()` 成新工具指引；段落找不到記 warning 略過 | `alembic downgrade 031`：逐字換回 ERPNext 版 | 無害；正式庫 prompt 若被人手改過，看 journal 有沒有「找不到這些段落」的 warning，有就人工比對 |
| 033 | 同上，專案段從「請到新前端」換成專案工具指引 | `alembic downgrade 032` | 無害 |

## 3. 部署步驟（與 #186、#188 那兩次相同）

前置：
```bash
ssh ct@192.168.11.11
cd ~/SDD/ching-tech-os && git log --oneline -1          # 應為 0b982f1
cd backend && uv run alembic current                     # 應為 029 (head)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8088/api/health   # 200
docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -Atc "select 1 from pg_available_extensions where name='pg_trgm'"   # 1
mkdir -p ~/backups && docker exec ching-tech-os-db pg_dump -U ching_tech -Fc ching_tech_os > ~/backups/ctos-$(date +%Y%m%d-%H%M).dump
```
部署：
```bash
cd ~/SDD/ching-tech-os && git pull --ff-only
git submodule sync && for p in $(git submodule status | grep -v '^-' | awk '{print $2}'); do git submodule update --init -- "$p"; done
cd backend && uv sync --extra voice
cd .. && npm ci && (cd frontend && npm install) && npm run build
cd backend && uv run alembic upgrade head        # 030 031 032 033，預期秒級
uv run alembic current                           # 033 (head)
sudo systemctl restart ching-tech-os
for i in $(seq 1 20); do curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8088/api/health | grep -q 200 && break; sleep 3; done
systemctl is-active ching-tech-os
journalctl -u ching-tech-os --since "5 minutes ago" --no-pager | grep -E "找不到這些段落|已切換|MCP servers|Added MCP server"
```
中斷時間：一次重啟。離峰做（030 建索引與 032 改 prompt 都是秒級，但避免有人正在跟 bot 對話）。

## 4. 部署後驗證（唯讀或臨時資料，臨時 session 用完刪）

1. HEAD 是 main 最新、`alembic current` 033、十張表在、`pg_extension` 有 `pg_trgm`、`ai_chats.prompt_name` 預設為 `web-chat-default`。
2. `journalctl` 無 032／033 的「找不到這些段落」warning（有就人工比對 prompt）。
3. REST：一般使用者 `GET /api/parties` 200、`POST /api/parties` 空 body 422、無 token 401；`GET /api/projects` 200。
4. MCP：journal 的工具載入行含 `find_party`、`find_project`。
5. **LINE bot 還能回話**：請 yazelin 用自己的 LINE 傳「你好」與「查一下有哪些專案」，兩句都要有回覆（第二句在匯入前會說沒有資料）。這是每天有人在用的東西，最優先。
6. 新前端：AI 助手頁送一句話有回覆且有工具時間軸；往來對象頁打開是空清單不是錯誤。
7. 舊桌面：AI 助手開一次能對話；桌面沒有 ERPNext 圖示。

## 5. 會打斷正在使用的人

- **CLI 使用者**：`ctos` CLI 要升到 0.2.0（`uv tool install ./cli` 重裝）；舊版的 `erp` 子命令打 `/api/erp` 在 extends/erpnext 停用前仍可用，停用後 404。
- **bot 使用者**：不需重登；但 032 之後 bot 對廠商／物料問題會改用新工具，匯入前新表是空的，會回「找不到」——所以**部署與匯入要接著做**，中間不要隔太久。
- **舊桌面開著的分頁**：這批沒改 socket 流程，不需重新整理；ERPNext 圖示要重新整理才消失。
- **不需要重新登入**（沒動權限預設值）。
- 不會打斷：專案頁、知識庫、AI Log。

## 6. 退路

- 服務起不來：`sudo systemctl status ching-tech-os`、`journalctl -u ching-tech-os -n 100`；`git checkout 0b982f1 && cd backend && uv run alembic downgrade 029 && sudo systemctl restart ching-tech-os`；仍不行就 `pg_restore` 前置那份 dump。
- 只退某一支：見第 2 節各自的 `downgrade`。
- **匯入之後**就不要退 030（會刪匯入資料），改用往前修。

## 7. 部署後接著做（各自另外授權）

1. **匯入**（#197）：`cd ~/SDD/ching-tech-os/backend && DB_NAME=ching_tech_os uv run python ../scripts/erpnext_import.py --src /mnt/nas/ctos/erpnext-backup/$(cat /mnt/nas/ctos/erpnext-backup/LATEST)/doctypes --dry-run`，看 `import-report.json` 沒有 errors 與 merge_review 再拿掉 `--dry-run` 正式跑一次；對數（parties 約 1035、contacts 約 1008、items 117、warehouses 4、stock 76）；重跑一次應零寫入。ERPNext 進入唯讀過渡期兩週。
2. **停用 ERPNext**（PR 8，尚未做）：移除 `extends/erpnext` submodule（它的三個 skill 只停容器關不掉）、`.env` 三個 ERPNEXT 變數、MCP server 註冊、`/api/erp` proxy；停九個 erpnext 容器保留 volume 四週；備份 timer 最後跑一次後停。
