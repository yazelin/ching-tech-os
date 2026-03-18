## MODIFIED Requirements

### Requirement: TTS 語音回覆
系統 SHALL 透過 AI 主動呼叫 `text_to_speech` MCP 工具生成語音，取代 Bot 層自動 TTS。

#### Scenario: 語音訊息走正常 AI 流程
- **WHEN** Bot 收到語音訊息且 STT 轉錄成功
- **THEN** 轉錄文字 SHALL 直接進入正常 AI 處理流程（與文字訊息相同路徑）
- **AND** 系統 SHALL 不再使用 `skip_send=True` 攔截 AI 回覆
- **AND** AI 的所有工具呼叫（畫圖、查資料等）SHALL 正常執行

#### Scenario: AI 決定是否語音回覆
- **WHEN** AI 處理完使用者訊息後
- **THEN** AI SHALL 根據 prompt 引導和情境自行決定是否呼叫 `text_to_speech`
- **AND** 語音回覆 SHALL 透過 `[VOICE_MESSAGE:{...}]` 標記由 Bot 層組裝發送

#### Scenario: TTS 生成失敗時的降級
- **WHEN** AI 呼叫 `text_to_speech` 但 TTS 引擎生成失敗
- **THEN** 系統 SHALL 僅回覆文字訊息（AI 收到錯誤後自行決定如何回覆）

#### Scenario: 長音訊不影響 TTS
- **WHEN** 原始語音訊息 > 60 秒（走非同步轉錄）
- **THEN** 系統 SHALL 不觸發 AI 流程（行為不變，僅推送逐字稿）

---

### Requirement: Line Bot TTS 回覆
系統 SHALL 在偵測到 AI 回覆中的語音標記時，組裝 Line `AudioMessage` 發送。

#### Scenario: Line Bot 語音 + 文字回覆
- **WHEN** `parse_ai_response()` 解析到 `[VOICE_MESSAGE:{...}]` 標記
- **AND** 平台為 Line
- **THEN** 系統 SHALL 建立 `AudioMessage(original_content_url, duration)` 加入回覆訊息列表
- **AND** SHALL 與文字訊息、圖片訊息一起透過 `reply_messages()` 發送

#### Scenario: reply_token 過期
- **WHEN** reply_token 不可用（AI + TTS 處理耗時超過 30 秒）
- **THEN** 系統 SHALL 使用 `push_messages()` 主動推送

---

### Requirement: Telegram Bot TTS 回覆
系統 SHALL 在偵測到 AI 回覆中的語音標記時，上傳語音訊息到 Telegram。

#### Scenario: Telegram 語音 + 文字回覆
- **WHEN** `parse_ai_response()` 解析到 `[VOICE_MESSAGE:{...}]` 標記
- **AND** 平台為 Telegram
- **THEN** 系統 SHALL 讀取 NAS 上的音檔 bytes
- **AND** SHALL 使用 `adapter.send_voice()` 上傳音檔

## REMOVED Requirements

### Requirement: Bot 層自動 TTS
**Reason**: 自動 TTS 會攔截 AI 正常回覆流程，導致工具呼叫結果遺失。改由 AI 透過 MCP 工具主動呼叫。
**Migration**: AI 透過 `text_to_speech` MCP 工具自行決定何時生成語音。Prompt 引導確保語音訊息仍優先收到語音回覆。
