# Proposal: extend-project-mcp

## Summary
擴充專案 MCP 工具，新增 `add_project_member` 和 `add_project_milestone`，讓 AI 助手能夠完整地建立專案，包含成員和里程碑。

## Problem Statement
目前 MCP 工具有 `create_project` 可以建立專案，但無法新增成員和里程碑。當用戶要求建立新專案並指定成員和里程碑時，AI 只能建立專案本體，成員和里程碑需要用戶手動新增。

## Proposed Solution
新增兩個 MCP 工具：
1. `add_project_member` - 新增專案成員
2. `add_project_milestone` - 新增專案里程碑

這兩個工具將呼叫現有的 `project.create_member` 和 `project.create_milestone` service 函數。

## Scope
- 新增：`mcp_server.py` 中的 `add_project_member` 工具
- 新增：`mcp_server.py` 中的 `add_project_milestone` 工具

## Out of Scope
- 不新增更新或刪除成員/里程碑的工具（可以之後擴充）
- 不修改現有的專案 service 函數
