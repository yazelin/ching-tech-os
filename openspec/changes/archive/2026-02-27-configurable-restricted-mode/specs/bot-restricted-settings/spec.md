## MODIFIED Requirements

### Requirement: 受限模式文字模板配置化
系統 SHALL 從 `bot-restricted` Agent 的 `settings` JSONB 欄位讀取部署相關的文字模板，未設定時 SHALL fallback 到程式碼中的預設值。

#### Scenario: 讀取歡迎訊息
- **WHEN** 用戶觸發 `/start` 指令或 LINE FollowEvent
- **AND** `bot-restricted` Agent 的 `settings.welcome_message` 有值
- **THEN** 系統 SHALL 使用該值作為歡迎訊息
- **AND** 不使用程式碼中的預設歡迎訊息

#### Scenario: 歡迎訊息未設定時使用預設值
- **WHEN** 用戶觸發 `/start` 指令或 LINE FollowEvent
- **AND** `bot-restricted` Agent 的 `settings.welcome_message` 未設定或為空
- **THEN** 系統 SHALL 使用程式碼中的預設歡迎訊息（現有行為）

#### Scenario: 讀取綁定帳號提示
- **WHEN** 未綁定用戶發送訊息且 `BOT_UNBOUND_USER_POLICY=reject`
- **AND** `bot-restricted` Agent 的 `settings.binding_prompt` 有值
- **THEN** 系統 SHALL 使用該值作為綁定提示（替代平台特定的硬編碼提示）

#### Scenario: 讀取頻率超限訊息
- **WHEN** 未綁定用戶觸發頻率限制
- **AND** `bot-restricted` Agent 的 `settings.rate_limit_hourly_msg` 或 `settings.rate_limit_daily_msg` 有值
- **THEN** 系統 SHALL 使用該值作為超限訊息
- **AND** 支援 `{hourly_limit}` 和 `{daily_limit}` 變數替換

#### Scenario: 免責聲明自動附加
- **WHEN** 受限模式 AI 回覆產生成功
- **AND** `bot-restricted` Agent 的 `settings.disclaimer` 有值且非空
- **THEN** 系統 SHALL 將免責聲明文字附加到回覆結尾

#### Scenario: 免責聲明未設定時不附加
- **WHEN** 受限模式 AI 回覆產生成功
- **AND** `bot-restricted` Agent 的 `settings.disclaimer` 未設定或為空
- **THEN** 系統 SHALL 不附加任何額外文字（現有行為）

#### Scenario: AI 呼叫失敗訊息
- **WHEN** 受限模式 AI 呼叫失敗
- **AND** `bot-restricted` Agent 的 `settings.error_message` 有值
- **THEN** 系統 SHALL 使用該值作為錯誤回覆

### Requirement: Agent settings 預設初始化
系統 SHALL 在初始化 `bot-restricted` Agent 時設定 `settings` JSONB 欄位的預設值。

#### Scenario: 新部署初始化
- **WHEN** 系統首次啟動建立 `bot-restricted` Agent
- **THEN** `settings` 欄位 SHALL 包含所有文字模板的預設值
- **AND** 預設值與現有硬編碼行為一致

#### Scenario: 既有部署升級
- **WHEN** 系統升級到此版本
- **AND** `bot-restricted` Agent 已存在但 `settings` 為 null 或空
- **THEN** migration SHALL 更新 `settings` 為預設值
- **AND** 不覆蓋已有的 settings 值

### Requirement: settings 欄位結構
`bot-restricted` Agent 的 `settings` JSONB 欄位 SHALL 支援以下 key：

| Key | 類型 | 說明 | 變數替換 |
|-----|------|------|---------|
| `welcome_message` | string | 歡迎訊息 | 無 |
| `binding_prompt` | string | 綁定帳號提示 | 無 |
| `rate_limit_hourly_msg` | string | 每小時超限訊息 | `{hourly_limit}` |
| `rate_limit_daily_msg` | string | 每日超限訊息 | `{daily_limit}` |
| `disclaimer` | string\|null | 免責聲明（null 或空表示不附加） | 無 |
| `error_message` | string | AI 呼叫失敗訊息 | 無 |
