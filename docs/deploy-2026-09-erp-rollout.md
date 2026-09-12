# 2026-09 一次授權全套：往來與物料模組（取代 ERPNext）部署清單

給 yazelin 回來一眼決定用。整理日期 2026-09-12；**在他點頭前 .11 完全不動**。

## 建議執行順序（來源待確認，2026-09-12）

2026-09-12 有一句「1B 2清 3確認運作正確後才停用 ERPNext」出現在 session 的輸入框，監督 session **不能確認是 yazelin 本人**，所以沒有執行。列在這裡讓他一句話確認或否決：

| 順序 | 內容 | 代價 |
|---|---|---|
| **甲：先部署（選項 B 全套）→ 再清歷史 → 匯入 → 觀察 → 停用 ERPNext** | 安全修補與功能今天就上線 | 清歷史會改掉 .11 部署後的 checkout hash，**正式機要再動一次**（runbook 步驟六：`git reset --hard` 到對應新 commit，不用重啟、不用 migration，但仍是動正式機） |
| **乙：先清歷史 → 重建 hotfix 與清單 → 再部署 → 匯入 → 觀察 → 停用** | 正式機只動一次 | 安全修補晚上線（清歷史含 GitHub Support 申請，可能拖幾天）；期間未綁定者仍能讀 NAS 檔案、寫全域知識庫 |
| **丙：先只部署選項 A（止血）→ 清歷史 → 再部署全套** | 洞今天關掉、正式機動兩次但第一次沒有 migration | .11 會歷經 hotfix → 改寫後重指 → 全套三個狀態，清單要跟三次 |

監督 session 的看法：乙最省（只動一次正式機），丙最安全（洞先關），甲最快但正式機要碰兩次。**三個都要 yazelin 本人拍板，任何一個都不會自己開始。** 停用 ERPNext 在最後，而且要等匯入後 bot 觀察兩週。

## 這份清單的維護規則

**最後更新：2026-09-12，hotfix/unbound-guards = `f1aaafb`（含 #206 #212 #216 #219），全套 1921 passed、覆蓋率 90.24%。**

yazelin 會照著這份跑，他不會知道哪幾行是舊的。每次 cherry-pick 一支進 hotfix、或 main 多合併一支要部署的 PR，**同一支 docs PR 內**要更新：
1. 這段的最後更新時間、hotfix commit、測試數與覆蓋率。
2. 「先看這段」的安全修補表格（PR 號、狀態）與選項 A 的「實際生效」清單、指令裡的 commit hash。
3. 第 1 節待部署 PR 表格。
4. 第 4 節部署後驗證項（新修補要有對應的驗證句）。
5. 第 5 節「會打斷誰」——特別是**有沒有動權限預設值**（動了就要重新登入）與 CLI／分頁是否要重整。
6. 改完自己從頭讀一次第 5 節與第 6 節，找有沒有跟新內容矛盾的句子；同一份文件兩處講相反的話比沒寫還糟（2026-09-12 第 125 行「不需要重新登入」在 #219 之後就是錯的，已改）。

## 硬規則：工作目錄、migration、重啟三件必須同一次做完（2026-09-12 起）

**不准拆開執行**：不准「先 `git pull` 備料、之後再 migration、再重啟」。三件由同一個人、同一次登入、一口氣做完，中間不留任何「拉了但沒套」的狀態。2026-09-12 差點拆開（agent 先拉了工作樹，服務還是舊程序），以下是查證出來的三個原因，每一條單獨都足以禁止拆開：

