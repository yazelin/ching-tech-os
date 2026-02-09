# ai-management Specification

## Purpose
TBD - created by archiving change add-ai-management. Update Purpose after archive.
## Requirements
### Requirement: AI Prompt 管理
AI 管理系統 SHALL 支援動態管理 AI Prompts。

#### Scenario: 取得 Prompt 列表
- **WHEN** 使用者請求 `GET /api/ai/prompts`
- **THEN** 系統回傳所有 prompts 列表
- **AND** 每個 prompt 包含 id、name、display_name、category、description、updated_at

#### Scenario: 依分類過濾 Prompts
- **WHEN** 使用者請求 `GET /api/ai/prompts?category=system`
- **THEN** 系統回傳該分類的 prompts

#### Scenario: 取得 Prompt 詳情
- **WHEN** 使用者請求 `GET /api/ai/prompts/{id}`
- **THEN** 系統回傳 prompt 完整內容
- **AND** 包含 content、variables、引用此 prompt 的 agents

#### Scenario: 新增 Prompt
- **WHEN** 使用者請求 `POST /api/ai/prompts`
- **AND** 提供 name、content、category 等欄位
- **THEN** 系統建立新 prompt
- **AND** 回傳建立的 prompt 資料

#### Scenario: 更新 Prompt
- **WHEN** 使用者請求 `PUT /api/ai/prompts/{id}`
- **AND** 提供更新欄位
- **THEN** 系統更新 prompt 內容
- **AND** 更新 updated_at 時間戳

#### Scenario: 刪除 Prompt
- **WHEN** 使用者請求 `DELETE /api/ai/prompts/{id}`
- **AND** 該 prompt 未被任何 agent 引用
- **THEN** 系統刪除該 prompt

#### Scenario: 刪除被引用的 Prompt
- **WHEN** 使用者請求刪除被 agent 引用的 prompt
- **THEN** 系統回傳錯誤訊息
- **AND** 列出引用該 prompt 的 agents

---

### Requirement: AI Agent 設定管理
AI 管理系統 SHALL 支援管理 AI Agent 配置。

#### Scenario: 取得 Agent 列表
- **WHEN** 使用者請求 `GET /api/ai/agents`
- **THEN** 系統回傳所有 agents 列表
- **AND** 每個 agent 包含 id、name、display_name、model、is_active

#### Scenario: 取得 Agent 詳情
- **WHEN** 使用者請求 `GET /api/ai/agents/{id}`
- **THEN** 系統回傳 agent 完整資訊
- **AND** 包含關聯的 system_prompt 內容

#### Scenario: 新增 Agent
- **WHEN** 使用者請求 `POST /api/ai/agents`
- **AND** 提供 name、model、system_prompt_id 等欄位
- **THEN** 系統建立新 agent
- **AND** 回傳建立的 agent 資料

#### Scenario: 更新 Agent
- **WHEN** 使用者請求 `PUT /api/ai/agents/{id}`
- **THEN** 系統更新 agent 設定

#### Scenario: 啟用/停用 Agent
- **WHEN** 使用者請求 `PUT /api/ai/agents/{id}` 並設定 is_active
- **THEN** 系統更新 agent 啟用狀態

#### Scenario: 刪除 Agent
- **WHEN** 使用者請求 `DELETE /api/ai/agents/{id}`
- **THEN** 系統刪除該 agent
- **AND** 相關的 AI logs 保留（agent_id 設為 null）

#### Scenario: 依名稱取得 Agent
- **WHEN** 使用者請求 `GET /api/ai/agents/by-name/{name}`
- **THEN** 系統回傳該名稱的 agent 資訊

---

### Requirement: AI Log 記錄
AI 管理系統 SHALL 記錄所有 AI 調用日誌，**包含完整的請求資訊**。

#### Scenario: 記錄完整對話輸入
- **WHEN** 系統透過 `call_agent()` 調用 AI
- **AND** 傳入對話歷史 `history`
- **THEN** 系統記錄 `input_prompt` 為組合後的完整對話內容

#### Scenario: 記錄允許的工具
- **WHEN** 系統調用 AI 且 Agent 設定有 tools
- **THEN** 系統記錄 `allowed_tools` 為當時允許使用的工具列表

#### Scenario: 無工具設定
- **WHEN** 系統調用 AI 但 Agent 無 tools 設定
- **THEN** `allowed_tools` 記錄為 null

---

### Requirement: AI Service 整合
AI 管理系統 SHALL 提供統一的 AI 調用服務。

#### Scenario: 透過 Agent 調用 AI
- **WHEN** 服務調用 `AiService.call(agent_name, message, context)`
- **THEN** 系統根據 agent 設定取得 model 和 system_prompt
- **AND** 調用 AI 並自動記錄到 ai_logs

#### Scenario: Agent 不存在或已停用
- **WHEN** 調用不存在或停用的 agent
- **THEN** 系統回傳錯誤訊息

