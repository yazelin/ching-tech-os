## MODIFIED Requirements

### Requirement: Script-First 實作策略
skill 能力 SHALL 優先以 scripts（`.py`/`.sh`）實作，MCP 僅保留必要整合能力。

#### Scenario: 同功能存在 script 與 MCP
- **WHEN** 某能力同時可由 script 與 MCP 完成
- **THEN** 系統預設選擇 script 路徑
- **AND** 僅在 script 失敗且符合回退條件時改走 MCP

#### Scenario: 最小 MCP 使用原則
- **WHEN** 規劃新 skill
- **THEN** 優先設計 script 方案
- **AND** 僅在跨系統整合（如 ERPNext、印表機）保留 MCP

#### Scenario: native base/file-manager 第一批 script 化
- **WHEN** 載入 native `base` 與 `file-manager` skills
- **THEN** `allowed-tools` SHALL 以 `mcp__ching-tech-os__run_skill_script` 為主要入口
- **AND** 其主要功能 SHALL 由 `scripts/` 目錄中的工具實作

#### Scenario: fallback 邊界
- **WHEN** script 執行失敗屬於參數驗證或權限檢查錯誤
- **THEN** 系統 SHALL 回傳錯誤且不 fallback 到 MCP

### Requirement: 功能等價驗證
系統 SHALL 在 script 化遷移過程維持功能等價與穩定性。

#### Scenario: 切換能力實作路徑
- **WHEN** 某能力從 MCP 切換到 script
- **THEN** 必須通過功能對照驗證（輸入、輸出、錯誤行為）
- **AND** 確保使用者可觀察行為與既有流程一致

#### Scenario: external 與 native 行為對齊
- **WHEN** native `base` 或 `file-manager` 進行 script 化
- **THEN** 應以 external 同名 skill 的 scripts 行為作為對照基準
- **AND** 功能差異 SHALL 以測試或文件明確標示
