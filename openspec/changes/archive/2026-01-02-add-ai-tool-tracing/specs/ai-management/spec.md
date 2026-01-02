# ai-management Spec Delta

## MODIFIED Requirements

### Requirement: AI Log 記錄
AI 管理系統 SHALL 記錄所有 AI 調用日誌，**包含完整的工具調用過程**。

#### Scenario: 記錄 AI 調用（含工具調用）
- **WHEN** 系統調用 AI（透過 Claude CLI）
- **THEN** 系統使用 `--output-format stream-json --verbose` 取得完整輸出
- **AND** 解析並記錄 input_prompt、raw_response
- **AND** 解析並記錄 tool_calls 到 parsed_response
- **AND** 記錄 agent_id、context_type、context_id
- **AND** 記錄 duration_ms、input_tokens、output_tokens

#### Scenario: tool_calls 資料格式
- **WHEN** AI 調用包含工具使用
- **THEN** parsed_response.tool_calls 為陣列
- **AND** 每個元素包含 id、name、input、output
- **AND** 順序反映實際調用順序

#### Scenario: 無工具調用
- **WHEN** AI 調用未使用任何工具
- **THEN** parsed_response.tool_calls 為空陣列或 null

---

### Requirement: AI Log 應用
系統 SHALL 提供獨立的 AI Log 桌面應用，**包含執行流程視覺化**。

#### Scenario: 查看 Log 詳情（含執行流程）
- **WHEN** 使用者點擊 Log 項目
- **THEN** 詳情面板顯示完整資訊
- **AND** 若 parsed_response.tool_calls 存在且非空，顯示「執行流程」區塊
- **AND** 執行流程按順序顯示每個工具調用
- **AND** 每個工具調用顯示名稱、輸入、輸出
- **AND** 最後顯示最終回應

#### Scenario: 工具調用收合展開
- **WHEN** 執行流程包含多個工具調用
- **THEN** 每個工具調用區塊可收合/展開
- **AND** 預設第一個展開，其餘收合
- **AND** 輸入輸出 JSON 格式化顯示

#### Scenario: 舊 Log 相容
- **WHEN** Log 的 parsed_response 為 null 或不含 tool_calls
- **THEN** 不顯示「執行流程」區塊
- **AND** 其他資訊正常顯示
