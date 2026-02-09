## MODIFIED Requirements

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
