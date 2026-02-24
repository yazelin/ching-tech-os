## MODIFIED Requirements

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
