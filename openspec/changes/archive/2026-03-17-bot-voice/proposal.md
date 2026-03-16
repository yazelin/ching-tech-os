## Why

Line Bot 與 Telegram Bot 目前無法處理語音訊息。Line Bot 收到音訊只會下載儲存但不觸發 AI；Telegram Bot 直接忽略 voice message。用戶希望透過語音與 AI 對話，並且 AI 能以語音回覆。功能以 `extends/voice/` 模組形式提供，不是所有部署都需要，因此不放在核心。

## What Changes

- 新增 `extends/voice/` 模組：STT（faster-whisper）+ TTS（Edge TTS）服務
- Line Bot / Telegram Bot 收到語音訊息後，自動轉錄為文字送入 AI 處理
- AI 回覆時同時生成語音回覆（用戶發語音 → AI 也回語音）
- 短音訊（≤ 60 秒）同步轉錄，長音訊（> 60 秒）走現有 media-transcription skill 非同步處理
- 新增 TTS 音檔 API 端點（供 Line 伺服器抓取音檔）
- 擴充 `_start_extends_modules()` 支援 `contributes.yaml` 的 `routers` 欄位
- `pyproject.toml` 新增 `edge-tts` optional dependency

## Capabilities

### New Capabilities
- `bot-voice`: Bot 語音訊息 STT 轉錄 + TTS 語音回覆（extends 模組）

### Modified Capabilities
- `media-transcription`: 長音訊（> 60 秒）委派給現有非同步轉錄 skill，需傳入 `caller_context` 以支援 proactive-push 回覆
- `feature-modules`: `_start_extends_modules()` 擴充支援 `routers` 欄位，extends 模組可宣告 FastAPI router

## Impact

- **後端核心**：`main.py`（router 註冊擴充）、`linebot_router.py`（音訊 → AI）、`telegram/handler.py` + `media.py` + `adapter.py`（voice 支援）、`bot_line/messaging.py`（AudioMessage 回覆）
- **新增模組**：`extends/voice/`（voice_stt.py、voice_tts.py、tts_router.py、voice_startup.py、SKILL.md）
- **新增橋接**：`services/bot/voice_bridge.py`（條件載入 voice 模組）
- **依賴**：新增 `edge-tts` optional dependency；`faster-whisper` 已安裝
- **NAS 儲存**：TTS 音檔暫存 `voice/tts/{date}/{uuid}.mp3`，24 小時後自動清理
