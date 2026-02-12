## ADDED Requirements

### Requirement: 外部 Skill 根目錄
系統 SHALL 支援外部 skill 根目錄，預設為 `~/SDD/skill`。

#### Scenario: 啟動時載入 skills
- **WHEN** 系統啟動並掃描 skills
- **THEN** 先掃描 `~/SDD/skill`
- **AND** 再掃描專案內建 skills 目錄作為 fallback

#### Scenario: 同名 skill 覆蓋
- **WHEN** 外部與內建目錄存在同名 skill
- **THEN** 以外部 skill 為準
- **AND** 記錄來源覆蓋日誌

---

### Requirement: 內建 Skill 拆分治理
系統 SHALL 以單一責任原則拆分內建 skills，降低單一 skill 負擔。

#### Scenario: 規劃拆分
- **WHEN** 盤點內建 skill 功能
- **THEN** 將多責任 skill 拆分為多個獨立 skill
- **AND** 每個 skill 僅保留單一職責與最小工具集合

---

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

---

### Requirement: 功能等價驗證
系統 SHALL 在 script 化遷移過程維持功能等價與穩定性。

#### Scenario: 切換能力實作路徑
- **WHEN** 某能力從 MCP 切換到 script
- **THEN** 必須通過功能對照驗證（輸入、輸出、錯誤行為）
- **AND** 確保使用者可觀察行為與既有流程一致
