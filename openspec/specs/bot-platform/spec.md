## ADDED Requirements

### Requirement: Telegram Bot 主動推送背景任務結果
Telegram Bot SHALL 在主動推送功能未明確停用時（預設開啟），於背景任務完成後自動推送結果給發起任務的使用者或群組。

#### Scenario: Telegram 主動推送預設開啟
- **WHEN** `bot_settings` 中無 Telegram `proactive_push_enabled` 記錄
- **AND** 背景任務完成
- **THEN** 系統 SHALL 視為啟用，主動推送結果

#### Scenario: 個人對話任務完成主動推送
- **WHEN** 背景任務完成
- **AND** Telegram `proactive_push_enabled` 不為 `"false"`
- **AND** `caller_context.is_group` 為 `false`
- **THEN** 系統 SHALL 使用 Telegram `send_text()` 推送結果給 `caller_context.platform_user_id`

#### Scenario: 群組對話任務完成主動推送
- **WHEN** 背景任務完成
- **AND** Telegram `proactive_push_enabled` 不為 `"false"`
- **AND** `caller_context.is_group` 為 `true`
- **THEN** 系統 SHALL 使用 Telegram `send_text()` 推送結果到 `caller_context.group_id`

#### Scenario: 管理員停用 Telegram 主動推送
- **WHEN** 管理員將 Telegram `proactive_push_enabled` 設為 `"false"`
- **THEN** 系統 SHALL 不主動推送任何背景任務結果
