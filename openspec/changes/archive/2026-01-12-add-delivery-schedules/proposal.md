# Proposal: add-delivery-schedules

## Summary
在專案管理應用程式中新增「發包/交貨」標籤頁，用於追蹤專案中廠商發包與料件交貨期程。支援透過前端 UI 和 AI（MCP 工具）進行新增與更新操作。

## Motivation
擎添工業的專案涉及多個廠商發包和料件採購，目前缺乏統一的追蹤機制。使用者需要能夠：
1. 記錄每筆發包的廠商、料件、數量、發包日期和預計交貨日期
2. 追蹤發包狀態（待發包 → 已發包 → 已到貨 → 已完成）
3. 透過 AI 助手快速更新發包進度（例如：「某廠商的某料件已到貨」）

## Scope
- **新增**：`project_delivery_schedules` 資料表
- **修改**：專案管理前端，新增「發包/交貨」標籤頁
- **新增**：後端 API 端點（CRUD）
- **新增**：MCP 工具（add_delivery_schedule、update_delivery_schedule、get_delivery_schedules）
- **修改**：Line Bot prompt，讓 AI 知道新工具的用途

## Out of Scope
- 發包金額追蹤（可於未來迭代加入）
- 與廠商的自動通知功能
- 與會計系統的整合

## Design Decisions
1. **資料結構**：發包記錄以一對多關聯至專案（一個專案多筆發包）
2. **狀態流程**：四階段（pending → ordered → delivered → completed）
3. **AI 更新**：透過 MCP 工具，AI 可根據使用者口述更新狀態
4. **前端位置**：作為專案管理的第六個標籤頁（概覽、成員、會議、附件、連結、發包/交貨）

## Dependencies
- 現有的專案管理模組（project-management spec）
- MCP Server 框架（mcp-tools spec）

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| AI 誤判更新對象 | MCP 工具需要精確匹配廠商+料件名稱，找不到時要求澄清 |
| 狀態轉換邏輯混亂 | 允許任意狀態轉換，由使用者自行決定 |