1. **啟動不檢查 schema 版本。** `backend/src/ching_tech_os/main.py` 沒有任何 alembic revision 比對，新程式碼配舊 schema 會靜默起來、health 回 200，要等到有人點往來對象或物料才炸；現場看起來是「昨天還好好的」，最難查。
2. **systemd unit 的 `ExecStartPre` 會自動跑 `uv run alembic upgrade head`。** 所以工作樹一旦拉到含新 migration 的版本，任何非計畫的重啟（斷電、重開機、OOM、`Restart=on-failure` 觸發、有人手動 restart）都會在沒人看的時候把 migration 與新程式碼一起上線。「拉了不重啟」不是備料，是埋雷。
3. **舊桌面靜態檔是活的。** `main.py` 用 `StaticFiles` 直接掛 `frontend/js|css|fonts|assets`，`index.html`／`login.html` 每次請求讀檔，`FRONTEND_DIR` 指向工作樹。`git pull` 的當下舊桌面就換成新版，不需要重啟；2026-09-12 就這樣讓 `desktop.js` 的 ERPNext 圖示在 ERP 模組上線前先消失。

選項 A 那句「`alembic current` 仍是 029，不要 upgrade」只對選項 A 成立（那四支不動 schema）；選項 B 動了 030 起的 schema，不能照抄。

對外驗證線上端點一律帶 `/ctos` 前綴（`https://ching-tech.ddns.net/ctos/api/...`）並看 content-type 是不是 `application/json`：不帶前綴會 301 到公司官網回 200 的 HTML，狀態碼是假的。

## 先看這段：這批裡有四支是安全修補，性質與其他不同

其餘 PR（#192／#194／#196／#198／#202）是新功能，現在不部署只是「功能還沒上」，沒有人在等。下面三支是**關掉現在對外開著的洞**——LINE／Telegram bot 是公開的，任何人加了帳號就能問：

| PR | 現在不部署的話，實際上誰能做到什麼 |
|---|---|
| #206 | 沒綁 CTOS 帳號的陌生人透過 bot 用 `search_nas_files`／`read_document` **讀 NAS 上的檔案內容**（正式機現在就是這樣）。同一支也擋專案、往來對象、物料工具，但那些工具在正式機還沒部署，所以那部分現在還碰不到。 |
| #212 | 陌生人用 `add_note` **匿名寫進擎添的全域知識庫**（沒有人掛名，事後追不到，agent 之後會把那些內容當公司資料用）；任何使用者（含已綁定的）只要 agent 帶別人的群組／使用者 id，就能**讀寫別人的記憶**（模型宣稱身分即可）。 |
| #216 | 任何呼叫者能把讀不到的知識條目或 NAS 檔案**做成公開分享連結**。目前正式機沒有 agent 明列分享工具、沒有群組掛自訂 agent，所以現在打不到，但同一家族。 |
| #219 | 任何已登入的員工（不需是擁有者、不需管理員）能把公司**任何一則 global／project 知識條目或 NAS 檔案做成公開連結發到網際網路上**；舊桌面的分享按鈕走的 REST 端點只驗登入沒驗權限。連結發出去收不回、不知道誰看過。 |

### 選項 A：只部署安全修補（不動 ERP 那批）

**查證結果**：#206、#212、#216、#219 都**不動 schema、沒有 migration**，只加權限檢查、環境變數注入、資源存取檢查與預設值。我從 .11 現在的 commit `0b982f1` 切了 `hotfix/unbound-guards` 分支（`f1aaafb`，已推到 origin），cherry-pick 這四支，把測試裡指到此分支沒有的 ERP／專案工具的部分去掉，**全套 1921 passed、覆蓋率 90.24%**。不是理論上可分開，是跑過的。

在這條分支上實際生效的是：未綁定者不能用 NAS 檔案工具、不能 `add_note`、記憶工具改用伺服器注入的身分（LINE 與 Telegram 都接上）；分享連結要先通過資源存取檢查；`share-manager` 預設關閉，REST 建連結端點與 `send_nas_file`／`prepare_file_message` 間接建連結都要這個權限。專案／往來對象／物料那幾個 app 的擋法也在，但工具本身不在此分支，等於備而不用。

