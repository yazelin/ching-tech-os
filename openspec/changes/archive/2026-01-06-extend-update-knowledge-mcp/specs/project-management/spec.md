## ADDED Requirements

### Requirement: MCP 工具建立專案
專案管理 MCP 服務 SHALL 提供 `create_project` 工具，支援在對話中建立新專案。

#### Scenario: AI 建立新專案
- **WHEN** AI 呼叫 `create_project` 工具
- **AND** 提供 `name` 參數（專案名稱）
- **THEN** 系統建立新專案
- **AND** 返回新專案的 ID 和名稱

#### Scenario: 建立專案含描述
- **WHEN** AI 呼叫 `create_project` 工具
- **AND** 提供 `name` 和 `description` 參數
- **THEN** 系統建立含描述的新專案

#### Scenario: 建立專案含日期
- **WHEN** AI 呼叫 `create_project` 工具
- **AND** 提供 `start_date` 和/或 `end_date` 參數
- **THEN** 系統建立含預計日期的新專案

#### Scenario: 專案名稱重複
- **WHEN** AI 呼叫 `create_project` 工具
- **AND** 提供的專案名稱已存在
- **THEN** 系統返回錯誤訊息「專案名稱已存在」

---
