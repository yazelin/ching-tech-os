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
   - 完成時回傳：`ctos_path`（用於歸檔、傳給 transcribe 等 CTOS 操作）、`file_path`（絕對路徑，可直接定位檔案）

**典型使用流程：**
1. 使用者提供影片 URL
2. 呼叫 get-video-info 查詢資訊，回報給使用者
3. 使用者確認後，呼叫 download-video 啟動下載
4. 呼叫 check-download 查詢進度，完成後取得 `ctos_path` 和 `file_path`
5. **回覆使用者時務必包含 `ctos_path`**，確保對話歷史中保留完整路徑供後續引用
6. 若使用者要轉逐字稿，用 check-download 回傳的 `ctos_path` 作為 transcribe 的 `source_path`
7. 若使用者要歸檔，使用 archive_to_library 歸檔到「影片資料」分類

**AI 行為指引：**
- **嚴禁使用 sleep 等待下載完成**。下載大檔案可能需要數分鐘，啟動後查詢一次進度即可：
  - 若仍在下載中：回覆使用者目前進度百分比，請他稍後再詢問，**結束本次回應**
  - 若已完成：回報 ctos_path 並繼續後續操作（歸檔等）
  - 不要在同一次回應中反覆 sleep + check-download，這會導致超時
- **務必使用 check-download 回傳的路徑，禁止自行猜測或拼湊路徑**。後續操作（轉逐字稿、歸檔等）必須使用 check-download 回傳的 `ctos_path`，不要用 YouTube ID 或影片標題自行組合路徑
- **回報下載完成時，回覆中須包含 `ctos_path`**，這樣後續對話中才能引用正確路徑
