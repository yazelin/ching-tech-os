## Context

Line Bot 與 Telegram Bot 目前只處理文字和圖片訊息。語音訊息在 Line Bot 僅下載儲存、Telegram Bot 直接忽略。專案已具備 STT 能力（`faster-whisper` + `media-transcription` skill），但為非同步 job 模式，不適合即時聊天場景。

本功能以 `extends/voice/` 模組實作，遵循現有 extends 架構（如 `extends/his/`、`extends/erpnext/`）。核心系統僅做最小修改，透過 `voice_bridge.py` 條件載入。

相關現有程式碼：
- `api/linebot_router.py`：Line Bot webhook，已識別 `AudioMessageContent` 但不觸發 AI
- `services/bot_telegram/handler.py:343-352`：訊息類型判斷，缺少 voice 分支
- `services/bot_telegram/media.py`：只有 photo 和 document 下載
- `services/bot_line/messaging.py`：只有 TextMessage / ImageMessage 回覆
- `skills/media-transcription/`：非同步 fork 轉錄（long-running job）
- `main.py:94-166`：`_start_extends_modules()` 僅處理 lifespan，不處理 routers

## Goals / Non-Goals

**Goals:**
- 用戶在 Line / Telegram 發送語音訊息 → AI 理解並回覆（文字 + 語音）
- 短音訊（≤ 60 秒）同步轉錄，體驗等同發文字訊息
- 長音訊（> 60 秒）委派 media-transcription skill 非同步處理
- 功能為 extends 模組，不影響未安裝的部署

**Non-Goals:**
- 語音串流（real-time streaming STT）— 只處理完整的語音訊息
- 多語言 TTS 切換 — v1 固定 `zh-TW-HsiaoChenNeural`
- Telegram `message.audio`（音訊檔案附件）的 STT — 只處理 `message.voice`（語音錄音）
- 前端 Web UI 語音功能 — 僅限 Bot 平台

## Decisions

### D1：同步轉錄在 thread pool 中執行

**選擇**：`asyncio.to_thread()` 包裝 faster-whisper 推論

**替代方案**：
- (a) 直接在 async handler 中同步呼叫 — 阻塞 event loop，影響其他請求
- (b) 啟動子程序（fork）— 現有 media-transcription 的做法，但對短音訊 overhead 太大

**理由**：`to_thread()` 最輕量，短音訊用 `base` 模型 CPU 推論約 2-5 秒，不需要 fork 的複雜度。用 `asyncio.Semaphore(1)` 序列化並行請求，避免 CTranslate2 thread-safety 問題。

### D2：`_start_extends_modules(app)` 擴充 routers 支援

**選擇**：擴充現有函式，新增 `app` 參數，讀取 `contributes.yaml` 的 `routers` 欄位

**替代方案**：
- (a) startup callable 中 `from ching_tech_os.main import app` — circular import 風險
- (b) 新建獨立的 extends router 註冊函式 — 分散邏輯

**理由**：與現有 `_register_module_routers()` 一致，app 作為參數傳入避免循環依賴。extends 模組的 module_dir 已在 sys.path 中，`importlib.import_module()` 可直接載入 router。

### D3：TTS 音檔用 UUID4 命名，API 無認證

**選擇**：`GET /api/voice/tts/{uuid4}.mp3` 公開端點

**替代方案**：
- (a) 帶簽名 token 的 URL — 增加複雜度，Line 只需要簡單 HTTPS URL
- (b) 透過 nginx 靜態服務 — 需改 nginx 配置

**理由**：Line `AudioMessage` 要求 `original_content_url` 可公開存取。UUID4 不可列舉（128-bit random），24 小時自動清理限制暴露窗口。FastAPI router 由 extends 模組提供，核心不需修改。

### D4：voice_bridge.py 條件載入

**選擇**：`try: import voice_stt` / `except ImportError: return None`

**替代方案**：
- (a) 檢查 `sys.modules` — 語義相似但需要知道模組已被 import 過
- (b) 在 config 中設定 flag — 多一個設定項要管理

**理由**：最簡單的 Python 慣用法。extends 模組的 sys.path 在 `_start_extends_modules()` 中已注入，import 能直接找到。模組不存在時 ImportError 被捕獲，核心代碼零影響。

### D5：origin_type 傳遞機制

**選擇**：在各自的 handler（Line / Telegram）中處理語音來源判斷和 TTS 回覆

**替代方案**：
- (a) 修改 `call_claude()` / `linebot_ai` 加入 origin_type 參數 — 侵入核心 AI 流程
- (b) 用 contextvars — 隱式傳遞，難以追蹤

**理由**：STT 和 TTS 都在 handler 層完成。Line Bot 在 `linebot_router.py` 的音訊分支中先 STT → 呼叫 AI（同文字）→ 取得回覆文字 → TTS → 回覆。Telegram 在 `_handle_voice()` 中做同樣的事。不需要修改 AI 核心。

### D6：duration 判斷策略

**選擇**：平台提供 → ffprobe fallback → 檔案大小估算

**理由**：Line 提供 `duration`（毫秒），Telegram `voice.duration` 提供秒數，大多數情況直接可用。少數缺失時 `ffprobe` 讀 header 很快（< 100ms），不需完整解碼。最後 fallback 用檔案大小估算（M4A ~16KB/s、OGG ~2KB/s）。

## Risks / Trade-offs

**[Edge TTS 依賴外部服務]** → 失敗時靜默降級為純文字回覆，不影響 STT 和 AI 功能。記錄 warning log 供排查。

**[Reply token 過期]** → Line reply token 有效期約 30 秒，AI + TTS 可能超時。使用 `push_messages()` 主動推送作為 fallback（現有 AI 回覆已有此機制）。

**[Whisper 模型記憶體]** → `base` 模型約 150MB RAM。`warmup()` 在啟動時預載，避免首次請求延遲。若部署環境記憶體吃緊可不安裝 extends/voice。

**[並行語音請求]** → Semaphore(1) 序列化推論，第二個以後的請求會排隊。對聊天場景可接受（語音訊息不會像文字那麼密集）。

**[TTS 音檔暫存]** → 每個語音回覆產生一個 MP3（~50KB/30s 語音）。24 小時清理任務防止累積。以每日 100 則語音估算，日增 ~5MB，可忽略。
