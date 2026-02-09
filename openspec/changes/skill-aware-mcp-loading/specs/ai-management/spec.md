## MODIFIED Requirements

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
