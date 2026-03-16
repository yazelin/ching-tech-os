## ADDED Requirements

### Requirement: 語音訊息 STT 轉錄
系統 SHALL 在收到 Bot 語音訊息時，透過 `extends/voice` 模組將語音轉錄為文字，並送入 AI 處理流程。

#### Scenario: 短音訊同步轉錄（≤ 60 秒）
- **WHEN** Bot 收到語音訊息且 duration ≤ 60 秒
- **THEN** 系統 SHALL 使用 faster-whisper `base` 模型在 thread pool 中同步轉錄
- **AND** 轉錄文字 SHALL 加上 `[語音訊息] ` 前綴
- **AND** 轉錄文字 SHALL 送入 AI 處理流程（與文字訊息相同路徑）

#### Scenario: 長音訊非同步轉錄（> 60 秒）
- **WHEN** Bot 收到語音訊息且 duration > 60 秒
- **THEN** 系統 SHALL 委派給 `media-transcription` skill 非同步處理
- **AND** 系統 SHALL 立即回覆用戶「語音訊息較長，轉錄中，完成後通知你」
- **AND** 轉錄完成後 SHALL 透過 proactive-push 通知用戶逐字稿

#### Scenario: duration 資訊缺失
- **WHEN** 平台未提供 duration 資訊
- **THEN** 系統 SHALL 優先使用 `ffprobe` 讀取檔案 header 取得 duration
- **AND** 若 `ffprobe` 失敗，SHALL 依檔案大小估算（Line M4A: 16KB/s、Telegram OGG: 2KB/s）

#### Scenario: 轉錄失敗
- **WHEN** faster-whisper 轉錄過程發生錯誤
- **THEN** 系統 SHALL 回覆用戶「語音辨識失敗，請重新發送或改用文字」
- **AND** SHALL 記錄錯誤到 logger

#### Scenario: 並行請求序列化
- **WHEN** 多個語音訊息同時到達
- **THEN** 系統 SHALL 使用 `asyncio.Semaphore(1)` 序列化 faster-whisper 推論
- **AND** 排隊中的請求 SHALL 等待前一個完成後再執行

---

### Requirement: Line Bot 語音訊息處理
系統 SHALL 在 Line Bot 收到 `AudioMessageContent` 時，下載音訊並觸發 STT 轉錄。

#### Scenario: Line Bot 收到音訊訊息
- **WHEN** `linebot_router.py` 收到 `AudioMessageContent`
- **AND** voice 模組已載入（`voice_bridge.get_voice_stt()` 不為 None）
- **THEN** 系統 SHALL 照現行流程下載音訊到 NAS
- **AND** SHALL 呼叫 `voice_stt.transcribe_for_bot()` 進行轉錄
- **AND** 轉錄文字 SHALL 進入 AI 處理流程

#### Scenario: voice 模組未安裝
- **WHEN** `linebot_router.py` 收到 `AudioMessageContent`
- **AND** voice 模組未載入（`voice_bridge.get_voice_stt()` 為 None）
- **THEN** 行為 SHALL 與現行相同（下載儲存但不觸發 AI）

---

### Requirement: Telegram Bot 語音訊息處理
系統 SHALL 在 Telegram Bot 收到 `message.voice` 時，下載音訊並觸發 STT 轉錄。

#### Scenario: Telegram 訊息類型識別
- **WHEN** `handler.py` 收到含 `message.voice` 的訊息
- **THEN** 系統 SHALL 將 `msg_type` 設為 `"audio"`

#### Scenario: Telegram audio 檔案不觸發 STT
- **WHEN** `handler.py` 收到含 `message.audio`（音訊檔案附件，如 MP3）的訊息
- **THEN** 系統 SHALL 視為一般檔案處理，不觸發 STT

#### Scenario: Telegram 語音下載
- **WHEN** 收到 Telegram voice message
- **THEN** 系統 SHALL 呼叫 `download_telegram_voice()` 下載 OGG 音訊到 NAS
- **AND** SHALL 記錄 `duration` 到 `bot_files`

#### Scenario: Telegram 語音送入 AI
- **WHEN** 語音下載並轉錄完成
- **THEN** 轉錄文字 SHALL 加上用戶名稱前綴
- **AND** SHALL 呼叫 `_handle_text_with_ai()` 走既有 AI 處理流程

---

### Requirement: TTS 語音回覆
系統 SHALL 在用戶發送語音訊息且 AI 回覆文字後，使用 Edge TTS 生成語音並同時回覆文字與語音。

#### Scenario: Edge TTS 生成語音
- **WHEN** 需要生成語音回覆
- **THEN** 系統 SHALL 使用 `edge-tts` 套件生成 MP3 音檔
- **AND** 預設語音角色 SHALL 為 `zh-TW-HsiaoChenNeural`
- **AND** 音檔 SHALL 儲存到 NAS `voice/tts/{date}/{uuid4}.mp3`

