# line-bot Specification Delta

## ADDED Requirements

### Requirement: Line Bot Agent 整合
Line Bot SHALL 使用資料庫中的 Agent/Prompt 設定進行 AI 對話處理。

#### Scenario: 個人對話使用 linebot-personal Agent
- **WHEN** Line 用戶在個人對話中發送訊息
- **AND** 觸發 AI 處理
- **THEN** 系統從資料庫取得 `linebot-personal` Agent 設定
- **AND** 使用該 Agent 的 model 設定
- **AND** 使用該 Agent 的 system_prompt 內容

#### Scenario: 群組對話使用 linebot-group Agent
- **WHEN** Line 用戶在群組中觸發 AI 處理
- **THEN** 系統從資料庫取得 `linebot-group` Agent 設定
- **AND** 使用該 Agent 的 model 設定
- **AND** 使用該 Agent 的 system_prompt 內容
- **AND** 動態附加群組資訊和綁定專案資訊到 prompt

#### Scenario: Agent 不存在時的 Fallback
- **WHEN** 系統找不到對應的 Agent 設定
- **THEN** 系統使用硬編碼的預設 Prompt 作為 fallback
- **AND** 記錄警告日誌

---

### Requirement: 預設 Line Bot Agent 初始化
系統 SHALL 在啟動時確保預設的 Line Bot Agent 存在。

#### Scenario: 應用程式啟動時檢查並建立預設 Agent
- **WHEN** 應用程式啟動
- **THEN** 系統檢查 `linebot-personal` Agent 是否存在
- **AND** 若不存在則建立預設的 `linebot-personal` Agent 和對應的 Prompt
- **AND** 系統檢查 `linebot-group` Agent 是否存在
- **AND** 若不存在則建立預設的 `linebot-group` Agent 和對應的 Prompt

#### Scenario: 保留使用者修改
- **WHEN** 應用程式啟動
- **AND** Agent 已存在
- **THEN** 系統不覆蓋現有 Agent 設定
- **AND** 保留使用者透過 UI 修改的內容

#### Scenario: linebot-personal Agent 預設設定
- **WHEN** 系統建立 `linebot-personal` Agent
- **THEN** Agent 的 model 為 `claude-sonnet`
- **AND** Prompt 類別為 `linebot`
- **AND** Prompt 內容包含 MCP 工具說明（專案查詢、知識庫搜尋等）

#### Scenario: linebot-group Agent 預設設定
- **WHEN** 系統建立 `linebot-group` Agent
- **THEN** Agent 的 model 為 `claude-haiku`
- **AND** Prompt 類別為 `linebot`
- **AND** Prompt 內容包含 MCP 工具說明
- **AND** Prompt 內容限制回覆長度（不超過 200 字）

---

### Requirement: Line Bot AI Log 記錄
Line Bot 的 AI 呼叫記錄 SHALL 正確關聯到 Agent。

#### Scenario: AI Log 記錄關聯 Agent
- **WHEN** Line Bot 完成一次 AI 呼叫
- **THEN** AI Log 的 agent_id 關聯到實際使用的 Agent（`linebot-personal` 或 `linebot-group`）
- **AND** 前端 AI Log 頁面顯示正確的 Agent 名稱

---

### Requirement: 個人對話重置功能
Line Bot SHALL 支援個人對話的對話歷史重置。

#### Scenario: 重置對話歷史
- **WHEN** Line 用戶在個人對話中發送 `/新對話` 或 `/reset`
- **THEN** 系統更新用戶的 `conversation_reset_at` 為當前時間
- **AND** 回覆「已清除對話歷史，開始新對話！」
- **AND** 後續 AI 處理不會看到重置前的對話內容

#### Scenario: 群組不支援重置
- **WHEN** Line 用戶在群組中發送重置指令
- **THEN** 系統靜默忽略，不執行重置操作
