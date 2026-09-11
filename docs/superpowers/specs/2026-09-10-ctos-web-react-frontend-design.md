# ctos-web：全公司用的新前端（React）設計

日期：2026-09-10
狀態：設計已拍板，待實作計劃

## 背景

現有 Web 桌面是純 JS 視窗式介面（43 支檔案、約 2.4 萬行），實際每月只剩一人登入；公司真正在用的是 LINE bot 那一層。管理層決定要一套全公司使用的新前端，同時停用 ERPNext，專案進度要回到自己的系統掌握。

本 spec 定義新前端 ctos-web 第一版的範圍、部署、帳號模型與後端改動。舊桌面不動，兩套前端並行，共用同一個後端。

## 決策摘要

| 項目 | 決定 |
|------|------|
| 框架 | React（非 Vue）。理由：AI 產碼錯誤率低、shadcn/ui 現成側邊欄版型、mori-desktop 已在用 React |
| 技術棧 | Vite、React、TypeScript、Tailwind、shadcn/ui、react-router、TanStack Query |
| 程式碼位置 | 新 repo `ching-tech/ctos-web`，公開（org 為 Free 方案，Pages 只給公開 repo） |
| 部署 | GitHub Pages，Actions 建置。自訂網域 `os.ching-tech.com`，Cloudflare DNS CNAME 指 `ching-tech.github.io`，DNS only |
| 後端 | 不搬，留在 `yazelin/ching-tech-os`，正式機 192.168.11.11，對外 `https://ching-tech.ddns.net/ctos` |
| 費用 | 零 |

不放 `yazelin.github.io`：那是所有專案頁共用的 origin，登入 token 會被其他頁讀到。

## 一、架構與部署

- 前端建置時以環境變數 `VITE_API_BASE` 注入 API 位址，正式為 `https://ching-tech.ddns.net/ctos`，本機開發可指本機後端。
- 認證沿用 Bearer token 放 localStorage（現有機制），跨網域無 cookie 問題。401 時清 token 導回 `/login` 路由。
- Socket.IO 後端已開放全部 origin；第一版四個模組不用即時通道，以 TanStack Query 輪詢代替。
- 後端 CORS 清單（`settings.cors_origins`，環境變數可覆寫）加入 `https://os.ching-tech.com`。
- Pages 是單頁應用，路由 fallback 用 `404.html` 複製 `index.html` 的慣用法。
- 舊桌面一行不改。新前端可用後再公告切換；舊桌面下線時間另議。

## 二、版型與導覽

- 左側邊欄固定，模組順序：首頁、知識庫、專案、Bot 管理、AI Log、使用者管理（僅 admin）、設定。可收合成純圖示列；手機寬度縮成抽屜。
- 右欄依路由切換。每個模組進入先是該模組 dashboard，再鑽到清單與明細。所有畫面有網址（例 `/projects/12`），可直接分享。
- 首頁 dashboard 面向管理層：進行中專案與逾期里程碑、今日 AI 用量、最近知識庫更新。
- 設計語彙沿用 `docs/design-system.md` 的 CSS 變數（主色 `#0891b2`、強調色 `#ea580c`、狀態色），亮暗主題照舊，新舊兩套視覺一致。

## 三、第一版模組

### 帳號

- 登入頁兩個分頁：「NAS 帳號」與「平台帳號」。
- 個人設定頁可綁定與解綁 NAS（輸入 NAS 帳密，驗過即綁）；LINE 綁定沿用現有綁定碼流程。
- admin 有使用者管理：建立平台帳號、重設密碼、停用、權限。

### 知識庫

清單、搜尋、閱讀、Markdown 編輯、附件、版本歷史、分享連結、scope（personal / project / global）切換。全部沿用 `/api/knowledge`，後端零改動。

### Bot 管理

群組清單與設定、訊息記錄、用戶綁定、黑名單、Agent 設定。沿用現有 `/api/admin`、`/api/admin/bot-settings`、`/api/ai` 端點。

### AI Log

用量統計、依用戶與 Agent 篩選、明細。沿用 `/api/ai/logs` 與 `/api/ai/logs/stats`。

### 專案（重建）

核心是管理層看進度。

