## Why

使用者透過 `media-downloader` skill 下載影片/音訊後，常需要將內容轉成逐字稿再進行後續處理（摘要整理、存入知識庫或歸檔至圖書館）。目前系統沒有任何語音轉文字功能，使用者必須手動處理，中斷了「下載 → 轉錄 → 整理 → 歸檔」的完整工作流。

## What Changes

- **新增 `media-transcription` skill**：提供影片/音訊轉逐字稿能力，作為 `media-downloader` 的下游 skill
- **新增 `transcribe` script**：接收 `ctos://` 路徑的音訊/影片檔，使用 `faster-whisper` 本地轉錄為逐字稿；因為大檔案轉錄耗時，採非同步模式（fork 背景程序，立即回傳 job_id，與 media-downloader 相同模式）
- **新增 `check-transcription` script**：查詢轉錄任務進度與結果（讀取 status.json）
- **轉錄結果暫存**：逐字稿以 Markdown 格式暫存於 CTOS zone，產生 `ctos://` 路徑，使用者可透過既有的 `add_note`（知識庫）或 `archive_to_library`（圖書館）進行後續處理
- **新增 Python 依賴**：`faster-whisper`、`opencc-python-reimplemented`（簡轉繁）

### 技術選型（參考 `asr-ime-fcitx` 專案）

| 項目 | 選擇 | 說明 |
|------|------|------|
| 語音辨識引擎 | `faster-whisper` | CTranslate2 優化版 Whisper，免費本地執行 |
| 模型 | 預設 `small`，可設定 | CPU 用 `int8`，有 GPU 自動用 `float16` |
| 裝置偵測 | 自動 | 有 `nvidia-smi` 用 CUDA，否則 CPU |
| 簡轉繁 | `opencc`（s2twp） | Whisper 輸出常為簡體，轉繁體含台灣用語 |
| 音軌提取 | `ffmpeg` | 從影片中提取音訊給 Whisper 處理 |
| 非同步模式 | fork 背景程序 + status.json | 與 media-downloader 相同模式 |

## Capabilities

### New Capabilities
- `media-transcription`：影片/音訊逐字稿轉錄 skill，包含非同步轉錄、進度查詢、結果暫存

### Modified Capabilities

（無修改既有 spec）

## Impact

- **後端 skills 目錄**：新增 `skills/media-transcription/` 目錄（SKILL.md + scripts）
- **Python 依賴**：新增 `faster-whisper`、`opencc-python-reimplemented`
- **系統依賴**：需要 `ffmpeg`（從影片提取音軌，系統通常已安裝）
- **儲存空間**：
  - 轉錄暫存檔存於 `ctos://linebot/transcriptions/{date}/{uuid}/`
  - 首次執行時 Whisper 模型自動下載至快取（`small` 約 500MB）
- **API 金鑰**：無需任何 API 金鑰，完全本地執行
- **使用者權限**：沿用 `requires_app: file-manager`，與 media-downloader 相同權限門檻
- **AI Prompt**：Agent prompt 需更新以引導「下載 → 轉錄 → 整理 → 歸檔」工作流
- **預期使用情境**：
  1. 使用者下載影片（media-downloader）
  2. 使用者要求 AI 轉錄逐字稿（media-transcription `transcribe`）
  3. AI 查詢轉錄進度（`check-transcription`）
  4. 使用者要求 AI 整理摘要/總結（AI 直接處理文字）
  5. AI 將結果存入知識庫（`add_note`）或歸檔至圖書館（`archive_to_library`）
