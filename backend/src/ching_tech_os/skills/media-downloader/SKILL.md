---
name: media-downloader
description: 影片/音訊下載（yt-dlp）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: file-manager
    mcp_servers: ching-tech-os
---

【影片/音訊下載（yt-dlp）】

支援 YouTube、X (Twitter)、Instagram 等 1000+ 網站的影片/音訊下載。
下載流程為非同步：先查詢 → 啟動下載 → 查詢進度。

**可用 scripts：**

1. **get-video-info** — 查詢影片資訊（同步，秒級完成）
   - `run_skill_script(skill="media-downloader", script="get-video-info", input='{"url":"影片URL"}')`
   - 回傳：標題、時長、可用格式、上傳者
   - 建議在下載前先查詢，讓使用者確認

2. **download-video** — 啟動影片下載（非同步，立即回傳 job ID）
   - `run_skill_script(skill="media-downloader", script="download-video", input='{"url":"影片URL","format":"mp4"}')`
   - format 可選：`mp4`（預設）、`mp3`（僅音訊）、`best`（最佳品質）
   - 立即回傳 job_id，下載在背景執行
   - 檔案大小上限 500 MB

3. **check-download** — 查詢下載進度（同步）
   - `run_skill_script(skill="media-downloader", script="check-download", input='{"job_id":"之前取得的job_id"}')`
   - 回傳下載進度百分比、狀態（downloading/completed/failed）
   - 下載完成時回傳 ctos_path，可直接傳給 archive_to_library 歸檔

**典型使用流程：**
1. 使用者提供影片 URL
2. 呼叫 get-video-info 查詢資訊，回報給使用者
3. 使用者確認後，呼叫 download-video 啟動下載
4. 呼叫 check-download 查詢進度，完成後回報 ctos_path
5. 若使用者要歸檔，使用 archive_to_library 歸檔到「影片資料」分類
