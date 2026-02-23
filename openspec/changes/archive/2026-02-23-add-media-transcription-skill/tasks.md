## 1. 環境準備

- [x] 1.1 在 `backend/pyproject.toml` 新增依賴：`faster-whisper`、`opencc-python-reimplemented`
- [x] 1.2 執行 `uv sync` 安裝依賴，確認 `faster-whisper` 和 `opencc` 可正常 import
- [x] 1.3 確認系統 `ffmpeg` 已安裝且可執行

## 2. Skill 目錄與定義

- [x] 2.1 建立 `backend/src/ching_tech_os/skills/media-transcription/` 目錄
- [x] 2.2 建立 `SKILL.md`：frontmatter 設定 name、description、allowed-tools、requires_app、mcp_servers；正文撰寫使用說明（scripts 介紹與用法）
- [x] 2.3 建立 `scripts/` 目錄

## 3. transcribe script

- [x] 3.1 建立 `scripts/transcribe.py`：stdin 讀取 JSON input（`source_path`、可選 `model`）
- [x] 3.2 實作 `ctos://` 路徑解析為實際檔案路徑，驗證檔案存在與格式支援
- [x] 3.3 實作 fork 非同步模式：父程序立即回傳 `{job_id, status: "started"}`，子程序背景執行
- [x] 3.4 實作暫存目錄建立：`ctos://linebot/transcriptions/{YYYY-MM-DD}/{uuid8}/`，寫入初始 status.json
- [x] 3.5 實作音軌提取：影片檔以 `ffmpeg -i input -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav` 提取；純音訊檔跳過此步
- [x] 3.6 實作 faster-whisper 轉錄：自動偵測 CPU/GPU、載入模型、執行轉錄取得 segments
- [x] 3.7 實作 opencc s2twp 簡轉繁：對每個 segment text 進行轉換
- [x] 3.8 實作 transcript.md 輸出：包含標題、metadata（來源、時間、模型、時長）、時間戳分段正文
- [x] 3.9 實作完成清理：刪除暫存 WAV、更新 status.json 為 completed（含 ctos_path、duration、transcript_preview）
- [x] 3.10 實作錯誤處理：各階段失敗時更新 status.json 為 failed 並記錄 error

## 4. check-transcription script

- [x] 4.1 建立 `scripts/check-transcription.py`：stdin 讀取 `{job_id}`
- [x] 4.2 實作搜尋 status.json：掃描最近 7 天的日期目錄（參考 media-downloader 的 check-download.py）
- [x] 4.3 實作狀態回傳：依 status 值回傳對應資訊（進行中顯示階段、完成顯示 ctos_path + preview、失敗顯示 error）
- [x] 4.4 實作逾時判定：status.json 超過 30 分鐘未更新且仍為 transcribing 時回傳 failed

## 5. 測試驗證

- [x] 5.1 手動測試：用 media-downloader 下載一段短影片，再用 transcribe 轉錄，確認完整流程
- [x] 5.2 測試純音訊檔（.mp3）轉錄
- [x] 5.3 測試 check-transcription 各狀態回傳（進行中、完成、不存在）
- [x] 5.4 測試錯誤情境：不存在的檔案、不支援的格式
- [x] 5.5 確認逐字稿為繁體中文（opencc 轉換正確）

## 6. AI Prompt 整合

- [x] 6.1 更新 Agent prompt：加入 media-transcription skill 的使用說明，引導「下載 → 轉錄 → 整理 → 歸檔」工作流