#### Scenario: 測試 Agent
- **WHEN** 使用者請求 `POST /api/ai/test`
- **AND** 提供 agent_id 和 test_message
- **THEN** 系統調用該 agent 並回傳結果
- **AND** 記錄為 context_type='test' 的 log

---

### Requirement: Prompt 編輯器應用
系統 SHALL 提供獨立的 Prompt 編輯器桌面應用。

#### Scenario: 開啟 Prompt 編輯器
- **WHEN** 使用者點擊 Taskbar 的 Prompt 編輯器圖示
- **THEN** 開啟 Prompt 編輯器視窗

#### Scenario: 顯示 Prompt 列表
- **WHEN** Prompt 編輯器視窗開啟
- **THEN** 左側顯示 Prompt 列表
- **AND** 上方顯示分類過濾標籤

#### Scenario: 選擇 Prompt 編輯
- **WHEN** 使用者點擊 Prompt 項目
- **THEN** 右側顯示該 Prompt 的編輯表單
- **AND** 包含名稱、分類、內容等欄位

#### Scenario: 儲存 Prompt
- **WHEN** 使用者修改 Prompt 並點擊儲存
- **THEN** 系統更新 Prompt 內容
- **AND** 顯示儲存成功訊息

#### Scenario: 新增 Prompt
- **WHEN** 使用者點擊「新增」按鈕
- **THEN** 右側顯示空白編輯表單
- **WHEN** 使用者填寫並儲存
- **THEN** 系統建立新 Prompt

#### Scenario: 刪除 Prompt
- **WHEN** 使用者點擊「刪除」按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 系統刪除該 Prompt

---

### Requirement: Agent 設定應用
系統 SHALL 提供獨立的 Agent 設定桌面應用。

#### Scenario: 開啟 Agent 設定
- **WHEN** 使用者點擊 Taskbar 的 Agent 設定圖示
- **THEN** 開啟 Agent 設定視窗

#### Scenario: 顯示 Agent 列表
- **WHEN** Agent 設定視窗開啟
- **THEN** 左側顯示 Agent 列表
- **AND** 每個 Agent 顯示名稱和啟用狀態指示

#### Scenario: 選擇 Agent 編輯
- **WHEN** 使用者點擊 Agent 項目
- **THEN** 右側顯示該 Agent 的設定表單
- **AND** 包含名稱、Model 選擇、Prompt 選擇、啟用狀態

#### Scenario: 測試 Agent
- **WHEN** 使用者在 Agent 設定頁面點擊「測試」按鈕
- **THEN** 顯示測試輸入框
- **WHEN** 使用者輸入測試訊息並送出
- **THEN** 系統調用該 Agent 並顯示回應結果

#### Scenario: 儲存 Agent
- **WHEN** 使用者修改 Agent 設定並點擊儲存
- **THEN** 系統更新 Agent 設定
- **AND** 顯示儲存成功訊息

---

### Requirement: AI Log 應用
系統 SHALL 提供獨立的 AI Log 桌面應用，**包含工具使用視覺化**。

#### Scenario: Log 列表顯示 Tools
- **WHEN** 使用者查看 Log 列表
- **THEN** 列表在「類型」後、「耗時」前顯示 Tools 欄位
- **AND** 預設只顯示實際使用的工具（used_tools），以實心背景 + 白字呈現
- **AND** 若有未使用的允許工具，顯示 `+N` 展開按鈕（N = allowed_tools 數量 - used_tools 數量）
- **AND** 若無任何工具使用，顯示 `-`

#### Scenario: 展開顯示 allowed tools
- **WHEN** 使用者點擊 `+N` 展開按鈕
- **THEN** 展開顯示完整的 allowed_tools 列表
- **AND** 已使用的工具保持實心背景 + 白字
- **AND** 未使用的工具顯示為淡色邊框樣式
- **AND** 再次點擊可收合回只顯示 used tools

#### Scenario: Tool Calls 預設折疊
- **WHEN** 使用者點擊 Log 查看詳情
- **AND** 該 Log 有工具調用記錄
- **THEN** 執行流程區塊中的 Tool Calls 預設為折疊狀態

#### Scenario: 複製完整請求
- **WHEN** 使用者點擊「複製完整請求」按鈕
- **THEN** 系統組合 system_prompt、allowed_tools、input_prompt
- **AND** 複製到剪貼簿
- **AND** 顯示複製成功提示

### Requirement: AI 對話 Agent 整合
現有 AI 對話應用 SHALL 改用資料庫的 Agent/Prompt 設定。

#### Scenario: 新對話選擇 Agent
- **WHEN** 使用者建立新對話
- **THEN** 工具列顯示 Agent 選擇下拉選單
- **AND** 預設選擇「web-chat-default」

#### Scenario: 對話使用 Agent 設定
- **WHEN** 使用者在對話中發送訊息
- **THEN** 系統使用該對話的 Agent 設定
- **AND** 從 Agent 取得 model 和 system_prompt
- **AND** 調用 AI 並記錄到 ai_logs

