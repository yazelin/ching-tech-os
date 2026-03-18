## ADDED Requirements

### Requirement: TTS 引擎抽象介面
系統 SHALL 定義 `TTSEngine` 抽象基底類別，所有 TTS 引擎 SHALL 實作此介面。介面設計 SHALL 相容三種差異極大的 TTS 引擎（Edge TTS、Google Cloud TTS、Gemini Native Audio）。

#### Scenario: 引擎介面定義
- **WHEN** 新增 TTS 引擎實作
- **THEN** 引擎 SHALL 實作 `synthesize_audio(text: str, **params) -> bytes` 方法
- **AND** SHALL 實作 `list_voices(language: str) -> list[VoiceInfo]` 方法
- **AND** SHALL 實作 `get_config_schema() -> dict` 方法
- **AND** `synthesize_audio` SHALL 回傳 MP3 格式的音訊 bytes
- **AND** `**params` SHALL 由各引擎自行定義（Edge: `voice`、Google: `voice`+`speed`+`pitch`、Gemini: `style`）

#### Scenario: 引擎設定 schema
- **WHEN** 呼叫引擎的 `get_config_schema()`
- **THEN** SHALL 回傳描述該引擎設定欄位的 dict
- **AND** 每個欄位 SHALL 包含 `type`（`select` / `slider` / `text`）
- **AND** `select` 類型 SHALL 搭配 `list_voices()` 提供選項
- **AND** `slider` 類型 SHALL 包含 `min`、`max`、`default`、`step` 屬性
- **AND** `text` 類型 SHALL 包含 `placeholder` 屬性

#### Scenario: 共用前處理邏輯
- **WHEN** 呼叫 `synthesize()` 主函式
- **THEN** 系統 SHALL 先執行共用前處理（Markdown 清除、Emoji 過濾、文字截斷）
- **AND** 再將清理後的文字和使用者的 `tts_params` 傳入引擎的 `synthesize_audio()`
- **AND** 最後執行共用後處理（存檔到 NAS、計算 duration）

---

### Requirement: 引擎選擇與切換
系統 SHALL 支援透過環境變數 `TTS_ENGINE` 切換 TTS 引擎。

#### Scenario: 預設引擎
- **WHEN** `TTS_ENGINE` 環境變數未設定或為 `edge`
- **THEN** 系統 SHALL 使用 `EdgeTTSEngine`

#### Scenario: 切換引擎
- **WHEN** `TTS_ENGINE` 設定為 `google_cloud` 或 `gemini`
- **THEN** 系統 SHALL 使用對應的引擎實作
- **AND** 若該引擎尚未實作，SHALL 拋出 `NotImplementedError` 並記錄錯誤

#### Scenario: 引擎單例
- **WHEN** 多次呼叫 TTS 功能
- **THEN** 系統 SHALL 重用同一個引擎實例（lazy singleton）
- **AND** 引擎實例 SHALL 在模組層級快取

---

### Requirement: Edge TTS 引擎實作
`EdgeTTSEngine` SHALL 封裝現有的 Edge TTS 邏輯。

#### Scenario: 語音生成
- **WHEN** 呼叫 `EdgeTTSEngine.synthesize_audio(text, voice="zh-TW-HsiaoChenNeural")`
- **THEN** SHALL 使用 `edge-tts` 套件生成 MP3 音訊
- **AND** 預設語音角色 SHALL 為 `zh-TW-HsiaoChenNeural`（可透過 `TTS_VOICE` 環境變數覆蓋）

#### Scenario: 語音角色列表
- **WHEN** 呼叫 `EdgeTTSEngine.list_voices(language)`
- **THEN** SHALL 回傳該語言可用的 Edge TTS 語音清單
- **AND** 每個語音 SHALL 包含 `id`、`name`、`gender`、`language` 欄位

#### Scenario: 設定 schema
- **WHEN** 呼叫 `EdgeTTSEngine.get_config_schema()`
- **THEN** SHALL 回傳 `{"voice": {"type": "select", "label": "語音角色", "required": true}}`

---

### Requirement: VoiceInfo 統一資料結構
系統 SHALL 定義 `VoiceInfo` 資料結構作為語音角色資訊的統一格式。

#### Scenario: VoiceInfo 欄位
- **WHEN** 引擎回傳語音角色資訊
- **THEN** 每個 `VoiceInfo` SHALL 包含以下欄位：
  - `id`: 引擎內部語音識別碼（如 `zh-TW-HsiaoChenNeural`）
  - `name`: 人類可讀的語音名稱（如「曉臻（女聲）」）
  - `gender`: 性別（`male` / `female` / `neutral`）
  - `language`: 語言代碼（如 `zh-TW`）
