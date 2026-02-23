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
   - source_path：要轉錄的音訊/影片檔的 ctos:// 路徑
   - 可選參數 model：whisper 模型大小（base/small/medium/large-v3，預設 small）
   - 支援格式：影片（.mp4、.mkv、.webm）、音訊（.mp3、.m4a、.wav、.ogg、.flac）
   - 立即回傳 job_id，轉錄在背景執行

2. **check-transcription** — 查詢轉錄進度（同步）
   - `run_skill_script(skill="media-transcription", script="check-transcription", input='{"job_id":"之前取得的job_id"}')`
   - 回傳轉錄狀態（extracting_audio/transcribing/completed/failed）
   - 完成時回傳 ctos_path（逐字稿 .md 檔）和 transcript_preview（前 500 字預覽）

**典型使用流程：**
1. 使用者透過 media-downloader 下載影片，取得 ctos_path
2. 呼叫 transcribe 啟動轉錄，取得 job_id
3. 呼叫 check-transcription 查詢進度，完成後取得逐字稿 ctos_path
4. 用 read_knowledge_attachment 或 read_document 讀取逐字稿內容
5. 依使用者要求整理摘要/總結/重點筆記
6. 使用 add_note 存入知識庫，或 archive_to_library 歸檔到圖書館

**AI 行為指引：**
- 當使用者下載了影片/音訊後問「幫我整理內容」、「這在講什麼」等，主動建議先轉錄
- 轉錄啟動後，等待約 30 秒再查詢進度；若仍在轉錄中，告知使用者需等待並稍後再查
- 轉錄完成後，主動讀取逐字稿並提供摘要，詢問使用者是否要進一步整理或存檔
- 對於短音訊（< 5 分鐘）建議使用 base 模型（速度快）；較長或需要高品質時建議 small 或 medium
