# bot-platform Specification

## Purpose
多平台 Bot 整合框架，支援 Line 和 Telegram 平台的統一訊息處理、AI 互動及資料儲存。
## Requirements
### Requirement: BotAdapter Protocol 定義
系統 SHALL 定義平台無關的 BotAdapter Protocol，作為所有訊息平台的統一介面。

#### Scenario: 標準化發送介面
- **WHEN** 系統需要發送訊息到任何平台
- **THEN** 透過 BotAdapter Protocol 的統一方法發送
- **AND** 所有平台 Adapter 必須實作 `send_text`、`send_image`、`send_file` 方法
- **AND** 每個方法回傳 `SentMessage`（包含 message_id、platform_type）

#### Scenario: 可選的訊息編輯能力
- **WHEN** 平台支援訊息編輯（如 Telegram）
- **THEN** 平台 Adapter 額外實作 `EditableMessageAdapter` Protocol
- **AND** 提供 `edit_message` 和 `delete_message` 方法
- **AND** 業務邏輯透過 `isinstance()` 檢查是否可用

#### Scenario: 可選的進度通知能力
- **WHEN** 平台支援即時更新訊息（如 Telegram 的 edit_message）
- **THEN** 平台 Adapter 額外實作 `ProgressNotifier` Protocol
- **AND** 提供 `send_progress`、`update_progress`、`finish_progress` 方法
- **AND** AI 處理期間的 tool 執行狀態可透過此介面即時更新

### Requirement: BotMessage 正規化格式
系統 SHALL 使用統一的 BotMessage 格式處理所有平台的訊息。

#### Scenario: 入站訊息正規化
- **WHEN** 收到任何平台的訊息
- **THEN** 平台 Adapter 將訊息轉換為 `BotMessage` 格式
- **AND** 包含 `platform_type`、`sender_id`、`target_id`、`text`、`media`、`context_type`（private/group）
- **AND** 平台特定資料存於 `platform_data` 字典

#### Scenario: 出站回應建構
- **WHEN** AI 處理完成需要回覆
- **THEN** 核心邏輯產生 `BotResponse`（text + images + files）
- **AND** 平台 Adapter 將 `BotResponse` 轉換為平台特定格式發送

### Requirement: BotContext 對話情境
系統 SHALL 使用統一的 BotContext 管理對話情境，不包含租戶資訊。

#### Scenario: 建構對話情境
- **WHEN** 收到訊息觸發 AI 處理
- **THEN** 系統建構 `BotContext` 包含 `platform_type`、`user_id`、`group_id`、`conversation_type`
- **AND** 不包含 `tenant_id` 欄位
- **AND** 平台 Adapter 負責從平台事件填充 context

#### Scenario: 依情境選擇 Agent
- **WHEN** 系統需要選擇 AI Agent
- **THEN** 根據 `BotContext.conversation_type`（private/group）選擇對應 Agent
- **AND** Agent 選擇邏輯與平台無關

### Requirement: 平台無關的 AI 處理核心
系統 SHALL 將 AI 處理邏輯抽離為平台無關的共用模組，不處理租戶邏輯。

#### Scenario: 統一的 AI 處理流程
- **WHEN** 任何平台觸發 AI 處理
- **THEN** 共用核心負責：Agent 選擇、system prompt 建構、對話歷史組合、Claude CLI 呼叫、回應解析
- **AND** 不處理租戶相關邏輯

#### Scenario: system prompt 建構
- **WHEN** 系統建構 AI system prompt
- **THEN** 核心邏輯組合：Agent 基礎 prompt + 使用者權限 + 對話情境 + 自訂記憶
- **AND** 不包含租戶資訊

#### Scenario: 回應解析
- **WHEN** Claude CLI 回傳 AI 回應
- **THEN** 核心邏輯負責解析 FILE_MESSAGE 標記、圖片生成自動處理
- **AND** 產生平台無關的 `BotResponse`

### Requirement: 多平台資料儲存
系統 SHALL 使用統一的資料表結構儲存多平台資料，不包含租戶欄位。