指令（與一般部署相同，少了 migration 與前端 build）：
```bash
ssh ct@192.168.11.11
cd ~/SDD/ching-tech-os && git log --oneline -1          # 應為 0b982f1
git fetch origin && git checkout hotfix/unbound-guards   # f1aaafb
cd backend && uv sync --extra voice
uv run alembic current                                   # 仍是 029，不要 upgrade（只對選項 A 成立，選項 B 不能照抄，見最上面的硬規則）
sudo systemctl restart ching-tech-os
for i in $(seq 1 20); do curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8088/api/health | grep -q 200 && break; sleep 3; done
systemctl is-active ching-tech-os
```
驗證：
1. 用一個**沒綁** CTOS 帳號的 LINE 帳號問 bot「幫我記一筆：測試」→ 應回「請先綁定」而不是寫入；問「搜尋 NAS 上的圖面」→ 同樣被擋。
2. 用**已綁定**帳號問同兩句 → 正常。
3. `journalctl -u ching-tech-os --since "10 minutes ago" | grep -E "模型帶入的 id|已改用連線身分"` 看記憶工具有沒有覆寫紀錄（有就代表注入生效）。
4. 舊桌面 AI 助手開一次能對話。
5. 分享：已綁定但沒開 `share-manager` 的帳號（部署後**重新登入**）在舊桌面知識庫按「分享」→ 應顯示「無「分享管理」功能權限」；admin 或已開權限者可以建。
6. 部署後**通知同事重新登入**：`share-manager` 預設改 False 只在重登後套用，登入中的 session 最多 8 小時仍能分享；要讓某人繼續分享，管理員到新前端使用者管理頁開 `share-manager` 後那個人也要重登。

退路：`git checkout 0b982f1 && sudo systemctl restart ching-tech-os`，沒有 schema 要退。

之後要上 ERP 全套時：`git checkout main && git pull --ff-only`，再走選項 B。hotfix 分支的 commit 不在 main 上（是 cherry-pick），切回 main 不會衝突。（#216、#219 已 cherry-pick 進去，見最上面的維護規則段。）

### 選項 B：一次全套

就是下面第 1～7 節。安全修補三支已含在 main。

## 0. 現況（2026-09-12 查證）

**2026-09-12 中午更新**：.11 的工作樹已被 agent 拉到 main `9166918`（含 #227–#233），`uv sync` 與前端 build 也跑了；服務仍是 2026-09-11 22:24 啟動的舊程序（`0b982f1`），alembic 029。這正是上面硬規則禁止的「拉了但沒套」狀態，雷已埋。數字（2026-09-12 查證）：

| 項目 | 值 |
|---|---|
| 工作樹 | `9166918`（#233 補齊 bot 身分注入與十八支工具的權限收尾） |
| 線上跑的 | `0b982f1`（2026-09-11 22:24 啟動） |
| 兩者相差 | 29 個 commit，含 `535dd1d` 整個 erp 模組 |
| 夾在中間的 migration | 030 erp_module、031、032、033，外加 `seed_data.sql` |
| 資料庫 | alembic 029 |

所以任何非計畫重啟（斷電、重開機、OOM、`Restart=on-failure`、有人手動 restart）都會在沒人看的情況下一次套四支 migration 加 29 個 commit 的程式碼上線。處理方式二選一，由 yazelin 決定：立刻照 §3 做完 migration 與重啟；或先把工作樹退回 `0b982f1`（`git checkout 0b982f1`）等之後一次做完；**退回本身也是寫正式機**，靜態檔會跟著退、ERPNext 圖示會回來，等於第二次沒人看的變化，所以這也只能由 yazelin 本人做，agent 不做。以下原文是拉之前的狀態。