#### Scenario: 向後相容舊對話
- **WHEN** 載入舊對話（使用 prompt_name）
- **THEN** 系統自動映射到對應的 Agent
- **AND** 對話功能正常運作

---

### Requirement: 資料庫儲存
AI 管理系統 SHALL 使用 PostgreSQL 資料庫儲存資料。

#### Scenario: ai_logs 新增 allowed_tools 欄位
- **WHEN** 系統儲存 AI log
- **THEN** log 資料包含 `allowed_tools JSONB` 欄位
- **AND** 欄位可為 null

---

### Requirement: Presentation Designer Agent
The system SHALL provide a presentation designer AI agent that generates visual design specifications for presentations.

The agent SHALL be registered in the `ai_agents` table with:
- `code`: "presentation_designer"
- `name`: "簡報設計師"
- `model`: "sonnet" (for design quality)
- `prompt_name`: "presentation_designer"

The agent SHALL consider the following factors when designing:
- Content type (technical, marketing, financial, product)
- Target audience (client, internal team, investor, technical staff)
- Presentation scenario (projection, online meeting, print, tablet)
- Brand/industry tone (tech, manufacturing, eco-friendly, luxury)
- Slide count and information density

The agent SHALL output a complete `design_json` specification including:
- Color scheme appropriate for the scenario
- Typography settings for readability
- Layout configuration for content organization
- Decoration elements for visual interest

#### Scenario: Design for client presentation
- **WHEN** the agent receives content for a client presentation
- **THEN** the agent outputs a professional design with polished colors
- **AND** the design emphasizes credibility and visual appeal

#### Scenario: Design for internal sharing
- **WHEN** the agent receives content for internal team sharing
- **THEN** the agent outputs a casual design with friendly colors
- **AND** the design prioritizes clarity over formality

#### Scenario: Design for projection display
- **WHEN** the presentation scenario is large venue projection
- **THEN** the agent outputs a dark background design
- **AND** the agent increases font sizes for visibility
- **AND** the agent uses high contrast colors

### Requirement: Presentation Designer Prompt
The system SHALL store a `presentation_designer` prompt in the `prompts` table.

The prompt SHALL instruct the AI to:
- Analyze the provided content and context
- Apply professional design principles (color theory, visual hierarchy, contrast)
- Output valid JSON matching the `design_json` schema
- Provide appropriate fallback values for optional fields

The prompt SHALL be updatable via database without code changes.

#### Scenario: Prompt retrieval
- **WHEN** the presentation designer agent is invoked
- **THEN** the system retrieves the prompt from the `prompts` table
- **AND** the system uses the latest prompt content

#### Scenario: Prompt update
- **WHEN** an administrator updates the prompt in the database
- **THEN** subsequent agent invocations use the updated prompt
- **AND** no service restart is required

### Requirement: AI 圖片生成模型資訊顯示
AI 助理 SHALL 根據 nanobanana MCP 的回應，在圖片生成完成後告知用戶實際使用的模型。

#### Scenario: 使用 Pro 模型成功
- **WHEN** nanobanana 回應 `modelUsed` 為 `gemini-3-pro-image-preview`
- **AND** `usedFallback` 為 `false`
- **THEN** AI 回覆不特別標註模型（預設高品質）

#### Scenario: 使用 Flash 模型（fallback）
- **WHEN** nanobanana 回應 `modelUsed` 為 `gemini-2.5-flash-image`
- **AND** `usedFallback` 為 `true`
- **THEN** AI 回覆標註「（快速模式）」或類似說明
- **AND** 讓用戶了解圖片可能與預期有差異

#### Scenario: 使用 FLUX 備用服務
- **WHEN** nanobanana MCP 完全失敗（timeout 或錯誤）
- **AND** 系統 fallback 到 Hugging Face FLUX
- **THEN** AI 回覆標註「（備用服務）」
- **AND** 說明可能需要較長時間或品質有所不同

---

### Requirement: 簡化圖片生成 Fallback 機制
圖片生成服務 SHALL 採用兩層 fallback 架構。

#### Scenario: 第一層 - nanobanana MCP
- **WHEN** 用戶請求生成圖片
- **THEN** 系統優先使用 nanobanana MCP
- **AND** nanobanana 內部自動處理 Gemini Pro → Flash 的 fallback

#### Scenario: 第二層 - FLUX 備用
- **WHEN** nanobanana MCP 完全失敗（timeout、API 錯誤、無回應）
- **THEN** 系統 fallback 到 Hugging Face FLUX
- **AND** 記錄 fallback 原因

#### Scenario: 移除重複的 Gemini Flash 層
- **WHEN** 系統處理圖片生成 fallback
- **THEN** 不再直接呼叫 Gemini Flash API
- **AND** Gemini 相關的 fallback 由 nanobanana MCP 內部處理