- 專案主檔：名稱、客戶、狀態、負責人、起迄日、描述。
- 成員：使用者與角色。
- 里程碑：名稱、預定日、實際完成日、狀態。
- 任務：標題、負責人、狀態、到期日、所屬里程碑（可空）。
- 進度百分比：由任務完成數計算，不手填。
- 會議紀錄與附件不重做：以知識庫 project scope 條目掛在專案底下，專案頁列出相關條目。

明確不在第一版：檔案管理、終端機、程式編輯器、物料庫存、記憶管理、排程、語音、簡報、發包期程、廠商主檔。這些留在舊桌面。

> **部分推翻（2026-09-12）**：「物料庫存」與「廠商主檔」兩項改由 `2026-09-12-ai-native-erp-design.md`（往來與物料模組，取代 ERPNext）在新前端實作，後端 PR #192 已合併。依據：管理層 2026-09-12 決定自建 AI native 類 ERP，原話見該規格第一節。其餘項目仍留在舊桌面。

## 四、後端改動

### 帳號模型

- `users` 表加 `nas_username`（可空、唯一）。遷移時既有帳號一律回填 `nas_username = username`（現有帳號全部源自 NAS）。
- `LoginRequest` 加 `method: "nas" | "local"`，預設 `nas` 以相容舊前端。
  - `nas`：SMB 驗證；依 `nas_username` 找使用者，找不到就建帳號並綁定，session 照舊存加密 SMB 密碼。
  - `local`：只驗 `password_hash`，不 fallback 到 SMB；session 不存 SMB 密碼。
- 新增 `POST /api/user/me/nas-binding`（驗 SMB 帳密後寫入 `nas_username`）與 `DELETE` 解綁。
- 依賴 SMB 憑證的 API（`/api/nas`、`/api/files`）對 session 無 SMB 密碼者回 403，訊息提示去綁定 NAS。
- PAT 行為不變。

### 專案模組

新增四張表：`projects`、`project_members`、`milestones`、`tasks`，Alembic 遷移。新增 `/api/projects` 路由，CRUD 加進度計算。二月移除的 `api/project.py`（commit 64b9c6b 前）從 git 取回當參考，不照抄。權限：所有登入者可讀；建立與編輯限 admin 與專案成員。

### CORS

`CORS_ORIGINS` 環境變數加 `https://os.ching-tech.com`；更新 `docs/backend.md` 環境變數表與 `.env.example`。

## 五、驗收與節奏

- 後端：現有 pytest 與 85% coverage 門檻（CI workflow 為準）。帳號模型與專案 API 各補測試。
- 前端：Playwright 冒煙，跑真後端：兩種登入、四個模組各開一頁、404 路由 fallback。
- 每個 PR 附驗證清單。trunk-based 短命 branch，PR 開了設 auto-merge。
- 順序：
  1. 後端：帳號模型 + CORS（一個 PR）。
  2. 前端：repo、骨架、側邊欄、登入、Pages 部署與網域。
  3. 知識庫（後端零改動，最快看到成果）。
  4. Bot 管理、AI Log。
  5. 專案模組（前後端都新寫）。
  6. 首頁 dashboard（等前面資料源都有了才做）。

## 獨立一條線：ERPNext 資料搬出

不等前端，隨時可做。寫一支腳本把 ERPNext 全部 doctype 匯成 JSON 與 CSV 到 NAS 備份區，與 `scripts/backup-knowledge-to-nas.sh` 一起排程。之後專用簡化 ERP 依真實需求另開 spec；第一版專案模組可選擇把 ERPNext 的 Project 匯入當種子資料。

> **進度（2026-09-12）**：備份已上線（PR #190，`backup-erpnext.timer` 每天 03:30，見 `docs/erpnext-backup.md`）。「專用簡化 ERP 另開 spec」已成為 `2026-09-12-ai-native-erp-design.md`，範圍從「之後再說」提前為現行工作，依據同上。

## 風險

- `ching-tech.ddns.net` 全站掛掉時先查 DDNS 漂移，不是憑證（既有教訓）。
- 登入頁掛在公開網域，API 本來就對外，攻擊面沒有變大，但要確認登入失敗記錄與頻率限制照常運作。
- 舊桌面與新前端並行期間，帳號模型的遷移必須讓舊登入完全不變（`method` 預設 `nas`）。
