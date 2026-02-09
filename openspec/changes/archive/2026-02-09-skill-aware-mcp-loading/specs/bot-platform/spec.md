## MODIFIED Requirements

### Requirement: 平台無關的 AI 處理核心
系統 SHALL 將 AI 處理邏輯抽離為平台無關的共用模組。

#### Scenario: 統一的 AI 處理流程
- **WHEN** 任何平台觸發 AI 處理
- **THEN** 共用核心負責：Agent 選擇、system prompt 建構、對話歷史組合、Claude CLI 呼叫、回應解析
- **AND** 平台特定的發送邏輯由各平台 Adapter 處理

#### Scenario: system prompt 建構
- **WHEN** 系統建構 AI system prompt
- **THEN** 核心邏輯組合：Agent 基礎 prompt + 使用者權限 + 對話情境 + 自訂記憶
- **AND** 平台特定資訊（如群組綁定專案）透過 BotContext 傳入

#### Scenario: 回應解析
- **WHEN** Claude CLI 回傳 AI 回應
- **THEN** 核心邏輯負責解析 FILE_MESSAGE 標記、圖片生成自動處理
- **AND** 產生平台無關的 `BotResponse`

#### Scenario: MCP Server 按需載入
- **WHEN** 系統建立 ClaudeClient 準備呼叫 AI
- **THEN** 系統 SHALL 透過 SkillManager 的 `get_required_mcp_servers()` 取得用戶權限所需的 MCP server 名稱集合
- **AND** 只啟動該集合中的 MCP server，而非全部
- **AND** `ching-tech-os` server SHALL 永遠被載入，不受過濾影響

#### Scenario: MCP Server 過濾失敗時 fallback
- **WHEN** SkillManager 取得 MCP server 集合失敗（模組不可用、YAML 損壞等）
- **THEN** 系統 SHALL fallback 到載入全部 MCP server
- **AND** 記錄 warning 日誌
- **AND** AI 處理流程不中斷
