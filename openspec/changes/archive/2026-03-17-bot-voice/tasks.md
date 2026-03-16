## 1. 核心基礎建設

- [x] 1.1 擴充 `main.py` 的 `_start_extends_modules(app)` 支援 `contributes.yaml` 的 `routers` 欄位（傳入 app 參數，動態 include_router）
- [x] 1.2 新增 `services/bot/voice_bridge.py`：`get_voice_stt()` 和 `get_voice_tts()` 條件載入函式
- [x] 1.3 `pyproject.toml` 新增 `edge-tts` 到 optional dependencies（`[project.optional-dependencies] voice = ["edge-tts>=6.1.0"]`）
- [x] 1.4 安裝 edge-tts 到後端環境（`uv sync --extra voice` 或 `uv pip install edge-tts`）

## 2. extends/voice 模組骨架

- [x] 2.1 建立 `extends/voice/` 目錄結構（contributes.yaml、voice_stt.py、voice_tts.py、voice_startup.py、tts_router.py、skills/voice/SKILL.md、README.md）
- [x] 2.2 撰寫 `contributes.yaml`（lifespan startup/shutdown、routers、scheduler）
- [x] 2.3 撰寫 `skills/voice/SKILL.md`（app: voice、permissions、icon）

## 3. STT 服務（voice_stt.py）

- [x] 3.1 實作 `TranscribeResult` dataclass 和 `transcribe_for_bot()` 主函式（duration 判斷 → 同步/非同步分流）
- [x] 3.2 實作同步轉錄邏輯：`asyncio.to_thread()` + faster-whisper `base` 模型 + `Semaphore(1)` 序列化
- [x] 3.3 實作 duration 取得策略：平台提供 → ffprobe fallback → 檔案大小估算（M4A 16KB/s、OGG 2KB/s）
- [x] 3.4 實作長音訊非同步委派：呼叫 media-transcription skill 的 `transcribe` script，傳入 `caller_context`
- [x] 3.5 實作 `warmup()`（async，to_thread 預載 base 模型）和 `cleanup()`（釋放模型）

## 4. TTS 服務（voice_tts.py）

- [x] 4.1 實作 `TTSResult` dataclass 和 `synthesize()` 主函式
- [x] 4.2 實作文字前處理：清除 Markdown 標記、截斷至 500 字
- [x] 4.3 實作 Edge TTS 生成 MP3：呼叫 edge-tts、UUID4 命名、儲存到 NAS `voice/tts/{date}/{uuid}.mp3`
- [x] 4.4 實作 `cleanup_old_files()`：掃描 NAS 刪除超過 24 小時的 TTS 音檔

## 5. TTS API 端點（tts_router.py）

- [x] 5.1 實作 `GET /api/voice/tts/{file_id}.mp3`：UUID4 格式驗證、NAS 讀取、回傳 audio/mpeg
- [x] 5.2 路徑穿越防護（file_id 必須符合 UUID4）、404 處理、Cache-Control header

## 6. 模組啟動（voice_startup.py）

- [x] 6.1 實作 `startup()`：呼叫 `voice_stt.warmup()`
- [x] 6.2 實作 `shutdown()`：呼叫 `voice_stt.cleanup()`

## 7. Line Bot 整合

- [x] 7.1 修改 `linebot_router.py`：`message_type == "audio"` 分支新增 voice_bridge 檢查 → STT → AI 處理
- [x] 7.2 修改 `linebot_router.py`：AI 回覆後呼叫 voice_tts.synthesize() → 組裝 TextMessage + AudioMessage 回覆
- [x] 7.3 修改 `bot_line/messaging.py`：import `AudioMessage`、更新 type hints、新增 `push_audio()` 函式

## 8. Telegram Bot 整合

- [x] 8.1 修改 `handler.py`：訊息類型判斷新增 `message.voice` → `msg_type = "audio"`
- [x] 8.2 新增 `media.py` 的 `download_telegram_voice()`：下載 OGG 到 NAS、記錄 duration
- [x] 8.3 新增 `handler.py` 的 `_handle_voice()`：下載 → STT → AI → TTS → 回覆
- [x] 8.4 新增 `adapter.py` 的 `send_voice(target, audio_bytes, duration, reply_to)`

## 9. 測試與驗證

- [ ] 9.1 重啟服務，確認 extends/voice 模組正常載入（檢查 startup log）
- [ ] 9.2 測試 Line Bot：發送短語音訊息（< 60 秒），確認 STT → AI → TTS 回覆完整流程
- [ ] 9.3 測試 Telegram Bot：發送 voice message，確認 STT → AI → TTS 回覆完整流程
- [ ] 9.4 測試長音訊（> 60 秒）：確認走非同步轉錄 + proactive-push 通知
- [ ] 9.5 測試 TTS 失敗降級：斷網情況下確認僅回覆文字
- [ ] 9.6 測試 voice 模組未安裝：移除 extends/voice，確認核心功能不受影響
