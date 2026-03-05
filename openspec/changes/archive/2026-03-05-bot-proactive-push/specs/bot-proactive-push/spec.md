## ADDED Requirements

### Requirement: 主動推送設定管理
系統 SHALL 透過 `bot_settings` 表儲存每個平台的主動推送開關，Line 預設關閉、Telegram 預設開啟。

#### Scenario: Line 平台預設關閉
- **WHEN** 系統首次初始化或 `bot_settings` 中無 `proactive_push_enabled` 記錄
- **AND** 平台為 `line`
- **THEN** 系統 SHALL 視為未啟用，不主動推送

#### Scenario: Telegram 平台預設開啟
- **WHEN** 系統首次初始化或 `bot_settings` 中無 `proactive_push_enabled` 記錄
- **AND** 平台為 `telegram`
- **THEN** 系統 SHALL 視為已啟用，主動推送任務完成通知

#### Scenario: 讀取平台推送設定
- **WHEN** 系統需判斷是否主動推送
- **THEN** 系統從 `bot_settings` 讀取 `platform=<platform>`, `key="proactive_push_enabled"` 的記錄
- **AND** 值為 `"true"` 時啟用，`"false"` 時停用
- **AND** 記錄不存在時依平台預設值處理

#### Scenario: 管理員更新推送設定
- **WHEN** 管理員呼叫 `PUT /api/admin/bot-settings/{platform}`
- **AND** 請求包含 `proactive_push_enabled: true/false`
- **THEN** 系統更新或建立對應的 `bot_settings` 記錄
- **AND** 立即生效（不需重啟）

### Requirement: 主動推送執行介面
系統 SHALL 提供統一的推送介面（`proactive_push_service`），供背景任務完成後呼叫，依平台設定決定是否推送。

#### Scenario: 平台已啟用時執行推送
- **WHEN** 背景任務完成
- **AND** 任務的 `caller_context` 包含有效的平台與用戶資訊
- **AND** 該平台的 `proactive_push_enabled` 為啟用
- **THEN** 系統 SHALL 向 `caller_context.platform_user_id`（或 `group_id`）推送完成訊息

#### Scenario: 平台未啟用時靜默跳過
- **WHEN** 背景任務完成
- **AND** 該平台的 `proactive_push_enabled` 為停用
- **THEN** 系統 SHALL 不發送任何推送，保持靜默

#### Scenario: caller_context 缺失時靜默跳過
- **WHEN** 背景任務的 `status.json` 不含 `caller_context` 欄位
- **THEN** 系統 SHALL 不發送推送
- **AND** 不影響任務結果本身

#### Scenario: 推送失敗靜默處理
- **WHEN** 推送 API 呼叫回傳錯誤
- **THEN** 系統 SHALL 記錄 warning log
- **AND** 不拋出例外、不影響任務狀態

#### Scenario: 觸發推送方式
- **WHEN** 背景子行程寫入 `status: "completed"`
- **THEN** 子行程 SHALL 以 HTTP POST 呼叫 `/api/internal/proactive-push`
- **AND** 請求包含 `job_id` 與 `skill`（用於讀取 status.json 中的 caller_context）

### Requirement: 背景任務 caller_context 傳遞
具 start/check 模式的背景 skill SHALL 接受並持久化 `caller_context`，記錄發起任務的平台與對話資訊。

#### Scenario: start script 接受 caller_context
- **WHEN** AI 呼叫 start script 時在 input JSON 附帶 `caller_context`
- **THEN** script SHALL 將其原樣寫入 `status.json`

#### Scenario: caller_context 結構
- **WHEN** 系統儲存 caller_context
- **THEN** 結構 SHALL 包含：`platform`（`"line"` 或 `"telegram"`）、`platform_user_id`（Line user ID 或 Telegram user chat_id）、`is_group`（布林）、`group_id`（群組對話時的 chat_id，個人對話為 null）

#### Scenario: caller_context 為選填
- **WHEN** AI 呼叫 start script 時未帶 `caller_context`
- **THEN** script SHALL 正常建立任務
- **AND** 任務完成時不觸發主動推送

### Requirement: 前端主動推送開關
系統 SHALL 在 Bot 設定頁面提供每個平台的主動推送開關，僅限管理員操作。

#### Scenario: 顯示主動推送開關
- **WHEN** 管理員開啟系統設定 → Bot 設定
- **THEN** Line Bot 和 Telegram Bot 設定區塊各自顯示「主動推送」切換開關
- **AND** 開關狀態反映當前 `bot_settings` 的值（Line 預設顯示關閉，Telegram 預設顯示開啟）

#### Scenario: 管理員切換開關
- **WHEN** 管理員點擊主動推送切換開關
- **THEN** 系統呼叫 `PUT /api/admin/bot-settings/{platform}`
- **AND** 更新成功後開關狀態即時反映
- **AND** 顯示操作成功提示
