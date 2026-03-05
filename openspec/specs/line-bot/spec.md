## ADDED Requirements

### Requirement: Line Bot 主動推送背景任務結果
Line Bot SHALL 在主動推送功能啟用時，於背景任務完成後自動推送結果給發起任務的使用者或群組，無需使用者主動詢問。

#### Scenario: 個人對話任務完成主動推送
- **WHEN** 背景任務完成（research、下載、轉錄等）
- **AND** `bot_settings` 中 Line `proactive_push_enabled` 為 `"true"`
- **AND** `caller_context.is_group` 為 `false`
- **THEN** 系統 SHALL 使用 `push_text()` 將結果推送給 `caller_context.platform_user_id`

#### Scenario: 群組對話任務完成主動推送
- **WHEN** 背景任務完成
- **AND** `bot_settings` 中 Line `proactive_push_enabled` 為 `"true"`
- **AND** `caller_context.is_group` 為 `true`
- **THEN** 系統 SHALL 使用 `push_text()` 將結果推送到 `caller_context.group_id`
- **AND** 推送訊息遵循群組 mention 規則（若可取得 platform_user_id 則 mention 發起者）

#### Scenario: Line 主動推送預設關閉
- **WHEN** `bot_settings` 中無 Line `proactive_push_enabled` 記錄
- **THEN** 系統 SHALL 不主動推送
- **AND** 使用者仍可透過 `check-*` 指令查詢結果
