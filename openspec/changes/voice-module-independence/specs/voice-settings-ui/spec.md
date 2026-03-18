## ADDED Requirements

### Requirement: 語音設定 API
系統 SHALL 提供語音設定相關的 REST API，支援多引擎的差異化設定。

#### Scenario: 取得可用語音列表與設定 schema
- **WHEN** 請求 `GET /api/voice/voices`（可選 `engine` 查詢參數）
- **THEN** 系統 SHALL 回傳指定引擎（或預設引擎）的語音角色清單
- **AND** 回應 SHALL 包含 `engine`（引擎名稱）、`voices`（VoiceInfo 陣列）、`config_schema`（設定欄位描述）、`available_engines`（所有可用引擎名稱列表）
- **AND** `config_schema` SHALL 描述該引擎的設定欄位（type/label/required 等），供前端動態渲染 UI

#### Scenario: 取得語音設定
- **WHEN** 請求 `GET /api/voice/settings`（可選 `scope` 和 `scope_id` 查詢參數）
- **THEN** 系統 SHALL 依 scope 回傳對應層級的語音設定：
  - `scope=user`（預設）：使用者設定
  - `scope=group&scope_id=<group_id>`：群組設定
  - `scope=agent&scope_id=<agent_id>`：Agent 設定
- **AND** 回應 SHALL 包含 `tts_engine`、`tts_params`、`scope`（設定來源層級）
- **AND** 若該層級未設定，SHALL 回傳 `null` 並附帶 `effective`（實際生效的繼承設定）

#### Scenario: 儲存語音設定
- **WHEN** 請求 `PUT /api/voice/settings` 並傳入語音設定
- **THEN** 系統 SHALL 依 request body 中的 `scope` 儲存到對應層級：
  - `scope: "user"`：存到 `users.voice_settings`
  - `scope: "group"`：存到 `bot_groups.voice_settings`（需群組管理權限）
  - `scope: "agent"`：存到 `bot_agents.voice_settings`（需管理員權限）
- **AND** 設定 SHALL 包含 `tts_engine` 和 `tts_params`

#### Scenario: 清除語音設定
- **WHEN** 請求 `DELETE /api/voice/settings` 並指定 `scope`
- **THEN** 系統 SHALL 清除該層級的語音設定（回退到上一層繼承）

#### Scenario: 語音試聽
- **WHEN** 請求 `POST /api/voice/preview` 並傳入 `engine`、`params` 和可選的 `text`
- **THEN** 系統 SHALL 使用指定引擎和參數生成短句預覽音檔
- **AND** SHALL 直接回傳 `audio/mpeg` 音訊串流（不儲存到 NAS）
- **AND** 若未傳入 `text`，SHALL 使用預設試聽文字

#### Scenario: 試聽頻率限制
- **WHEN** 同一使用者在 10 秒內重複請求試聽
- **THEN** 系統 SHALL 回傳 429 Too Many Requests

---

### Requirement: 語音設定資料儲存
系統 SHALL 在多個層級儲存語音設定，採階層式繼承架構。

#### Scenario: 階層式設定存儲
- **WHEN** 儲存語音設定
- **THEN** 系統 SHALL 支援在以下四個層級儲存設定：
  - 系統預設：環境變數 `TTS_ENGINE` + `TTS_VOICE`
  - Agent 層：`bot_agents` 表 `voice_settings` JSONB 欄位
  - 群組層：`bot_groups` 表 `voice_settings` JSONB 欄位
  - 使用者層：`users` 表 `voice_settings` JSONB 欄位
- **AND** JSONB 格式 SHALL 為 `{"tts_engine": "<name>", "tts_params": {...}}`

#### Scenario: 設定解析優先級 — 私訊
- **WHEN** 解析私訊情境的語音設定
- **THEN** 系統 SHALL 依以下優先級查詢：使用者設定 > Agent 設定 > 系統預設
- **AND** SHALL 回傳第一個有設定的層級

#### Scenario: 設定解析優先級 — 群組
- **WHEN** 解析群組情境的語音設定
- **THEN** 系統 SHALL 依以下優先級查詢：群組設定 > Agent 設定 > 系統預設
- **AND** SHALL 回傳第一個有設定的層級

#### Scenario: 系統預設 fallback
- **WHEN** 所有層級均未設定語音偏好
- **THEN** 系統 SHALL 使用 `TTS_ENGINE` 環境變數選擇引擎（預設 `edge`）
- **AND** SHALL 使用 `TTS_VOICE` 環境變數作為 Edge TTS 的預設 voice（預設 `zh-TW-HsiaoChenNeural`）

---

### Requirement: 前端語音設定 App
前端 SHALL 提供語音設定桌面應用程式，替代現有的「開發中」佔位。UI SHALL 由後端 `config_schema` 動態驅動，不硬編碼任何引擎的設定元件。

#### Scenario: App 註冊
- **WHEN** 使用者開啟桌面環境
- **THEN** 語音 App SHALL 在 `desktop.js` 中註冊為可用應用程式
- **AND** 點擊 SHALL 開啟語音設定介面（不再顯示「開發中」）

#### Scenario: 引擎選擇
- **WHEN** 使用者開啟語音設定 App
- **THEN** 系統 SHALL 顯示引擎選擇器（從 `available_engines` 列表渲染）
- **AND** 切換引擎時 SHALL 重新載入該引擎的 `config_schema` 和 `voices`
- **AND** 設定表單 SHALL 依 `config_schema` 動態渲染（select → 下拉選單、slider → 滑桿、text → 文字輸入）

#### Scenario: 語音角色選擇
- **WHEN** `config_schema` 包含 `type: "select"` 的欄位
- **THEN** 系統 SHALL 渲染下拉選單，選項來自 `voices` 列表
- **AND** 目前選用的語音 SHALL 被標記為已選取

#### Scenario: 參數調整
- **WHEN** `config_schema` 包含 `type: "slider"` 的欄位（如語速、音調）
- **THEN** 系統 SHALL 渲染滑桿控制項
- **AND** SHALL 顯示目前數值和標籤

#### Scenario: 文字風格輸入
- **WHEN** `config_schema` 包含 `type: "text"` 的欄位（如 Gemini 風格描述）
- **THEN** 系統 SHALL 渲染文字輸入框
- **AND** SHALL 顯示 placeholder 提示

#### Scenario: 語音試聽
- **WHEN** 使用者調整設定後點擊試聽按鈕
- **THEN** 系統 SHALL 以目前選擇的引擎和參數呼叫 `POST /api/voice/preview`
- **AND** SHALL 在瀏覽器中播放預覽音訊
- **AND** 播放期間 SHALL 顯示播放狀態指示

#### Scenario: 儲存設定
- **WHEN** 使用者完成設定並點擊儲存
- **THEN** 系統 SHALL 呼叫 `PUT /api/voice/settings` 儲存 `tts_engine` 和 `tts_params`
- **AND** SHALL 顯示儲存成功提示
