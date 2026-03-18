## ADDED Requirements

### Requirement: text_to_speech MCP 工具
系統 SHALL 提供 `text_to_speech` MCP 工具，讓 AI 可主動將指定文字轉換為語音檔案。

#### Scenario: 基本語音生成
- **WHEN** AI 呼叫 `text_to_speech` 工具並傳入 `text` 參數
- **THEN** 系統 SHALL 呼叫 TTS 引擎生成 MP3 音檔
- **AND** 音檔 SHALL 儲存到 NAS `voice/tts/{date}/{uuid4}.mp3`
- **AND** 工具 SHALL 回傳包含 `[VOICE_MESSAGE:{"file_id":"<uuid>","duration_ms":<ms>}]` 標記的成功訊息

#### Scenario: 階層式語音設定解析
- **WHEN** AI 呼叫 `text_to_speech` 工具
- **THEN** 系統 SHALL 依階層優先級解析語音設定：
  - 私訊：使用者設定 > Agent 設定 > 系統預設
  - 群組：群組設定 > Agent 設定 > 系統預設
- **AND** SHALL 使用解析後的引擎和參數包生成音檔

#### Scenario: context 參數自動注入
- **WHEN** AI 呼叫 `text_to_speech` 工具
- **THEN** 框架層 SHALL 自動注入 `ctos_user_id`、`group_id`、`agent_id` 參數
- **AND** 工具 SHALL 將這些參數傳入 `resolve_voice_settings()` 取得最終設定

#### Scenario: 文字前處理
- **WHEN** 傳入的文字包含 Markdown 格式或 Emoji
- **THEN** 系統 SHALL 先清除 Markdown 標記和 Emoji 再送入 TTS 引擎
- **AND** 若清理後文字超過 500 字，SHALL 截斷並加上「...後續請參考文字訊息」

#### Scenario: voice 模組未安裝
- **WHEN** AI 呼叫 `text_to_speech` 但 voice 模組未載入
- **THEN** 工具 SHALL 回傳錯誤訊息「語音功能未安裝」

#### Scenario: TTS 生成失敗
- **WHEN** TTS 引擎生成音檔時發生錯誤
- **THEN** 工具 SHALL 回傳錯誤訊息描述失敗原因
- **AND** SHALL 記錄錯誤到 logger

---

### Requirement: Bot 層語音訊息組裝
Bot 回覆層 SHALL 自動偵測 AI 回覆中的 `[VOICE_MESSAGE:{...}]` 標記，並組裝為平台語音訊息。

#### Scenario: 解析 AI 回覆中的語音標記
- **WHEN** AI 回覆文字包含 `[VOICE_MESSAGE:{"file_id":"<uuid>","duration_ms":<ms>}]`
- **THEN** `parse_ai_response()` SHALL 提取語音訊息資訊
- **AND** SHALL 從回覆文字中移除該標記
- **AND** SHALL 回傳 `(text, files, voices)` 三元組

#### Scenario: Line Bot 語音訊息發送
- **WHEN** 解析到語音標記且平台為 Line
- **THEN** 系統 SHALL 建立 `AudioMessage(original_content_url, duration)`
- **AND** `original_content_url` SHALL 指向 `/api/voice/tts/{file_id}.mp3`
- **AND** SHALL 與文字訊息、圖片訊息一起透過 `reply_messages()` 發送

#### Scenario: Telegram Bot 語音訊息發送
- **WHEN** 解析到語音標記且平台為 Telegram
- **THEN** 系統 SHALL 讀取 NAS 上的音檔 bytes
- **AND** SHALL 呼叫 `adapter.send_voice()` 上傳音檔

#### Scenario: 無語音標記
- **WHEN** AI 回覆不包含 `[VOICE_MESSAGE:{...}]` 標記
- **THEN** 系統 SHALL 正常發送文字和檔案訊息（行為不變）

---

### Requirement: Agent prompt 語音工具引導
Agent prompt SHALL 包含語音工具使用指引，引導 AI 在適當時機使用語音回覆。

#### Scenario: 語音訊息優先語音回覆
- **WHEN** 使用者用語音訊息發問（訊息含 `[語音訊息]` 前綴）
- **THEN** prompt SHALL 引導 AI 優先使用 `text_to_speech` 工具附帶語音回覆

#### Scenario: AI 可自訂語音內容
- **WHEN** AI 決定使用語音回覆
- **THEN** prompt SHALL 說明 AI 可指定要轉語音的文字（不一定是完整回覆）
- **AND** 例如可以只唸摘要、用更口語的方式表達

#### Scenario: 不適合語音的情況
- **WHEN** AI 回覆主要是圖片、檔案、程式碼或表格
- **THEN** prompt SHALL 引導 AI 不使用語音回覆