#### Scenario: bot_groups 資料表
- **WHEN** 系統儲存群組
- **THEN** 群組資料存於 `bot_groups` 資料表
- **AND** 包含 `platform_type` 欄位（'line'、'telegram' 等）
- **AND** 包含 `platform_group_id` 欄位（平台原生群組 ID）
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_users 資料表
- **WHEN** 系統儲存使用者
- **THEN** 使用者資料存於 `bot_users` 資料表
- **AND** 包含 `platform_type` 欄位
- **AND** 包含 `platform_user_id` 欄位（平台原生用戶 ID）
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_messages 資料表
- **WHEN** 系統儲存訊息
- **THEN** 訊息資料存於 `bot_messages` 資料表
- **AND** 關聯到 `bot_groups` 和 `bot_users`
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_files 資料表
- **WHEN** 系統儲存檔案
- **THEN** 檔案資料存於 `bot_files` 資料表
- **AND** 關聯到 `bot_messages`
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_binding_codes 資料表
- **WHEN** 系統產生綁定驗證碼
- **THEN** 驗證碼資料存於 `bot_binding_codes` 資料表
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_group_memories 和 bot_user_memories 資料表
- **WHEN** 系統儲存自訂記憶
- **THEN** 記憶資料存於 `bot_group_memories` 和 `bot_user_memories` 資料表
- **AND** 分別關聯到 `bot_groups` 和 `bot_users`
- **AND** 不包含 `tenant_id` 欄位

### Requirement: Agent 管理通用化
系統 SHALL 將 Agent 管理邏輯從 Line 專屬改為平台通用。

#### Scenario: 通用 Agent 初始化
- **WHEN** 應用程式啟動
- **THEN** 系統確保預設的 bot Agent 存在（bot-personal、bot-group）
- **AND** 保持與舊 Agent name（linebot-personal、linebot-group）的向後相容映射

#### Scenario: 動態工具 prompt 生成
- **WHEN** 系統建構 Agent prompt
- **THEN** 動態工具 prompt 生成邏輯與平台無關
- **AND** 根據使用者的 app 權限決定可用工具

#### Scenario: 動態工具白名單生成
- **WHEN** 任何平台（Line、Telegram）需要組裝 AI 呼叫的工具白名單
- **THEN** 系統 SHALL 透過 `bot/agents.py` 的 `get_tools_for_user()` 函式，從 SkillManager 動態產生工具名稱列表
- **AND** 根據使用者的 app 權限過濾可用的 skills
- **AND** 合併所有可用 skills 的 tools 列表作為白名單
- **AND** 各平台 handler 不再硬編碼 nanobanana、printer、erpnext 等外部 MCP 工具列表

#### Scenario: SkillManager 載入失敗時 fallback
- **WHEN** SkillManager 無法載入 skill YAML（檔案遺失、格式錯誤等）
- **THEN** 系統 SHALL fallback 到硬編碼的工具列表
- **AND** 記錄 warning 日誌
- **AND** 不中斷 AI 處理流程

### Requirement: Telegram Bot Message Reception
Telegram Bot MUST 使用 polling（`getUpdates`）模式主動向 Telegram API 拉取訊息更新。

#### Scenario: 正常 polling 接收訊息
- **WHEN** polling 服務啟動且 Telegram 有新訊息
- **THEN** 系統透過 `getUpdates` 取得更新並交由 `handle_update()` 處理

#### Scenario: 服務啟動時自動開始 polling
- **WHEN** FastAPI 應用程式啟動
- **THEN** 系統自動刪除現有 webhook 並啟動 polling 背景任務

#### Scenario: 服務關閉時優雅停止
- **WHEN** FastAPI 應用程式關閉
- **THEN** polling 任務被取消，當前處理中的訊息完成後才結束

#### Scenario: 網路錯誤自動重試
- **WHEN** polling 過程中發生網路錯誤
- **THEN** 系統以指數退避方式自動重試，不丟失訊息（透過 offset 機制）