| 項目 | .11 正式機 | main |
|---|---|---|
| HEAD | `0b982f1`（#189，2026-09-11 22:2x 部署） | `#202` 合併後 |
| alembic | `029 (head)` | 033 |
| 已上線 | #186 授權缺口、#188 專案模組後端、#189 ai_logs.user_id | — |
| 另外裝好的 | ERPNext 每日備份腳本與 `backup-erpnext.timer`（#190，不經部署流程） | — |

專案頁（os.ching-tech.com/projects）後端已在線上，`/api/projects` 回 401 不是 404。

## 0b. 2026-09-12 下午到晚間合併、尚未部署的後端 PR（會跟著下一次部署一起上）

| PR | 內容 | 部署時要注意 |
|---|---|---|
| #227 #228 #229 #230 | #220 文件、#211 附件描述、#199 舊桌面 requires_app 清單、#218 分享連結 created_by | 無 |
| #233 | #209 bot 身分注入補齊、#210 十八支工具權限收尾、`browse_webpage` SSRF 阻擋 | 未綁定者可用工具從 25 支降到 17 支；bot 對未綁定者的行為會變 |
| #238 | #237 種子資料 tenant id | 只影響全新安裝 |
| #245 | #240 jsonb 雙重編碼：寫入端傳 dict、讀取端新舊都吃、preferences 字串列剝殼合併 | **PG 版本下限變 16**（`pg_input_is_valid`）；既有壞列不會自動修，見 #244 |
| #258 | #255 `/api/login-records/stats` 必 500（days 以 int 串 INTERVAL）改 `make_interval` | 新前端登入紀錄頁的統計卡部署後才會有數字 |
| #263 | #262 `/api/config/apps` 與 `/api/skills/{name}/frontend/{path}` 加登入（舊桌面附 `?token=`） | **部署後舊桌面開一次 NVR／HIS 的 skill app 確認還載得到** |

## 1. 待部署 PR 與對使用者可見的影響

| PR | 做了什麼 | 使用者看得到的 |
|---|---|---|
| #192 | 往來與物料模組後端：十張表、23 支 MCP 工具、REST `/api/parties`、`/api/items`、`/api/warehouses`、`/api/stock`、`/api/purchase-orders` | 新前端往來對象、物料庫存、採購單、首頁待收貨卡從「連線失敗」變可用（表是空的，要等匯入） |
| #194 | web 聊天 `ai_response` 帶 `toolCalls`／`toolTimings`，訊息存 `tool_calls`，`prompt_name` 預設對齊 | 新前端 AI 助手頁看得到「agent 做了什麼」的時間軸；舊桌面 AI 助手不受影響（只讀 `message`） |
| #196 | 往來對象聯絡人／地址編輯刪除端點、搜尋含聯絡人電話、role=both | 往來對象頁的編輯／刪除／設主要可用 |
| #198 | bot prompt、skills、CLI、舊桌面切到新模組；`requires_app` 支援清單 | **LINE／Telegram bot 開始用新工具**回答廠商／物料／庫存／採購問題；舊桌面少了 ERPNext 圖示；CLI 0.2.0 |
| #202 | 專案模組 MCP 工具九支，bot prompt 專案段改工具指引 | bot 能代查專案、開任務、完成里程碑（成員才能寫） |
| #206（**安全修補**） | 未綁定 CTOS 帳號的 bot 使用者不得使用專案、往來對象、物料庫存、檔案工具（issue #201，既有缺口） | LINE／Telegram 未綁定者問專案／廠商／NAS 檔案會得到「請先綁定」；已綁定者不變。**無 migration，建議與這批一起上，且不要晚於 #192／#202** |
| #212（**安全修補**） | 未綁定者不得寫入知識庫（#207）、記憶工具改用伺服器注入身分（#204）、MCP 工具存取矩陣 | 未綁定的 LINE／Telegram 使用者 `add_note` 會得到「請先綁定」；記憶工具不再信模型帶入的群組／使用者 id；已綁定者不變。**無 migration** |
| #216（**安全修補**） | 分享連結先通過資源存取檢查、兩支分享工具對到 `share-manager`、未綁定拒絕（#205） | bot 分享不到讀不到的東西 |
| #219（**安全修補**） | `share-manager` 預設 False；REST 建連結與 `send_nas_file`／`prepare_file_message` 間接建連結都要此權限（#217） | 沒開權限的同事不能再建公開連結；**要重新登入才套用** |
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
4b. 部署前先查正式庫 `ai_agents.tools` 有沒有網頁聊天 agent 帶 `add_note`（網頁路徑沒注入 `ctos_user_id`，會對已登入者回「請先綁定」；dev 庫的 web-chat-default／web-chat-code 是空的）：`docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -Atc "select name, tools from ai_agents where tools::text ilike '%add_note%'"`。
4a. 未綁定防護（#206）：用一個沒綁 CTOS 帳號的 LINE 帳號問「查一下有哪些專案」，應回「請先綁定」而不是資料；同一句用已綁定帳號問要有回覆。
5. **LINE bot 還能回話**：請 yazelin 用自己的 LINE 傳「你好」與「查一下有哪些專案」，兩句都要有回覆（第二句在匯入前會說沒有資料）。這是每天有人在用的東西，最優先。
6. 新前端：AI 助手頁送一句話有回覆且有工具時間軸；往來對象頁打開是空清單不是錯誤。
7. 舊桌面：AI 助手開一次能對話；桌面沒有 ERPNext 圖示。

