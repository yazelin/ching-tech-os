# Change: 擴展知識庫與專案管理 MCP 工具

## Why
目前 Line Bot AI 透過 MCP 工具管理知識庫時有以下限制：

1. `update_knowledge_item` 只能修改 title、content、category、topics，無法修改：
   - `type` - 知識類型
   - `projects` - 關聯專案（多選）
   - `roles` - 適用角色（多選）
   - `level` - 難度層級

2. 沒有建立專案的 MCP 工具，AI 無法在對話中建立新專案並將知識庫關聯到該專案

這限制了 AI 助理幫助用戶完整管理知識庫和專案的能力。

## What Changes
1. 擴展 `update_knowledge_item` MCP 工具，新增 `type`、`projects`、`roles`、`level` 參數
2. 新增 `create_project` MCP 工具，支援在對話中建立新專案

## Impact
- Affected specs: `knowledge-base`, `project-management`
- Affected code:
  - `backend/src/ching_tech_os/services/mcp_server.py` - 擴展 `update_knowledge_item`、新增 `create_project`
  - `backend/src/ching_tech_os/services/linebot_agents.py` - 更新 prompt 說明
  - `backend/migrations/versions/013_update_linebot_prompts.py` - 同步更新
