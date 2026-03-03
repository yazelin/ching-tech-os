## ADDED Requirements

### Requirement: /start 歡迎指令
系統 SHALL 提供 `/start` 指令，回覆歡迎訊息並引導使用者綁定 CTOS 帳號。

#### Scenario: 個人對話執行 /start
- **WHEN** 用戶在個人對話中發送 `/start`
- **THEN** 系統 SHALL 回覆歡迎訊息
- **AND** 訊息包含 Bot 功能介紹
- **AND** 訊息包含帳號綁定步驟說明
- **AND** 訊息包含 `/help` 指令提示

#### Scenario: 群組中執行 /start
- **WHEN** 用戶在群組中發送 `/start`
- **THEN** 系統 SHALL 靜默忽略（`private_only=true`）

#### Scenario: /start 不要求綁定
- **WHEN** 未綁定帳號的用戶發送 `/start`
- **THEN** 系統 SHALL 正常回覆歡迎訊息（`require_bound=false`）

### Requirement: /help 動態指令列表
系統 SHALL 提供 `/help` 指令，動態列出所有已註冊且可用的指令說明。

#### Scenario: 一般用戶執行 /help
- **WHEN** 非管理員用戶在個人對話中發送 `/help`
- **THEN** 系統 SHALL 回覆指令列表
- **AND** 列表僅包含 `require_admin=false` 的已啟用指令
- **AND** 列表根據 `ctx.platform_type` 過濾（僅顯示支援當前平台的指令）
- **AND** 每個指令顯示名稱和說明

#### Scenario: 管理員執行 /help
- **WHEN** 管理員用戶在個人對話中發送 `/help`
- **THEN** 系統 SHALL 回覆完整指令列表
- **AND** 包含管理員專用指令（如 `/debug`、`/agent`），標註「（管理員）」

#### Scenario: /help 不要求綁定
- **WHEN** 未綁定帳號的用戶發送 `/help`
- **THEN** 系統 SHALL 正常回覆指令列表（`require_bound=false`）

#### Scenario: /help 內容格式
- **WHEN** 系統生成 /help 回覆
- **THEN** 回覆 SHALL 包含以下區塊：
- **AND** 基本使用說明（如何對話、群組觸發方式）
- **AND** 指令列表（格式：`/指令名 — 說明`）
- **AND** 帳號綁定說明

#### Scenario: 指令顯示別名
- **WHEN** 指令有別名
- **THEN** /help SHALL 在指令說明中顯示主要別名（如 `/reset — 重置對話（/新對話）`）

### Requirement: SlashCommand description 欄位
SlashCommand 資料結構 SHALL 新增 `description` 字串欄位，供 `/help` 指令使用。

#### Scenario: 每個指令包含 description
- **WHEN** 指令透過 `register_builtin_commands()` 註冊
- **THEN** 每個指令 SHALL 設定 `description` 欄位
- **AND** description 為簡短的繁體中文說明（如「重置對話歷史」、「系統診斷」）

### Requirement: 移除 Telegram 寫死的 /start 和 /help
Telegram handler SHALL 移除寫死的 `/start` 和 `/help` 處理邏輯，改由 CommandRouter 統一處理。

#### Scenario: Telegram /start 由 CommandRouter 處理
- **WHEN** Telegram 用戶發送 `/start`
- **THEN** CommandRouter SHALL 匹配並執行 `/start` handler
- **AND** Telegram handler 中的 `START_MESSAGE` 常數和對應 if 區塊 SHALL 被移除

#### Scenario: Telegram /help 由 CommandRouter 處理
- **WHEN** Telegram 用戶發送 `/help`
- **THEN** CommandRouter SHALL 匹配並執行 `/help` handler
- **AND** Telegram handler 中的 `HELP_MESSAGE` 常數和對應 if 區塊 SHALL 被移除
