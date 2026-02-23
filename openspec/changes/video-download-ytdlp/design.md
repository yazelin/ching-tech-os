## Context

CTOS 已有完整的 Skill 系統（script-first 架構）和檔案下載/歸檔流程（`download_web_file` → `archive_to_library`）。現在要新增影片下載能力，利用 yt-dlp CLI 工具處理 YouTube、X 等平台的影片解析與下載。

現有相關元件：
- **ScriptRunner**：在隔離 temp 目錄執行 skill scripts，預設 30 秒 timeout
- **PathManager**：統一路徑格式（`ctos://`、`shared://`），解析到實際檔案系統路徑
- **download_web_file**：HTTP 直接下載，存到 `ctos://linebot/web-downloads/{date}/{uuid}/`
- **archive_to_library**：從 CTOS zone 複製到 `shared://library/{category}/{folder}/`
- **LIBRARY_CATEGORIES 白名單**：目前有 6 類（技術文件、產品資料、教育訓練、法規標準、設計圖面、其他）

## Goals / Non-Goals

**Goals:**
- 透過 AI 助手一句話下載 YouTube/X 等平台影片
- 下載後取得 `ctos://` 路徑，可無縫銜接 `archive_to_library` 歸檔
- 以 Skill 封裝，可透過 SkillHub 安裝/更新
- 支援格式選擇（mp4/mp3/best）

**Non-Goals:**
- 不做影片串流播放或線上預覽
- 不做影片轉碼（僅使用 yt-dlp 內建的格式合併）
- 不做批次下載（播放清單/頻道）— 第一版只支援單一影片 URL
- 不做前端 UI — 完全透過 AI 對話操作

## Decisions

### 1. Skill script 直接寫檔到 NAS，而非透過 stdout 回傳

**選擇**：Script 直接寫入 `ctos://linebot/videos/` 對應的檔案系統路徑
**替代方案**：Script 透過 stdout 回傳檔案內容，由 MCP fallback 處理
**原因**：
- 影片檔案可能數百 MB，無法透過 stdout pipe
- Script 可 import `ching_tech_os.config.settings` 取得 `ctos_mount_path`（ScriptRunner 已設定 PYTHONPATH）
- 與 `download_web_file` 相同的儲存模式，路徑命名一致

### 2. 兩階段架構：先查詢再非同步下載

**選擇**：拆成兩個 script，查詢同步、下載非同步
**替代方案 A**：同步下載，加長 timeout 到 300 秒
**替代方案 B**：Socket.IO 即時進度推送
**原因**：

同步方案行不通 — 多層 timeout 限制：
- ScriptRunner 預設 30 秒（可調）
- Claude CLI 呼叫層 180 秒（`claude_agent.py`）
- 即使 script timeout 調大，上層 MCP → Claude CLI 鏈路也會截斷
- 影片下載時間不可預測（網速、影片長度），同步等待不可靠

**兩階段設計**：

**階段 1 — `get_video_info.py`（同步，秒級完成）**：
- 呼叫 yt-dlp 的 `extract_info(download=False)` 取得影片 metadata
- 回傳：標題、時長、可用格式、預估大小
- AI 可據此向使用者確認是否下載

**階段 2 — `download_video.py`（非同步，背景執行）**：
- Script 收到參數後立即回傳 job ID（`{"success": true, "job_id": "xxx", "status": "started"}`）
- 使用 `asyncio.create_task()` 在背景執行 yt-dlp 下載
- 下載完成後寫入狀態檔（JSON），AI 可透過第三個 script 查詢
- 或：Script 本身 fork 成背景程序，主程序立即退出回傳 job ID

**階段 2b — `check_download.py`（同步，查詢下載狀態）**：
- 讀取狀態檔，回傳進度或完成路徑
- AI 可定期呼叫查詢，下載完成後告知使用者

**狀態追蹤**：下載狀態寫在 `ctos://linebot/videos/{date}/{uuid}/status.json`
```json
{
  "job_id": "a1b2c3d4",
  "status": "downloading|completed|failed",
  "progress": 45.2,
  "filename": "video-title.mp4",
  "file_size": 123456789,
  "ctos_path": "ctos://linebot/videos/2026-02-23/a1b2c3d4/video-title.mp4",
  "error": null
}

### 3. yt-dlp 作為 Python 套件安裝（非系統 CLI）

**選擇**：在 `pyproject.toml` 加入 `yt-dlp` 依賴，script 用 `import yt_dlp` 呼叫
**替代方案**：要求系統預裝 `yt-dlp` CLI，script 用 `subprocess` 呼叫
**原因**：
- Script 以 `uv run` 執行，自動使用專案虛擬環境
- Python API 比 subprocess 更可靠，可直接取得 metadata、進度、錯誤處理
- 部署更簡單，`uv sync` 就搞定，不需額外系統安裝步驟

### 4. 儲存路徑格式與 download_web_file 對齊

**選擇**：`ctos://linebot/videos/{YYYY-MM-DD}/{uuid8}/{filename}`
**原因**：
- 與 `download_web_file` 的 `ctos://linebot/web-downloads/` 模式一致
- 按日期分目錄，方便清理
- UUID 防止檔名衝突

### 5. 檔案大小限制 500 MB

**選擇**：最大 500 MB，超過時中止下載並回傳錯誤
**原因**：
- NAS 空間有限，避免意外下載超大影片
- `download_web_file` 限制 50 MB，影片合理放寬到 500 MB
- yt-dlp Python API 支援 `max_filesize` 選項

### 6. 圖書館新增「影片資料」分類

**選擇**：在 `LIBRARY_CATEGORIES` 白名單新增 `"影片資料"`
**原因**：
- 與現有分類風格一致（中文、四字）
- 明確區分影片和其他文件類型

### 7. Skill 放在 native skills 目錄

**選擇**：放在 `backend/src/ching_tech_os/skills/media-downloader/`
**替代方案**：放在 external `~/SDD/skill/media-downloader/`
**原因**：
- 這是核心功能，不是使用者自裝的外掛
- 跟著 git 版本控制，方便團隊同步
- 使用者仍可透過 external 覆蓋

## Risks / Trade-offs

- **yt-dlp 版本追趕**：YouTube 等平台經常更新反爬機制，yt-dlp 需定期更新 → 透過 `uv lock --upgrade-package yt-dlp` 快速更新
- **背景程序管理**：Script fork 的背景程序不受 ScriptRunner 管理 → 用狀態檔追蹤，若程序異常終止，status.json 會停留在 `downloading`，需設計逾時判定（如 10 分鐘無更新視為失敗）
- **NAS 磁碟空間**：影片比文件大得多 → 500 MB 上限 + 按日期存放方便清理
- **地區封鎖/需登入**：部分影片可能需要 cookies 或 VPN → 第一版不處理，回傳明確錯誤訊息
- **版權議題**：下載影片可能涉及版權 → 這是企業內部使用，由使用者自行判斷
- **並發下載**：多個使用者同時下載 → UUID 目錄隔離，不會衝突，但需注意頻寬
