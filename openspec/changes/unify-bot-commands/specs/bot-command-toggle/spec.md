## ADDED Requirements

### Requirement: 指令啟用/停用開關
系統 SHALL 支援透過環境變數 `BOT_CMD_DISABLED` 停用特定斜線指令，停用的指令在 CommandRouter 中不會被匹配。

#### Scenario: 設定停用指令
- **WHEN** 環境變數 `BOT_CMD_DISABLED` 設為 `debug,start`
- **THEN** 系統啟動時 SHALL 將 `/debug` 和 `/start` 指令標記為 `enabled=false`
- **AND** 其他指令（如 `/reset`、`/help`）維持 `enabled=true`

#### Scenario: 停用的指令不被匹配
- **WHEN** 用戶發送 `/debug`
- **AND** `debug` 在 `BOT_CMD_DISABLED` 清單中
- **THEN** CommandRouter.parse() SHALL 回傳 None（不匹配）
- **AND** 訊息視為一般文字，繼續 AI 處理流程

#### Scenario: 未設定 BOT_CMD_DISABLED
- **WHEN** `BOT_CMD_DISABLED` 環境變數未設定或為空字串
- **THEN** 所有已註冊的指令 SHALL 維持啟用狀態

#### Scenario: 大小寫不敏感
- **WHEN** `BOT_CMD_DISABLED` 設為 `Debug,START`
- **THEN** 系統 SHALL 以大小寫不敏感方式比對指令名稱
- **AND** `/debug` 和 `/start` 都被停用

### Requirement: SlashCommand enabled 欄位
SlashCommand 資料結構 SHALL 新增 `enabled` 布林欄位，預設為 `true`。

#### Scenario: 註冊時設定 enabled
- **WHEN** `register_builtin_commands()` 執行
- **THEN** 每個指令的 `enabled` 欄位 SHALL 根據 `BOT_CMD_DISABLED` 設定值初始化
- **AND** 在 `BOT_CMD_DISABLED` 清單中的指令設為 `enabled=false`

#### Scenario: CommandRouter.parse() 過濾停用指令
- **WHEN** CommandRouter 解析訊息
- **AND** 匹配到一個 `enabled=false` 的指令
- **THEN** parse() SHALL 回傳 None
- **AND** 行為等同於該指令未註冊
