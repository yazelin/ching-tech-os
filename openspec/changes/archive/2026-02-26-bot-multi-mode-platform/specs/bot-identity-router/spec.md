## ADDED Requirements

### Requirement: 未綁定用戶策略配置
系統 SHALL 透過環境變數 `BOT_UNBOUND_USER_POLICY` 配置未綁定用戶的處理策略，預設為 `reject`（向下相容）。

#### Scenario: reject 策略（預設）
- **WHEN** `BOT_UNBOUND_USER_POLICY` 設為 `reject` 或未設定
- **AND** 未綁定 CTOS 帳號的用戶在個人對話中發送訊息
- **THEN** 系統 SHALL 回覆綁定提示，不進行 AI 處理
- **AND** 行為與現有系統完全一致

#### Scenario: restricted 策略
- **WHEN** `BOT_UNBOUND_USER_POLICY` 設為 `restricted`
- **AND** 未綁定 CTOS 帳號的用戶在個人對話中發送訊息
- **THEN** 系統 SHALL 將訊息路由到受限模式 AI 流程

#### Scenario: 已綁定用戶不受策略影響
- **WHEN** 已綁定 CTOS 帳號的用戶發送訊息
- **THEN** 系統 SHALL 走現有的完整 AI 處理流程
- **AND** 不受 `BOT_UNBOUND_USER_POLICY` 影響

#### Scenario: 群組中未綁定用戶
- **WHEN** 未綁定用戶在群組中觸發 AI
- **THEN** 系統 SHALL 維持現有行為（靜默忽略）
- **AND** 不受 `BOT_UNBOUND_USER_POLICY` 影響

### Requirement: 身份分流路由
系統 SHALL 在 AI 處理入口（`process_message_with_ai()`）中，查詢用戶綁定狀態後、Agent 選擇前，根據策略分流訊息。

#### Scenario: 分流判斷點
- **WHEN** `process_message_with_ai()` 查詢到 `bot_users.user_id`
- **AND** `user_id` 為 NULL（未綁定）
- **THEN** 系統 SHALL 查詢 `BOT_UNBOUND_USER_POLICY` 策略
- **AND** 根據策略值呼叫對應的處理路徑

#### Scenario: 綁定驗證碼不受分流影響
- **WHEN** 未綁定用戶發送 6 位數字（綁定驗證碼）
- **THEN** 系統 SHALL 優先執行綁定驗證流程
- **AND** 不進入身份分流路由

### Requirement: 受限模式 AI 流程
當策略為 `restricted` 時，系統 SHALL 為未綁定用戶提供受限的 AI 對話流程。

#### Scenario: 選擇受限模式 Agent
- **WHEN** 未綁定用戶的訊息進入受限模式
- **THEN** 系統 SHALL 從資料庫取得 `bot-restricted` Agent 設定
- **AND** 使用 `BOT_RESTRICTED_MODEL` 環境變數指定的模型（預設 `haiku`）

#### Scenario: 組裝受限模式 system prompt
- **WHEN** 系統為受限模式組裝 system prompt
- **THEN** SHALL 包含：Agent 基礎 prompt（部署方自訂）
- **AND** SHALL 包含：受限模式工具說明（根據 Agent 的 tools 設定動態生成）
- **AND** SHALL 包含：對話識別（platform_user_id，標記為「未綁定用戶」）
- **AND** SHALL 不包含：自訂記憶、CTOS 內部工具說明

#### Scenario: 受限模式對話歷史
- **WHEN** 系統為受限模式取得對話歷史
- **THEN** SHALL 使用與已綁定用戶相同的機制（`conversation_reset_at` 過濾）
- **AND** 歷史長度限制為 10 條（較已綁定用戶的 20 條縮短）

#### Scenario: 受限模式工具白名單
- **WHEN** 系統為受限模式設定可用工具
- **THEN** SHALL 以 `bot-restricted` Agent 在 DB 中的 `tools` 欄位為準
- **AND** 預設僅包含 `search_knowledge`（限公開分類）
- **AND** 部署方可透過 AI 管理介面調整工具列表

#### Scenario: 受限模式回覆
- **WHEN** 受限模式 AI 處理完成
- **THEN** 系統 SHALL 回覆純文字訊息
- **AND** 不處理 `[FILE_MESSAGE:...]` 標記（不支援檔案/圖片發送）

### Requirement: bot-restricted Agent 預設初始化
系統 SHALL 在啟動時確保 `bot-restricted` Agent 存在。

#### Scenario: 應用程式啟動時建立預設 Agent
- **WHEN** 應用程式啟動
- **AND** `bot-restricted` Agent 不存在
- **THEN** 系統 SHALL 建立 `bot-restricted` Agent
- **AND** 預設 model 為 `BOT_RESTRICTED_MODEL` 環境變數值
- **AND** 預設 system prompt 為通用的受限助理 prompt：「你是 AI 助理，僅能回答特定範圍的問題。請根據可用工具和知識範圍提供協助。」
- **AND** 預設 tools 為 `["search_knowledge"]`

#### Scenario: 保留使用者修改
- **WHEN** 應用程式啟動
- **AND** `bot-restricted` Agent 已存在
- **THEN** 系統 SHALL 不覆蓋現有設定

#### Scenario: 部署方自訂 Agent
- **WHEN** 部署方透過 AI 管理介面修改 `bot-restricted` Agent
- **THEN** 修改後的 prompt 和工具設定 SHALL 立即生效
- **AND** 應用程式重啟不會覆蓋修改

### Requirement: 受限模式 AI 模型配置
系統 SHALL 透過環境變數 `BOT_RESTRICTED_MODEL` 配置受限模式使用的 AI 模型。

#### Scenario: 預設模型
- **WHEN** `BOT_RESTRICTED_MODEL` 未設定
- **THEN** 系統 SHALL 使用 `haiku` 作為受限模式模型

#### Scenario: 自訂模型
- **WHEN** `BOT_RESTRICTED_MODEL` 設為 `sonnet`
- **THEN** 系統 SHALL 使用 `sonnet` 模型處理受限模式訊息

### Requirement: Debug 模式 AI 模型配置
系統 SHALL 透過環境變數 `BOT_DEBUG_MODEL` 配置 debug 模式使用的 AI 模型。

#### Scenario: 預設模型
- **WHEN** `BOT_DEBUG_MODEL` 未設定
- **THEN** 系統 SHALL 使用 `sonnet` 作為 debug 模式模型

#### Scenario: 自訂模型
- **WHEN** `BOT_DEBUG_MODEL` 設為 `opus`
- **THEN** 系統 SHALL 使用 `opus` 模型處理 debug 診斷
