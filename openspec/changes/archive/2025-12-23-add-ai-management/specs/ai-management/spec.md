## ADDED Requirements

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
AI 管理系統 SHALL 記錄所有 AI 調用日誌。

#### Scenario: 記錄 AI 調用
- **WHEN** 系統調用 AI（透過 AI Service）
- **THEN** 系統記錄 input_prompt、raw_response、parsed_response
- **AND** 記錄 agent_id、context_type、context_id
- **AND** 記錄 duration_ms、input_tokens、output_tokens

#### Scenario: 記錄失敗調用
- **WHEN** AI 調用失敗（timeout、API 錯誤等）
- **THEN** 系統記錄 success=false 和 error_message

#### Scenario: 取得 Log 列表
- **WHEN** 使用者請求 `GET /api/ai/logs`
- **THEN** 系統回傳 AI logs 列表（分頁）
- **AND** 每筆包含 id、agent 名稱、context_type、success、duration_ms、created_at

#### Scenario: 過濾 Logs
- **WHEN** 使用者請求 `GET /api/ai/logs?agent_id={id}&context_type={type}&start_date={date}`
- **THEN** 系統回傳符合條件的 logs

#### Scenario: 取得 Log 詳情
- **WHEN** 使用者請求 `GET /api/ai/logs/{id}`
- **THEN** 系統回傳 log 完整資訊
- **AND** 包含完整的 input_prompt 和 raw_response

#### Scenario: 取得 Log 統計
- **WHEN** 使用者請求 `GET /api/ai/logs/stats`
- **THEN** 系統回傳統計資訊
- **AND** 包含總調用次數、成功率、平均 duration、token 統計

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
系統 SHALL 提供獨立的 AI Log 桌面應用。

#### Scenario: 開啟 AI Log
- **WHEN** 使用者點擊 Taskbar 的 AI Log 圖示
- **THEN** 開啟 AI Log 視窗

#### Scenario: 顯示 Log 列表
- **WHEN** AI Log 視窗開啟
- **THEN** 顯示 Log 列表
- **AND** 上方顯示過濾器（Agent、類型、日期）
- **AND** 顯示統計卡片（今日次數、成功率、平均耗時）

#### Scenario: 過濾 Logs
- **WHEN** 使用者選擇過濾條件
- **THEN** 列表即時更新顯示符合條件的 logs

#### Scenario: 查看 Log 詳情
- **WHEN** 使用者點擊 Log 項目
- **THEN** 下方或右側顯示該 Log 詳情
- **AND** 顯示完整的 input_prompt 和 raw_response
- **AND** 顯示 token 統計

#### Scenario: 分頁瀏覽
- **WHEN** Log 數量超過單頁顯示
- **THEN** 顯示分頁控制項
- **WHEN** 使用者點擊分頁
- **THEN** 載入對應頁的 logs

---

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

#### Scenario: ai_prompts 資料表
- **WHEN** 系統儲存 prompt
- **THEN** prompt 資料存於 `ai_prompts` 資料表
- **AND** 包含欄位：id、name、display_name、category、content、description、variables、created_at、updated_at

#### Scenario: ai_agents 資料表
- **WHEN** 系統儲存 agent
- **THEN** agent 資料存於 `ai_agents` 資料表
- **AND** 包含欄位：id、name、display_name、description、model、system_prompt_id、is_active、settings、created_at、updated_at

#### Scenario: ai_logs 分區表
- **WHEN** 系統儲存 AI log
- **THEN** log 資料存於 `ai_logs` 分區表
- **AND** 按月份分區（如 ai_logs_2025_01）

#### Scenario: 自動建立分區
- **WHEN** 新月份開始且對應分區不存在
- **THEN** 系統自動建立新月份的分區

#### Scenario: 級聯處理
- **WHEN** 刪除 prompt
- **THEN** 引用該 prompt 的 agents 之 system_prompt_id 設為 null
- **WHEN** 刪除 agent
- **THEN** 相關的 ai_logs 之 agent_id 設為 null
