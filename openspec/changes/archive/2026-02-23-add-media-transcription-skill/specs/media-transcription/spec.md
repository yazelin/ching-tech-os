## ADDED Requirements

### Requirement: 非同步轉錄音訊/影片
Skill SHALL 提供 `transcribe` script，以非同步方式將音訊或影片檔轉錄為繁體中文逐字稿。

#### Scenario: 啟動轉錄（立即回傳 job ID）
- **WHEN** AI 呼叫 `run_skill_script(skill="media-transcription", script="transcribe", input='{"source_path":"ctos://linebot/videos/2026-02-23/a1b2c3d4/video.mp4"}')`
- **THEN** Script 在 3 秒內回傳 `{"success": true, "job_id": "<uuid8>", "status": "started"}`
- **AND** 轉錄在背景程序中繼續執行

#### Scenario: 轉錄影片檔（含音軌提取）
- **WHEN** source_path 指向影片檔（.mp4、.mkv、.webm）
- **THEN** 系統先以 ffmpeg 提取音軌為 16kHz mono WAV
- **AND** 再以 faster-whisper 進行語音辨識

#### Scenario: 轉錄純音訊檔
- **WHEN** source_path 指向音訊檔（.mp3、.m4a、.wav、.ogg、.flac）
- **THEN** 系統直接以 faster-whisper 進行語音辨識，不需額外提取音軌

#### Scenario: 指定模型大小
- **WHEN** input 包含 `"model": "base"` 或 `"medium"` 或 `"large-v3"`
- **THEN** 系統使用指定的 Whisper 模型進行轉錄

#### Scenario: 預設模型
- **WHEN** input 未指定 model
- **THEN** 系統使用 `small` 模型

#### Scenario: 裝置自動偵測
- **WHEN** 系統有 NVIDIA GPU（`nvidia-smi` 可用）
- **THEN** 使用 CUDA + float16 推論
- **WHEN** 系統無 GPU
- **THEN** 使用 CPU + int8 推論

#### Scenario: 來源檔案不存在
- **WHEN** source_path 對應的實際檔案不存在
- **THEN** 系統回傳 `{"success": false, "error": "來源檔案不存在：<path>"}`

#### Scenario: 不支援的檔案格式
- **WHEN** source_path 的副檔名不在支援清單中
- **THEN** 系統回傳 `{"success": false, "error": "不支援的檔案格式：<ext>"}`

---

### Requirement: 簡體轉繁體輸出
Skill SHALL 將 Whisper 輸出的簡體中文自動轉換為繁體中文（台灣用語）。

#### Scenario: 簡體轉繁體
- **WHEN** Whisper 辨識結果包含簡體中文
- **THEN** 系統以 opencc `s2twp` 轉換為繁體台灣用語
- **AND** 最終逐字稿為繁體中文

#### Scenario: 非中文內容
- **WHEN** 辨識結果為英文或其他語言
- **THEN** 系統不進行簡繁轉換，原樣保留

---

### Requirement: 查詢轉錄狀態
Skill SHALL 提供 `check-transcription` script，查詢背景轉錄的進度與結果。

#### Scenario: 查詢進行中的轉錄
- **WHEN** AI 呼叫 `run_skill_script(skill="media-transcription", script="check-transcription", input='{"job_id":"a1b2c3d4"}')`
- **AND** 轉錄正在進行中
- **THEN** 系統回傳 `{"success": true, "status": "transcribing", "progress": "<階段描述>"}`

#### Scenario: 查詢已完成的轉錄
- **WHEN** 轉錄已完成
- **THEN** 系統回傳包含 `status: "completed"`、`ctos_path`（逐字稿 .md 檔路徑）、`duration`（音訊時長）、`transcript_preview`（前 500 字預覽）

#### Scenario: 查詢不存在的 job
- **WHEN** job_id 不存在或狀態檔遺失
- **THEN** 系統回傳 `{"success": false, "error": "找不到轉錄任務"}`

#### Scenario: 轉錄失敗
- **WHEN** 轉錄過程中發生錯誤（ffmpeg 失敗、模型載入失敗等）
- **THEN** 狀態更新為 `{"status": "failed", "error": "<錯誤訊息>"}`

#### Scenario: 轉錄逾時判定
- **WHEN** 狀態檔的 `updated_at` 超過 30 分鐘未更新
- **AND** status 仍為 `transcribing`
- **THEN** 系統回傳 `{"status": "failed", "error": "轉錄逾時（超過 30 分鐘無進度）"}`

---

### Requirement: 逐字稿暫存格式
轉錄完成的逐字稿 SHALL 以 Markdown 格式暫存，並包含來源資訊與時間戳分段。

#### Scenario: 逐字稿 Markdown 結構
- **WHEN** 轉錄完成
- **THEN** 產生 `transcript.md` 檔案
- **AND** 包含標題（原始檔名）、來源路徑、轉錄時間、模型名稱、音訊時長等 metadata
- **AND** 正文依時間戳分段，每段標示起始時間（如 `[00:30]`）

#### Scenario: 暫存路徑格式
- **WHEN** 啟動一個新的轉錄任務
- **THEN** 建立目錄 `ctos://linebot/transcriptions/{YYYY-MM-DD}/{uuid8}/`
- **AND** 逐字稿存於該目錄下的 `transcript.md`

#### Scenario: 暫存清理
- **WHEN** 轉錄完成
- **THEN** 刪除提取的暫存音軌檔案（.wav）以節省空間
- **AND** 保留 `transcript.md` 和 `status.json`

---

### Requirement: Skill 定義與權限
Skill SHALL 以 `SKILL.md` 定義 metadata，遵循 Agent Skills 標準。

#### Scenario: Skill 載入
- **WHEN** 系統啟動或 reload skills
- **THEN** `media-transcription` Skill 被載入
- **AND** 包含 2 個 scripts：`transcribe`、`check-transcription`

#### Scenario: 權限控管
- **WHEN** 使用者不具備 `file-manager` app 權限
- **THEN** 系統拒絕執行任何 media-transcription script

#### Scenario: SKILL.md 結構
- **WHEN** 讀取 SKILL.md
- **THEN** frontmatter 包含 `name: media-transcription`、`requires_app: file-manager`、`mcp_servers: ching-tech-os`

---

### Requirement: 狀態追蹤
轉錄任務 SHALL 以 status.json 追蹤進度，與 media-downloader 格式一致。

#### Scenario: 狀態檔欄位
- **WHEN** 轉錄任務建立
- **THEN** 在任務目錄建立 `status.json`
- **AND** 包含 `job_id`、`status`、`progress`、`source_path`、`ctos_path`、`duration`、`model`、`error`、`created_at`、`updated_at` 欄位

#### Scenario: 狀態轉換流程
- **WHEN** 任務執行
- **THEN** 狀態依序為：`started` → `extracting_audio`（影片才有）→ `transcribing` → `completed`
- **AND** 失敗時為 `failed`
