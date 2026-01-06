# 實作任務清單

## 1. 新增專案成員 MCP 工具
- [ ] 1.1 在 `mcp_server.py` 新增 `add_project_member` 函數
  - 呼叫 `await ensure_db_connection()` 確保資料庫連線
  - 參數：project_id, name (必填), role, company, email, phone, notes, is_internal
  - 呼叫 `project.create_member`
  - 回傳新增的成員資訊

## 2. 新增專案里程碑 MCP 工具
- [ ] 2.1 在 `mcp_server.py` 新增 `add_project_milestone` 函數
  - 呼叫 `await ensure_db_connection()` 確保資料庫連線
  - 參數：project_id, name (必填), milestone_type, planned_date, actual_date, status, notes
  - 日期格式：YYYY-MM-DD
  - 呼叫 `project.create_milestone`
  - 回傳新增的里程碑資訊

## 3. 更新 Agent Prompts
- [ ] 3.1 更新 `linebot_agents.py` 中的群組對話 prompt
  - 加入 `add_project_member` 工具說明
  - 加入 `add_project_milestone` 工具說明
- [ ] 3.2 更新 `013_update_linebot_prompts.py` migration 檔案
  - 同步新的 prompt 內容
- [ ] 3.3 直接更新資料庫中的 prompt 資料
  - 執行 SQL 或 migration 更新現有資料
