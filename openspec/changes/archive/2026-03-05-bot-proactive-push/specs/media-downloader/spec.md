## MODIFIED Requirements

### Requirement: 非同步下載影片
Skill SHALL 提供 `download_video` script，以非同步方式下載影片到 CTOS 暫存區。start script SHALL 接受並持久化 `caller_context`，供主動推送使用。

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

#### Scenario: download-video 接受 caller_context
- **WHEN** AI 呼叫 `download-video` 時 input 包含 `caller_context` 欄位
- **THEN** script SHALL 將 `caller_context` 原樣寫入 `status.json`
- **AND** 下載完成後，背景程序 SHALL 呼叫 `/api/internal/proactive-push` 觸發通知

#### Scenario: 下載完成後觸發推送通知
- **WHEN** 背景下載程序寫入 `status: "completed"`
- **THEN** 程序 SHALL POST 至 `/api/internal/proactive-push`，帶入 `job_id` 與 `skill="media-downloader"`
- **AND** 推送訊息包含檔案名稱、大小與 ctos_path
