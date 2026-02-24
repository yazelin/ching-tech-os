## ADDED Requirements

### Requirement: 查詢影片資訊
Skill SHALL 提供 `get_video_info` script，同步查詢影片 metadata（不下載）。

#### Scenario: 查詢 YouTube 影片資訊
- **WHEN** AI 呼叫 `run_skill_script(skill="media-downloader", script="get-video-info", input='{"url":"https://www.youtube.com/watch?v=xxx"}')`
- **THEN** 系統回傳 JSON 包含 `title`、`duration`（秒）、`formats`（可用格式列表）、`thumbnail`、`uploader`
- **AND** 不下載任何檔案

#### Scenario: 查詢 X (Twitter) 影片資訊
- **WHEN** AI 呼叫 `get-video-info` 並傳入 X 貼文 URL
- **THEN** 系統回傳影片 metadata（標題可能為貼文文字）

#### Scenario: 無效 URL
- **WHEN** AI 傳入不支援的 URL 或無影片的頁面
- **THEN** 系統回傳 `{"success": false, "error": "不支援的 URL 或找不到影片"}`

---

### Requirement: 非同步下載影片
Skill SHALL 提供 `download_video` script，以非同步方式下載影片到 CTOS 暫存區。

#### Scenario: 啟動下載（立即回傳 job ID）
- **WHEN** AI 呼叫 `run_skill_script(skill="media-downloader", script="download-video", input='{"url":"...","format":"mp4"}')`
- **THEN** Script 在 3 秒內回傳 `{"success": true, "job_id": "<uuid8>", "status": "started"}`
- **AND** 下載在背景程序中繼續執行

#### Scenario: 指定輸出格式
- **WHEN** input 包含 `"format": "mp3"`
- **THEN** yt-dlp 下載音訊並轉為 mp3 格式

#### Scenario: 預設格式
- **WHEN** input 未指定 format 或指定 `"format": "mp4"`
- **THEN** yt-dlp 下載最佳品質的 mp4 影片（bestvideo+bestaudio/best，合併為 mp4）

#### Scenario: 檔案大小超過限制
- **WHEN** 下載過程中檔案超過 500 MB
- **THEN** 系統中止下載、清理暫存檔案
- **AND** 狀態更新為 `{"status": "failed", "error": "檔案超過 500 MB 限制"}`

#### Scenario: 下載完成
- **WHEN** 背景程序下載完成
- **THEN** 狀態檔更新為 `{"status": "completed", "ctos_path": "ctos://linebot/videos/{date}/{uuid}/{filename}"}`

#### Scenario: 下載失敗
- **WHEN** yt-dlp 回報錯誤（網路問題、地區封鎖、需登入等）
- **THEN** 狀態檔更新為 `{"status": "failed", "error": "<錯誤訊息>"}`

---

### Requirement: 查詢下載狀態
Skill SHALL 提供 `check_download` script，查詢背景下載的進度與結果。完成時 SHALL 同時回傳虛擬路徑（`ctos_path`）與絕對路徑（`file_path`），使 AI 可直接定位檔案。

#### Scenario: 查詢進行中的下載
- **WHEN** AI 呼叫 `run_skill_script(skill="media-downloader", script="check-download", input='{"job_id":"a1b2c3d4"}')`
- **AND** 下載正在進行中
- **THEN** 系統回傳 `{"status": "downloading", "progress": 45.2, "filename": "video.mp4"}`

#### Scenario: 查詢已完成的下載
- **WHEN** 下載已完成
- **THEN** 系統回傳 `{"status": "completed", "ctos_path": "ctos://...", "file_path": "/mnt/nas/ctos/...", "file_size": 123456789, "filename": "video.mp4"}`
- **AND** `file_path` 為透過 `PathManager.to_filesystem(ctos_path)` 轉換的絕對路徑
- **AND** 若 `file_path` 轉換失敗，回傳結果 SHALL 不包含 `file_path` 欄位但不影響其他欄位

#### Scenario: 查詢不存在的 job
- **WHEN** job_id 不存在或狀態檔遺失
- **THEN** 系統回傳 `{"success": false, "error": "找不到下載任務"}`

#### Scenario: 下載逾時判定
- **WHEN** 狀態檔的 `updated_at` 超過 10 分鐘未更新
- **AND** status 仍為 `downloading`
- **THEN** 系統回傳 `{"status": "failed", "error": "下載逾時（超過 10 分鐘無進度）"}`

---

### Requirement: Skill 定義與權限
Skill SHALL 以 `SKILL.md` 定義 metadata，遵循 Agent Skills 標準。SKILL.md SHALL 包含 AI 行為指引，明確說明路徑使用方式。

#### Scenario: Skill 載入
- **WHEN** 系統啟動或 reload skills
- **THEN** `media-downloader` Skill 被載入
- **AND** 包含 3 個 scripts：`get-video-info`、`download-video`、`check-download`

#### Scenario: 權限控管
- **WHEN** 使用者不具備 `file-manager` app 權限
- **THEN** 系統拒絕執行任何 media-downloader script

#### Scenario: SKILL.md 結構
- **WHEN** 讀取 SKILL.md
- **THEN** frontmatter 包含 `name: media-downloader`、`requires_app: file-manager`、`mcp_servers: ching-tech-os`

#### Scenario: SKILL.md 路徑指引
- **WHEN** AI 讀取 SKILL.md 的 check-download 說明
- **THEN** 說明 SHALL 包含：完成時回傳 `ctos_path` 和 `file_path`
- **AND** 說明 SHALL 指引 AI 在後續操作（如轉逐字稿）中使用 `ctos_path` 作為 `source_path`
- **AND** 說明 SHALL 明確禁止 AI 自行猜測或拼湊路徑

---

### Requirement: 儲存路徑與狀態追蹤
下載的影片 SHALL 存放在 CTOS zone，並以狀態檔追蹤進度。

#### Scenario: 儲存路徑格式
- **WHEN** 啟動一個新的下載任務
- **THEN** 建立目錄 `ctos://linebot/videos/{YYYY-MM-DD}/{uuid8}/`
- **AND** 影片檔案存於該目錄下

#### Scenario: 狀態檔格式
- **WHEN** 下載任務建立
- **THEN** 在同一目錄建立 `status.json`
- **AND** 包含 `job_id`、`status`、`progress`、`filename`、`file_size`、`ctos_path`、`error`、`created_at`、`updated_at` 欄位

#### Scenario: 進度更新頻率
- **WHEN** 下載進行中
- **THEN** 狀態檔每 5 秒或每 5% 進度更新一次（取先到者）
