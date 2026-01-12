# Change: Line Bot 知識庫來源與權限機制

## Why

目前透過 Line Bot 建立的知識一律設為全域知識（scope=global），導致：
1. 一般使用者無法編輯自己透過 Line Bot 建立的知識
2. 除了管理員外，其他人都無法修改 Line Bot 產生的內容
3. 缺乏專案級別的知識管理機制

## What Changes

### 知識庫來源自動判斷
- **個人聊天**：建立個人知識（scope=personal），建立者可編輯
- **群組聊天**：若群組有綁定專案，建立專案知識（scope=project），專案成員可編輯
- **其他情況**：維持全域知識（scope=global）

### 知識庫權限擴展
- 新增 scope=project 類型，關聯 project_id
- 專案成員可編輯/刪除專案級別知識
- 管理員或有 global_write/global_delete 權限的人可編輯/刪除任何知識

### MCP 工具更新
- `add_note` 和 `add_note_with_attachments` 新增對話脈絡參數
- 根據 line_group_id/line_user_id 自動判斷知識來源

## Impact
- Affected specs: knowledge-base, line-bot, mcp-tools
- Affected code:
  - `backend/src/ching_tech_os/services/mcp_server.py`（add_note 工具）
  - `backend/src/ching_tech_os/services/knowledge.py`（知識服務）
  - `backend/src/ching_tech_os/services/permissions.py`（權限檢查）
  - `backend/src/ching_tech_os/api/knowledge.py`（知識 API）
  - `backend/src/ching_tech_os/models/knowledge.py`（知識模型）
  - `backend/src/ching_tech_os/services/linebot_agents.py`（Agent prompt）
  - 知識庫索引 `index.json` 結構更新
