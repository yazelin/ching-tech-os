## ADDED Requirements

### Requirement: 更新專案 MCP 工具
MCP Server SHALL 提供 `update_project` 工具讓 AI 助手更新專案資訊。

#### Scenario: 更新專案基本資訊
- **GIVEN** AI 助手有專案 ID 和要更新的資訊
- **WHEN** 呼叫 `update_project(project_id, name="新名稱", description="新描述")`
- **THEN** 系統更新專案的對應欄位
- **AND** 回傳更新後的專案資訊

#### Scenario: 更新專案狀態
- **GIVEN** AI 助手有專案 ID
- **WHEN** 呼叫 `update_project(project_id, status="completed")`
- **THEN** 系統更新專案狀態
- **AND** status 可選值：planning, in_progress, completed, on_hold

#### Scenario: 更新專案日期
- **GIVEN** AI 助手有專案 ID
- **WHEN** 呼叫 `update_project(project_id, start_date="2026-01-01", end_date="2026-06-30")`
- **THEN** 系統更新專案日期

#### Scenario: 專案不存在
- **WHEN** 呼叫 `update_project` 且專案 ID 不存在
- **THEN** 回傳錯誤訊息「專案不存在」

---

### Requirement: 更新里程碑 MCP 工具
MCP Server SHALL 提供 `update_milestone` 工具讓 AI 助手更新里程碑資訊。

#### Scenario: 更新里程碑狀態
- **GIVEN** AI 助手有里程碑 ID
- **WHEN** 呼叫 `update_milestone(milestone_id, status="completed", actual_date="2026-01-15")`
- **THEN** 系統更新里程碑狀態和實際完成日期

#### Scenario: 更新里程碑預計日期
- **GIVEN** AI 助手有里程碑 ID
- **WHEN** 呼叫 `update_milestone(milestone_id, planned_date="2026-02-01")`
- **THEN** 系統更新里程碑預計日期

#### Scenario: 更新里程碑名稱與備註
- **GIVEN** AI 助手有里程碑 ID
- **WHEN** 呼叫 `update_milestone(milestone_id, name="新名稱", notes="備註說明")`
- **THEN** 系統更新里程碑名稱和備註

#### Scenario: 里程碑不存在
- **WHEN** 呼叫 `update_milestone` 且里程碑 ID 不存在
- **THEN** 回傳錯誤訊息「里程碑不存在」

---

### Requirement: 更新專案成員 MCP 工具
MCP Server SHALL 提供 `update_project_member` 工具讓 AI 助手更新成員資訊。

#### Scenario: 更新成員角色
- **GIVEN** AI 助手有成員 ID
- **WHEN** 呼叫 `update_project_member(member_id, role="專案經理")`
- **THEN** 系統更新成員角色

#### Scenario: 更新成員聯絡資訊
- **GIVEN** AI 助手有成員 ID
- **WHEN** 呼叫 `update_project_member(member_id, email="new@email.com", phone="0912345678")`
- **THEN** 系統更新成員聯絡資訊

#### Scenario: 更新成員公司與備註
- **GIVEN** AI 助手有成員 ID
- **WHEN** 呼叫 `update_project_member(member_id, company="新公司", notes="備註")`
- **THEN** 系統更新成員公司和備註

#### Scenario: 成員不存在
- **WHEN** 呼叫 `update_project_member` 且成員 ID 不存在
- **THEN** 回傳錯誤訊息「成員不存在」

---

### Requirement: 新增專案會議 MCP 工具
MCP Server SHALL 提供 `add_project_meeting` 工具讓 AI 助手新增會議記錄。

#### Scenario: 新增會議（僅標題）
- **GIVEN** AI 助手有專案 ID
- **WHEN** 呼叫 `add_project_meeting(project_id, title="週會")`
- **THEN** 系統在該專案新增會議
- **AND** 回傳新增的會議 ID 和資訊

#### Scenario: 新增會議含日期
- **GIVEN** AI 助手有專案 ID 和會議資訊
- **WHEN** 呼叫 `add_project_meeting(project_id, title="設計審查", meeting_date="2026-01-10")`
- **THEN** 系統新增會議並設定日期

#### Scenario: 新增會議含完整記錄
- **GIVEN** AI 助手有專案 ID 和完整會議資訊
- **WHEN** 呼叫 `add_project_meeting(project_id, title="週會", meeting_date="2026-01-07", location="會議室A", content="# 會議內容\n...", attendees="王小明, 李小華")`
- **THEN** 系統新增會議記錄包含完整內容

#### Scenario: 專案不存在
- **WHEN** 呼叫 `add_project_meeting` 且專案 ID 不存在
- **THEN** 回傳錯誤訊息「專案不存在」

---

### Requirement: 更新專案會議 MCP 工具
MCP Server SHALL 提供 `update_project_meeting` 工具讓 AI 助手更新會議記錄。

#### Scenario: 更新會議內容
- **GIVEN** AI 助手有會議 ID
- **WHEN** 呼叫 `update_project_meeting(meeting_id, content="# 更新後的會議內容\n...")`
- **THEN** 系統更新會議內容

#### Scenario: 更新會議時間地點
- **GIVEN** AI 助手有會議 ID
- **WHEN** 呼叫 `update_project_meeting(meeting_id, meeting_date="2026-01-08 10:00", location="線上")`
- **THEN** 系統更新會議時間和地點

#### Scenario: 更新會議標題與參與者
- **GIVEN** AI 助手有會議 ID
- **WHEN** 呼叫 `update_project_meeting(meeting_id, title="新標題", attendees="全員")`
- **THEN** 系統更新會議標題和參與者

#### Scenario: 會議不存在
- **WHEN** 呼叫 `update_project_meeting` 且會議 ID 不存在
- **THEN** 回傳錯誤訊息「會議不存在」

