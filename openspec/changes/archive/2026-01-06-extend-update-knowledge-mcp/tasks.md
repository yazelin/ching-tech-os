# 實作任務清單

## 1. 擴展 update_knowledge_item MCP 工具
- [x] 1.1 在 `mcp_server.py` 的 `update_knowledge_item` 函數新增參數
  - `type: str | None` - 知識類型
  - `projects: list[str] | None` - 專案列表
  - `roles: list[str] | None` - 角色列表
  - `level: str | None` - 層級
- [x] 1.2 更新 `KnowledgeTags` 建立邏輯，整合所有標籤參數
- [x] 1.3 更新工具的 docstring 說明新參數用法

## 2. 新增 create_project MCP 工具
- [x] 2.1 在 `mcp_server.py` 新增 `create_project` 工具函數
  - 參數：name（必填）、description（選填）、start_date、end_date
- [x] 2.2 呼叫專案管理服務建立專案
- [x] 2.3 返回新建專案的 ID 和名稱

## 3. 更新 Line Bot Agent Prompt
- [x] 3.1 更新 `linebot_agents.py` 中的 prompt
  - 說明 `update_knowledge_item` 可更新的新欄位
  - 說明 `create_project` 工具用法
- [x] 3.2 更新 migration `013_update_linebot_prompts.py` 保持一致
- [x] 3.3 更新資料庫中現有的 prompt 內容
