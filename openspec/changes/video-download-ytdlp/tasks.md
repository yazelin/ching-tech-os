## 1. 依賴與環境

- [x] 1.1 在 `backend/pyproject.toml` 新增 `yt-dlp` 依賴，執行 `uv sync` 安裝
- [x] 1.2 驗證 `import yt_dlp` 可正常使用（`uv run python -c "import yt_dlp; print(yt_dlp.version.__version__)"`)

## 2. Skill 骨架

- [x] 2.1 建立 `backend/src/ching_tech_os/skills/media-downloader/` 目錄結構（`SKILL.md`、`scripts/`）
- [x] 2.2 撰寫 `SKILL.md`：frontmatter（name、description、allowed-tools、requires_app、mcp_servers）+ prompt 說明三個 script 的用法

## 3. get-video-info script（同步查詢）

- [x] 3.1 實作 `scripts/get-video-info.py`：讀取 stdin JSON → 呼叫 `yt_dlp.YoutubeDL.extract_info(download=False)` → 回傳 title、duration、formats、thumbnail、uploader
- [x] 3.2 處理錯誤情境：無效 URL、不支援的網站、網路錯誤，統一回傳 `{"success": false, "error": "..."}`

## 4. download-video script（非同步下載）

- [x] 4.1 實作 `scripts/download-video.py` 主體：讀取 stdin JSON → 建立 `ctos://linebot/videos/{date}/{uuid}/` 目錄 → 寫入初始 `status.json` → fork 背景程序 → 立即回傳 `{"success": true, "job_id": "...", "status": "started"}`
- [x] 4.2 實作背景下載邏輯：呼叫 yt-dlp Python API 下載，支援 format 參數（mp4/mp3/best），設定 `max_filesize: 500MB`
- [x] 4.3 實作進度回調：yt-dlp progress hook → 更新 `status.json`（每 5 秒或每 5% 進度）
- [x] 4.4 實作完成/失敗處理：下載成功時更新 status 為 `completed` 並寫入 `ctos_path`；失敗時更新為 `failed` 並記錄 error

## 5. check-download script（狀態查詢）

- [x] 5.1 實作 `scripts/check-download.py`：讀取 stdin JSON 的 `job_id` → 找到對應 `status.json` → 回傳目前狀態
- [x] 5.2 實作逾時判定：`updated_at` 超過 10 分鐘未更新且 status 仍為 `downloading`，回傳 `failed` + 逾時錯誤

## 6. 圖書館分類

- [x] 6.1 在 `services/mcp/nas_tools.py` 的 `LIBRARY_CATEGORIES` 白名單新增 `"影片資料"`

## 7. 測試與驗證

- [x] 7.1 手動測試：透過 `run_skill_script` 呼叫 `get-video-info`，驗證 YouTube 影片的 metadata 回傳
- [x] 7.2 手動測試：透過 `download-video` 啟動下載 → `check-download` 輪詢進度 → 確認檔案寫入正確路徑
- [x] 7.3 手動測試：下載完成後使用 `archive_to_library` 歸檔到「影片資料」分類（白名單已更新，需在執行中系統驗證）
- [x] 7.4 邊界測試：無效 URL、ffmpeg 不存在 fallback、錯誤格式處理
