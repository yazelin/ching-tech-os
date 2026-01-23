# AI Management Specification - Multi-Tenant Changes

## MODIFIED Requirements

### Requirement: AI Chat Sessions
系統 SHALL 管理 AI 對話 session：
- id: UUID 主鍵
- **tenant_id: UUID 租戶識別（必填）**
- user_id: 用戶 ID
- agent_id: 使用的 Agent ID
- title: 對話標題
- created_at, updated_at: 時間戳

#### Scenario: 建立對話
- **WHEN** 用戶開始新的 AI 對話
- **THEN** 自動帶入當前 session 的 tenant_id
- **AND** 對話歸屬於該租戶

#### Scenario: 查詢對話歷史
- **WHEN** 用戶查詢對話歷史
- **THEN** 僅回傳當前租戶的對話
- **AND** 不顯示其他租戶的對話

### Requirement: AI Logs
系統 SHALL 記錄 AI 呼叫日誌：
- id: UUID 主鍵
- **tenant_id: UUID 租戶識別（必填）**
- agent_id: Agent ID
- context_type: 來源類型 (line_group, line_user, web)
- context_id: 來源 ID
- input_prompt: 輸入 prompt
- raw_response: 原始回應
- success: 是否成功
- duration_ms: 執行時間

#### Scenario: 記錄 AI 呼叫
- **WHEN** AI Agent 完成一次呼叫
- **THEN** 日誌記錄包含 tenant_id
- **AND** 日誌歸屬於發起請求的租戶

#### Scenario: 查詢 AI 日誌
- **WHEN** 管理員查詢 AI 日誌
- **THEN** 僅回傳當前租戶的日誌
- **AND** 平台管理員可查詢所有租戶

### Requirement: AI Agents Configuration
系統 SHALL 管理 AI Agent 設定：
- id: UUID 主鍵
- **tenant_id: UUID 租戶識別（可選，NULL 為全域 Agent）**
- name: Agent 名稱
- type: Agent 類型 (linebot, web, api)
- model: 使用的模型
- system_prompt_id: 系統 prompt ID
- is_active: 是否啟用

#### Scenario: 全域 Agent
- **WHEN** Agent 的 tenant_id 為 NULL
- **THEN** 該 Agent 可被所有租戶使用
- **AND** 作為預設 Agent

#### Scenario: 租戶專屬 Agent
- **WHEN** Agent 設定了 tenant_id
- **THEN** 該 Agent 僅該租戶可使用
- **AND** 可覆寫全域 Agent 設定

### Requirement: AI Prompts
系統 SHALL 管理 AI Prompt 範本：
- id: UUID 主鍵
- **tenant_id: UUID 租戶識別（可選，NULL 為全域 Prompt）**
- agent_type: 適用的 Agent 類型
- name: Prompt 名稱
- content: Prompt 內容
- version: 版本號
- is_active: 是否啟用

#### Scenario: 全域 Prompt
- **WHEN** Prompt 的 tenant_id 為 NULL
- **THEN** 該 Prompt 作為預設範本
- **AND** 所有租戶可使用

#### Scenario: 租戶自訂 Prompt
- **WHEN** 租戶建立自訂 Prompt
- **THEN** 該 Prompt 的 tenant_id 為該租戶
- **AND** 優先於全域 Prompt 使用

### Requirement: AI Usage Tracking
系統 SHALL 追蹤 AI 使用量：
- 按租戶統計 API 呼叫次數
- 按租戶統計 token 使用量
- 支援用量配額限制

#### Scenario: 用量統計
- **WHEN** 查詢租戶 AI 使用統計
- **THEN** 回傳該租戶的呼叫次數和 token 用量
- **AND** 可按時間範圍篩選

#### Scenario: 用量超過配額
- **WHEN** 租戶 AI 用量超過配額
- **THEN** 後續 AI 請求回傳「用量已達上限」
- **AND** 管理員可調整配額

## ADDED Requirements

### Requirement: AI Data Isolation
系統 SHALL 確保 AI 資料的租戶隔離：
- AI 對話歷史不跨租戶共享
- AI 生成的檔案儲存於租戶目錄
- AI 搜尋結果僅包含租戶資料

#### Scenario: AI 搜尋知識庫
- **WHEN** AI 需要搜尋知識庫回答問題
- **THEN** 搜尋範圍限定於當前租戶
- **AND** 不會引用其他租戶的知識

#### Scenario: AI 生成檔案
- **WHEN** AI 生成圖片或文件
- **THEN** 檔案儲存於 /mnt/nas/ctos/tenants/{tenant_id}/ai-generated/
- **AND** 其他租戶無法存取

### Requirement: AI Context Passing
系統 SHALL 在所有 AI 互動中傳遞租戶上下文：
- Line Bot 訊息處理時帶入 tenant_id
- Web AI 助手帶入當前 session 的 tenant_id
- MCP 工具呼叫帶入 ctos_tenant_id

#### Scenario: Line Bot AI 上下文
- **WHEN** Line Bot 收到訊息並呼叫 AI
- **THEN** 從群組/用戶的 tenant_id 取得上下文
- **AND** 傳遞給 AI Agent 和 MCP 工具
