## MODIFIED Requirements

### Requirement: 非同步轉錄音訊/影片
Skill SHALL 提供 `transcribe` script，以非同步方式將音訊或影片檔轉錄為繁體中文逐字稿。start script SHALL 接受並持久化 `caller_context`，供主動推送使用。

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

#### Scenario: transcribe 接受 caller_context
- **WHEN** AI 呼叫 `transcribe` 時 input 包含 `caller_context` 欄位
- **THEN** script SHALL 將 `caller_context` 原樣寫入 `status.json`
- **AND** 轉錄完成後，背景程序 SHALL 呼叫 `/api/internal/proactive-push` 觸發通知

#### Scenario: 轉錄完成後觸發推送通知
- **WHEN** 背景轉錄程序寫入 `status: "completed"`
- **THEN** 程序 SHALL POST 至 `/api/internal/proactive-push`，帶入 `job_id` 與 `skill="media-transcription"`
- **AND** 推送訊息包含逐字稿前 300 字與完整逐字稿的 ctos_path