#### Scenario: 文字前處理
- **WHEN** AI 回覆文字包含 Markdown 格式
- **THEN** 系統 SHALL 先清除 Markdown 標記再送入 TTS
- **AND** 若文字超過 500 字 SHALL 截斷，末尾加上「...後續請參考文字訊息」

#### Scenario: TTS 失敗降級
- **WHEN** Edge TTS 生成失敗
- **THEN** 系統 SHALL 僅回覆文字訊息
- **AND** SHALL 記錄 warning 到 logger

#### Scenario: 長音訊不觸發 TTS
- **WHEN** 原始語音訊息 > 60 秒（走非同步轉錄）
- **THEN** 系統 SHALL 不生成 TTS 回覆，僅推送逐字稿文字

---

### Requirement: Line Bot TTS 回覆
系統 SHALL 在 Line Bot 語音回覆時，使用 `AudioMessage` 回覆。

#### Scenario: Line Bot 語音 + 文字回覆
- **WHEN** AI 回覆文字已生成且 TTS 音檔已產生
- **THEN** 系統 SHALL 同時回覆 `TextMessage` + `AudioMessage`
- **AND** `AudioMessage.original_content_url` SHALL 指向 TTS API 端點

#### Scenario: reply_token 過期
- **WHEN** reply_token 不可用（AI + TTS 處理耗時超過 30 秒）
- **THEN** 系統 SHALL 使用 `push_messages()` 主動推送

---

### Requirement: Telegram Bot TTS 回覆
系統 SHALL 在 Telegram Bot 語音回覆時，直接上傳音檔。

#### Scenario: Telegram 語音 + 文字回覆
- **WHEN** AI 回覆文字已生成且 TTS 音檔已產生
- **THEN** 系統 SHALL 同時發送文字訊息和語音訊息
- **AND** 語音 SHALL 使用 `bot.send_voice()` 直接上傳（不需公開 URL）

#### Scenario: Telegram adapter send_voice
- **WHEN** 呼叫 `TelegramBotAdapter.send_voice(target, audio_bytes, duration, reply_to)`
- **THEN** SHALL 使用 `bot.send_voice()` 上傳音檔到指定 chat

---

### Requirement: TTS 音檔 API
系統 SHALL 提供 TTS 音檔下載端點供 Line 伺服器抓取。

#### Scenario: 正常下載
- **WHEN** 請求 `GET /api/voice/tts/{file_id}.mp3`
- **AND** file_id 為有效的 UUID4 格式
- **THEN** 系統 SHALL 回傳對應的 MP3 檔案
- **AND** Content-Type SHALL 為 `audio/mpeg`
- **AND** Cache-Control SHALL 為 `public, max-age=86400`

#### Scenario: file_id 格式驗證
- **WHEN** 請求的 file_id 不符合 UUID4 格式
- **THEN** 系統 SHALL 回傳 400

#### Scenario: 檔案不存在
- **WHEN** 請求的 file_id 對應的檔案不存在
- **THEN** 系統 SHALL 回傳 404

#### Scenario: 音檔自動清理
- **WHEN** TTS 音檔存放超過 24 小時
- **THEN** 排程任務 SHALL 刪除過期音檔
- **AND** 清理任務 SHALL 透過 `contributes.yaml` 的 `scheduler` 欄位註冊

---

### Requirement: voice_bridge 條件載入
系統 SHALL 提供 `voice_bridge.py` 供核心程式碼條件載入 voice 模組。

#### Scenario: 模組已安裝
- **WHEN** extends/voice 模組已載入（sys.path 已包含 voice 模組路徑）
- **THEN** `get_voice_stt()` SHALL 回傳 `voice_stt` 模組
- **AND** `get_voice_tts()` SHALL 回傳 `voice_tts` 模組

#### Scenario: 模組未安裝
- **WHEN** extends/voice 模組未安裝
- **THEN** `get_voice_stt()` SHALL 回傳 `None`
- **AND** `get_voice_tts()` SHALL 回傳 `None`

---

### Requirement: extends/voice 模組生命週期
系統 SHALL 透過 `contributes.yaml` 管理 voice 模組的啟動和關閉。

#### Scenario: 模組啟動
- **WHEN** 應用程式啟動且 `extends/voice/contributes.yaml` 存在
- **THEN** 系統 SHALL 執行 `voice_startup.startup()`
- **AND** startup SHALL 預載 whisper `base` 模型（透過 `asyncio.to_thread` 避免阻塞）

#### Scenario: 模組關閉
- **WHEN** 應用程式關閉
- **THEN** 系統 SHALL 執行 `voice_startup.shutdown()`
- **AND** shutdown SHALL 釋放 whisper 模型資源

#### Scenario: TTS router 動態註冊
- **WHEN** 模組啟動
- **THEN** 系統 SHALL 透過 `contributes.yaml` 的 `routers` 欄位動態註冊 TTS API router
