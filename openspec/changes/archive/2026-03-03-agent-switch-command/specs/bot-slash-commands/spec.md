## MODIFIED Requirements

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
