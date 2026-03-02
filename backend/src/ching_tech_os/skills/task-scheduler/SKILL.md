---
name: task-scheduler
description: 動態排程管理工具，可建立、查詢、修改、刪除定時排程任務
allowed-tools:
  - mcp__ching-tech-os__manage_scheduled_task
  - mcp__ching-tech-os__list_scheduled_tasks
metadata:
  ctos:
    mcp_servers: ching-tech-os
    requires_app: task-scheduler
---

【排程管理工具】
管理動態排程任務，支援 Agent 執行和 Skill Script 呼叫兩種模式。

## 可用工具

### manage_scheduled_task
管理排程（建立/更新/刪除/啟用/停用）：

- **create**: 建立新排程
  · action: "create"
  · name: 排程名稱
  · trigger_type: "cron" 或 "interval"
  · trigger_config: JSON，如 {"hour": "8", "minute": "0"} 或 {"hours": 1}
  · executor_type: "agent" 或 "skill_script"
  · executor_config: JSON，如 {"agent_name": "bot", "prompt": "每日報告"}

- **update**: 更新排程
  · action: "update"
  · task_id: 排程 UUID
  · 其他欄位（僅傳需要更新的）

- **delete**: 刪除排程
  · action: "delete"
  · task_id: 排程 UUID

- **enable/disable**: 啟用/停用排程
  · action: "enable" 或 "disable"
  · task_id: 排程 UUID

### list_scheduled_tasks
查詢排程列表：
  · is_enabled: 可選，篩選啟用或停用的排程
