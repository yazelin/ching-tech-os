# bot-platform spec delta

## ADDED Requirements

### Requirement: Telegram Bot 租戶級憑證儲存
系統 MUST 支援在租戶設定中儲存 Telegram Bot 憑證（bot_token、admin_chat_id），並使用加密儲存敏感欄位。

#### Scenario: 儲存 Telegram Bot Token
- Given: 平台管理員進入租戶的 Telegram Bot 設定
- When: 輸入 Bot Token 並儲存
- Then: Token 加密儲存至租戶設定，API 回應不包含明文 Token

#### Scenario: 未設定時使用全域設定
- Given: 租戶未設定獨立 Telegram Bot 憑證
- When: 系統需要發送 Telegram 訊息
- Then: 使用環境變數中的全域 Telegram Bot Token

### Requirement: Telegram Bot 設定管理 API
系統 MUST 提供 Telegram Bot 設定的 CRUD API，供平台管理和租戶管理使用。

#### Scenario: 平台管理員管理租戶 Telegram Bot
- Given: 平台管理員有權限存取 `/api/admin/tenants/{id}/telegram-bot`
- When: 呼叫 GET/PUT/DELETE API
- Then: 可查詢、更新、清除該租戶的 Telegram Bot 設定

#### Scenario: 租戶管理員管理自己的 Telegram Bot
- Given: 租戶管理員有權限存取 `/api/tenant/telegram-bot`
- When: 呼叫 GET/PUT/DELETE API
- Then: 可查詢、更新、清除自己租戶的 Telegram Bot 設定

### Requirement: Telegram Bot 連線測試
系統 MUST 提供 Telegram Bot 連線測試功能，驗證 Token 是否有效。

#### Scenario: 測試有效的 Bot Token
- Given: 租戶已設定 Telegram Bot Token
- When: 呼叫測試 API
- Then: 使用 Telegram getMe API 驗證，回傳 Bot 資訊（名稱、username）

#### Scenario: 測試無效的 Bot Token
- Given: 租戶設定了錯誤的 Token
- When: 呼叫測試 API
- Then: 回傳錯誤訊息

### Requirement: Telegram Bot 設定 UI
平台管理和租戶管理介面 MUST 提供 Telegram Bot 設定的 UI，與 Line Bot 設定並列。

#### Scenario: 平台管理顯示 Telegram Bot tab
- Given: 平台管理員開啟租戶詳情
- When: 查看 tab 列表
- Then: 可見 "Telegram Bot" tab，點擊後顯示設定表單

#### Scenario: 租戶管理顯示 Telegram Bot 設定
- Given: 租戶管理員進入設定頁面
- When: 查看 Bot 設定區域
- Then: 可見 Telegram Bot 設定區塊，包含 Bot Token 和 Admin Chat ID 欄位
