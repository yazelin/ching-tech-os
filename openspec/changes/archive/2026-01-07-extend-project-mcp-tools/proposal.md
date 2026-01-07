# Change: 擴充專案管理 MCP 工具

## Why
目前 MCP 工具只有新增功能（add_project_member, add_project_milestone），缺乏更新功能。此外，雖然群組對話已經會傳遞綁定專案資訊給 AI，但 Prompt 沒有明確引導 AI 如何使用，且缺乏專案操作的權限控制。

**重要**：需要避免 A 專案人員不小心改到 B 專案的資料（因為沒參與該專案，更新很可能是錯誤的）。

## What Changes

### MCP 工具新增
- `update_project` - 更新專案基本資訊
- `update_milestone` - 更新里程碑狀態與資訊
- `update_project_member` - 更新成員資訊
- `add_project_meeting` - 新增會議記錄
- `update_project_meeting` - 更新會議記錄（AI 先讀取完整內容，整合後再更新）

### 權限控制（Phase 2 - 待實作）
需要完整的權限檢查流程：

```
Line 用戶 → 關聯 CTOS 用戶 → 檢查是否為專案成員 → 允許/拒絕操作
```

**權限規則：**
- 群組對話（有綁定專案）：只能操作綁定的專案，不檢查成員
- 群組對話（無綁定專案）：需要是專案成員才能更新
- 個人對話：需要是專案成員才能更新該專案

**實作方式：**
1. `line_users` 表新增 `ctos_user_id` 欄位（關聯 CTOS 用戶）
2. Line Bot 對話時，將用戶的 `ctos_user_id` 傳給 MCP 工具（透過 context）
3. MCP 工具根據 context 中的用戶身份檢查權限
4. 無權限時回傳錯誤訊息：「您不是此專案的成員，無法進行此操作」

### 資料庫變更
- `project_members` 新增 `user_id` 欄位（可選，關聯到 CTOS 用戶）✅ 已完成
- `line_users` 新增 `ctos_user_id` 欄位（關聯到 CTOS 用戶）⏳ 待實作

### Prompt 更新
- 群組對話：只能操作綁定專案，不可操作其他專案
- 個人對話：從對話上下文推斷，無法判斷時詢問用戶

## 現況說明
- 群組對話已有傳遞綁定專案（`linebot_ai.py:726-730`）
- `project_members.user_id` 已實作，可關聯 CTOS 用戶
- 權限檢查函數 `check_project_member_permission` 已建立，但尚未在 MCP 工具中啟用

## Impact
- Affected specs: `mcp-tools`, `line-bot`, `project-management`
- Affected code:
  - `backend/src/ching_tech_os/services/mcp_server.py` - 新增 MCP 工具 + 權限檢查
  - `backend/src/ching_tech_os/services/linebot_agents.py` - 更新 Prompt
  - `backend/src/ching_tech_os/services/linebot_ai.py` - 傳遞用戶身份給 MCP
  - `backend/migrations/` - 新增 `line_users.ctos_user_id`
