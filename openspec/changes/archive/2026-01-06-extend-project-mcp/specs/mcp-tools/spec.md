## ADDED Requirements

### Requirement: 新增專案成員 MCP 工具
MCP Server SHALL 提供 `add_project_member` 工具讓 AI 助手新增專案成員。

#### Scenario: 新增內部成員
- **GIVEN** AI 助手有專案 ID 和成員資訊
- **WHEN** 呼叫 `add_project_member(project_id, name="王小明", role="工程師", is_internal=true)`
- **THEN** 系統在該專案新增內部成員
- **AND** 回傳新增的成員 ID 和資訊

#### Scenario: 新增外部聯絡人
- **GIVEN** AI 助手有專案 ID 和聯絡人資訊
- **WHEN** 呼叫 `add_project_member(project_id, name="客戶A", company="XX公司", is_internal=false)`
- **THEN** 系統在該專案新增外部聯絡人
- **AND** 回傳新增的成員資訊

#### Scenario: 專案不存在
- **WHEN** 呼叫 `add_project_member` 且專案 ID 不存在
- **THEN** 回傳錯誤訊息「專案不存在」

---

### Requirement: 新增專案里程碑 MCP 工具
MCP Server SHALL 提供 `add_project_milestone` 工具讓 AI 助手新增專案里程碑。

#### Scenario: 新增里程碑含預計日期
- **GIVEN** AI 助手有專案 ID 和里程碑資訊
- **WHEN** 呼叫 `add_project_milestone(project_id, name="設計完成", planned_date="2026-01-15")`
- **THEN** 系統在該專案新增里程碑
- **AND** 回傳新增的里程碑 ID 和資訊

#### Scenario: 新增里程碑指定類型
- **GIVEN** AI 助手有專案 ID
- **WHEN** 呼叫 `add_project_milestone(project_id, name="出貨", milestone_type="delivery")`
- **THEN** 系統新增指定類型的里程碑

#### Scenario: 專案不存在
- **WHEN** 呼叫 `add_project_milestone` 且專案 ID 不存在
- **THEN** 回傳錯誤訊息「專案不存在」

---
