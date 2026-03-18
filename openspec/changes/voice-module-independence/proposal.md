## Why

目前語音模組的 STT/TTS 是硬接線在 Bot 層的自動流程中，AI 無法自行決定是否使用語音回覆。這導致兩個問題：（1）使用者用語音要求 AI 執行工具操作（如畫圖）時，自動 TTS 流程會攔截正常的回覆路徑，造成工具結果遺失；（2）AI 無法在使用者用文字發問時選擇語音回覆，也無法控制語音回覆的內容。此外，TTS 引擎目前綁定 Edge TTS，未來需要能切換至 Google Cloud TTS 或 Gemini Native Audio。語音模組的前端 App UI 目前僅顯示「開發中」，需要建置語音設定介面供使用者選擇語音角色與試聽。

## What Changes

- **BREAKING**：移除 Bot 層（Line/Telegram）語音訊息的自動 TTS 回覆邏輯，改由 AI 透過 MCP 工具主動呼叫
- 新增 `text_to_speech` MCP 工具，AI 可自行決定何時、對什麼內容生成語音回覆
- Bot 回覆組裝層新增 TTS 結果偵測邏輯，自動將語音檔組裝為平台音訊訊息
- TTS 引擎抽象化：新增 `TTSEngine` 介面，支援透過 `TTS_ENGINE` 環境變數切換引擎（edge / google_cloud / gemini）
- Agent prompt 新增語音工具使用指引，引導 AI 在使用者發送語音訊息時優先語音回覆
- 前端語音 App UI：語音角色選擇、試聽功能、個人語音偏好設定

## Capabilities

### New Capabilities
- `tts-mcp-tool`：AI 可呼叫的 text_to_speech MCP 工具，生成語音檔並回傳結構化結果供 Bot 層組裝
- `tts-engine-abstraction`：TTS 引擎抽象層，支援多引擎切換（Edge TTS / Google Cloud TTS / Gemini Native Audio）
- `voice-settings-ui`：前端語音設定 App，包含語音角色選擇、試聽、個人偏好儲存

### Modified Capabilities
- `bot-voice`：移除自動 TTS 硬接線邏輯，語音訊息改走正常 AI 流程；Bot 回覆層新增 TTS 工具結果偵測與語音訊息組裝
- `mcp-tools`：註冊 text_to_speech 工具

## Impact

- **後端**：
  - `extends/voice/voice_tts.py`：重構為引擎抽象層
  - `services/mcp/`：新增 TTS 工具註冊
  - `api/linebot_router.py`：移除語音自動 TTS 和 skip_send 邏輯
  - `services/bot_telegram/handler.py`：移除自動 TTS 邏輯
  - `services/linebot_ai.py`：新增 TTS 結果偵測 + 語音訊息組裝
  - `services/linebot_agents.py` + `bot/agents.py`：prompt 新增語音工具說明
  - 新增 Alembic migration：更新資料庫 prompt + 語音設定表
- **前端**：
  - 語音 App UI（語音選擇、試聽、設定儲存）
  - 新增 API 端點支援語音設定 CRUD
- **不動的部分**：
  - STT 自動轉錄流程維持不變
  - `[語音訊息]` 前綴維持不變
  - `tts_router.py` 音檔下載 API 維持不變
  - `voice_bridge.py` 條件載入維持不變
