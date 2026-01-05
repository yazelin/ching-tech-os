# ai-management Spec Delta

## MODIFIED Requirements

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

### Requirement: 資料庫儲存
AI 管理系統 SHALL 使用 PostgreSQL 資料庫儲存資料。

#### Scenario: ai_logs 新增 allowed_tools 欄位
- **WHEN** 系統儲存 AI log
- **THEN** log 資料包含 `allowed_tools JSONB` 欄位
- **AND** 欄位可為 null

---

### Requirement: AI Log 應用
系統 SHALL 提供獨立的 AI Log 桌面應用，**包含工具使用視覺化**。

#### Scenario: Log 列表顯示 Tools
- **WHEN** 使用者查看 Log 列表
- **THEN** 列表在「類型」後、「耗時」前顯示 Tools 欄位
- **AND** 可用且有使用的工具顯示為實心背景 + 白字
- **AND** 可用但未使用的工具顯示為色框 + 色字

#### Scenario: Tool Calls 預設折疊
- **WHEN** 使用者點擊 Log 查看詳情
- **AND** 該 Log 有工具調用記錄
- **THEN** 執行流程區塊中的 Tool Calls 預設為折疊狀態

#### Scenario: 複製完整請求
- **WHEN** 使用者點擊「複製完整請求」按鈕
- **THEN** 系統組合 system_prompt、allowed_tools、input_prompt
- **AND** 複製到剪貼簿
- **AND** 顯示複製成功提示