## 5. 會打斷正在使用的人

- **CLI 使用者**：`ctos` CLI 要升到 0.2.0（`uv tool install ./cli` 重裝）；舊版的 `erp` 子命令打 `/api/erp` 在 extends/erpnext 停用前仍可用，停用後 404。
- **bot 使用者**：不需重登；但 032 之後 bot 對廠商／物料問題會改用新工具，匯入前新表是空的，會回「找不到」——所以**部署與匯入要接著做**，中間不要隔太久。
- **舊桌面開著的分頁**：這批沒改 socket 流程，不需重新整理；ERPNext 圖示要重新整理才消失。
- **需要重新登入**：#219 把 `share-manager` 預設改成 False，已登入 session 帶著登入時的權限快照，最多 8 小時 TTL 內仍能分享；管理員新開的權限同樣要重登才生效；PAT 每次請求重算，不受影響。舊桌面的「分享管理」圖示重登後才會依權限消失。
- 不會打斷：專案頁、知識庫、AI Log。

## 6. 退路

- 服務起不來：`sudo systemctl status ching-tech-os`、`journalctl -u ching-tech-os -n 100`；`git checkout 0b982f1 && cd backend && uv run alembic downgrade 029 && sudo systemctl restart ching-tech-os`；仍不行就 `pg_restore` 前置那份 dump。
- 只退某一支：見第 2 節各自的 `downgrade`。
- **匯入之後**就不要退 030（會刪匯入資料），改用往前修。

## 7. 部署後接著做（各自另外授權）

1. **匯入**（#197）：`cd ~/SDD/ching-tech-os/backend && DB_NAME=ching_tech_os uv run python ../scripts/erpnext_import.py --src /mnt/nas/ctos/erpnext-backup/$(cat /mnt/nas/ctos/erpnext-backup/LATEST)/doctypes --dry-run`，看 `import-report.json` 沒有 errors 與 merge_review 再拿掉 `--dry-run` 正式跑一次；對數（parties 約 1035、contacts 約 1008、items 117、warehouses 4、stock 76）；重跑一次應零寫入。ERPNext 進入唯讀過渡期兩週。
2. **停用 ERPNext**（PR 8，尚未做）：移除 `extends/erpnext` submodule（它的三個 skill 只停容器關不掉）、`.env` 三個 ERPNEXT 變數、MCP server 註冊、`/api/erp` proxy；停九個 erpnext 容器保留 volume 四週；備份 timer 最後跑一次後停。
