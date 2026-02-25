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
Agent 管理 SHALL 依啟用模組動態產生工具 prompt 和工具白名單，停用模組的工具說明和工具 SHALL 不出現。

#### Scenario: 通用 Agent 初始化
- **WHEN** 應用程式啟動且 Line Bot Agent 不存在
- **THEN** 系統 SHALL 自動建立預設 Agent 和 Prompt

#### Scenario: 動態工具 prompt 生成
- **WHEN** 為使用者組裝 system prompt
- **THEN** SHALL 呼叫 `generate_tools_prompt(app_permissions)` 只包含啟用模組的工具說明
- **THEN** 停用模組對應的 `APP_PROMPT_MAPPING` 片段 SHALL 被跳過

#### Scenario: 動態工具白名單生成
- **WHEN** 呼叫 `get_tools_for_user(app_permissions)`
- **THEN** SHALL 從 SkillManager 動態產生工具名稱列表，根據使用者 app 權限過濾可用 skills
- **THEN** 停用模組的 `app_id` SHALL 不存在於 `app_permissions` 中，其工具自動被排除
- **THEN** 各平台 handler 不再硬編碼工具列表

#### Scenario: SkillManager 載入失敗時 fallback
- **WHEN** SkillManager 載入失敗
- **THEN** SHALL fallback 到 `_FALLBACK_TOOLS` 硬編碼工具列表
- **THEN** 硬編碼列表同樣 SHALL 依 `app_permissions`（已排除停用模組）過濾

#### Scenario: script 與 MCP 能力重疊
- **WHEN** 同一功能同時存在 script 實作與 MCP 工具
- **THEN** 預設 SHALL 優先暴露 script tool（`run_skill_script`）
- **THEN** 被抑制的 MCP 工具 SHALL 不出現在白名單中

#### Scenario: script 執行失敗回退
- **WHEN** script 執行失敗且 `SKILL_SCRIPT_FALLBACK_ENABLED=true`
- **THEN** SHALL 允許回退到對應的 MCP tool

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

### Requirement: 外部研究任務優先 script-first 路由
Bot 平台在判斷外部研究任務時 SHALL 優先使用 `run_skill_script` 呼叫 `research-skill`，避免預設直接走同步 WebSearch/WebFetch。

#### Scenario: 研究查詢走 start-research
- **WHEN** 使用者請求需要外部搜尋與擷取的研究任務
- **THEN** 系統優先呼叫 `run_skill_script(skill="research-skill", script="start-research", ...)`
- **AND** 不直接以內建 WebSearch/WebFetch 啟動長流程同步回合

#### Scenario: script 明確要求回退
- **WHEN** `research-skill` 回傳 `fallback_required`
- **AND** `SKILL_SCRIPT_FALLBACK_ENABLED=true`
- **THEN** 系統允許回退到既有工具路徑
- **AND** 記錄回退原因與路由決策

### Requirement: 研究任務結果可追蹤
Bot 平台處理研究任務時 MUST 讓後續回合可用 `job_id` 查詢，並可從部分成果組裝可回覆內容。

#### Scenario: start 回傳 job_id 後的對話狀態
- **WHEN** `start-research` 成功回傳 `job_id`
- **THEN** 系統在當前回合回覆受理訊息與查詢方式
- **AND** 後續回合可使用 `check-research` 取得進度或最終結果

#### Scenario: 同步回合失敗但有部分成果
- **WHEN** 外部研究流程遇到逾時或部分工具失敗
- **THEN** 系統優先回覆可用的部分成果或查詢指引
- **AND** 不得僅回覆空白結果
