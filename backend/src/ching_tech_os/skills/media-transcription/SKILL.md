---
name: media-transcription
description: 影片/音訊逐字稿轉錄（faster-whisper）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: file-manager
    mcp_servers: ching-tech-os
---

【影片/音訊逐字稿轉錄（faster-whisper）】

將影片或音訊檔轉錄為繁體中文逐字稿。使用 faster-whisper 本地語音辨識，免費、無需 API 金鑰。
轉錄流程為非同步：啟動轉錄 → 查詢進度 → 取得逐字稿。

**可用 scripts：**

1. **transcribe** — 啟動轉錄（非同步，立即回傳 job ID）
   - `run_skill_script(skill="media-transcription", script="transcribe", input='{"source_path":"ctos://linebot/videos/2026-02-23/a1b2c3d4/video.mp4"}')`
   - source_path：要轉錄的音訊/影片檔路徑（支援 `ctos://`、`shared://` 等格式）
   - 可選參數 model：whisper 模型大小（base/small/medium/large-v3，預設 small）
   - 支援格式：影片（.mp4、.mkv、.webm）、音訊（.mp3、.m4a、.wav、.ogg、.flac）
   - 立即回傳 job_id，轉錄在背景執行

2. **check-transcription** — 查詢轉錄進度（同步）
   - `run_skill_script(skill="media-transcription", script="check-transcription", input='{"job_id":"之前取得的job_id"}')`
   - 回傳轉錄狀態（extracting_audio/transcribing/completed/failed）
   - 完成時回傳：file_path（逐字稿絕對路徑，可直接用 Read 工具讀取）、transcript_preview（前 500 字預覽）、duration（音訊時長）

**典型使用流程：**
1. 使用者透過 media-downloader 下載影片，取得 ctos_path
2. 呼叫 transcribe 啟動轉錄，取得 job_id
3. 呼叫 check-transcription 查詢進度，完成後取得 file_path（絕對路徑）和 transcript_preview
4. 用 Read 工具直接讀取 file_path 取得逐字稿全文。**不要用 read_document（不支援 .md）、不要用 get_nas_file_info（不需要，check-transcription 已回傳絕對路徑）**
5. 依使用者要求整理摘要/總結/重點筆記（若只需簡短摘要，transcript_preview 已有前 500 字，可直接使用不需讀全文）
6. 使用 add_note 存入知識庫，或 archive_to_library 歸檔到圖書館

**AI 行為指引：**
- 當使用者下載了影片/音訊後問「幫我整理內容」、「這在講什麼」等，主動建議先轉錄
- source_path 支援 `ctos://` 和 `shared://` 等路徑格式。來源可能是：media-downloader 的 check-download 回傳的 ctos_path、search_nas_files 搜尋結果（`shared://` 格式）、archive_to_library 回傳路徑（`shared://library/...` 格式）、list_library_folders 瀏覽結果、知識庫附件路徑等。**務必從對話歷史或工具回傳結果中取得確切路徑，不要自行猜測或拼湊**
- 對於短音訊（< 5 分鐘）建議使用 base 模型（速度快）；較長或需要高品質時建議 small 或 medium
- **嚴禁使用 sleep 等待轉錄完成**。轉錄可能需要數分鐘，啟動後只需查詢一次進度：
  - 若仍在轉錄中：直接回覆使用者「轉錄進行中，請稍後再詢問進度」，**結束本次回應**
  - 若已完成：讀取逐字稿並提供摘要
  - 不要在同一次回應中反覆 sleep + check，這會導致超時
