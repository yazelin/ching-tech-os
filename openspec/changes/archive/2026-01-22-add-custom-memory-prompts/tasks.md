## 1. 資料庫

- [ ] 1.1 建立 `line_group_memories` 資料表（含索引）
- [ ] 1.2 建立 `line_user_memories` 資料表（含索引）

## 2. 後端 API

- [ ] 2.1 建立記憶管理 API 路由 (`api/linebot/memories.py`)
  - GET /api/linebot/groups/{id}/memories - 取得群組記憶列表
  - POST /api/linebot/groups/{id}/memories - 新增群組記憶
  - PUT /api/linebot/memories/{id} - 更新記憶
  - DELETE /api/linebot/memories/{id} - 刪除記憶
  - GET /api/linebot/users/{id}/memories - 取得個人記憶列表
  - POST /api/linebot/users/{id}/memories - 新增個人記憶
- [ ] 2.2 建立 Pydantic models (`models/linebot.py` 擴充)
- [ ] 2.3 在 `main.py` 註冊路由

## 3. Line Bot AI 整合

- [ ] 3.1 修改 `build_system_prompt()` 載入並整合記憶
- [ ] 3.2 建立 `get_active_memories()` 輔助函式

## 4. MCP 工具

- [ ] 4.1 新增 `add_memory` 工具
- [ ] 4.2 新增 `get_memories` 工具
- [ ] 4.3 新增 `update_memory` 工具
- [ ] 4.4 新增 `delete_memory` 工具

## 5. Linebot Prompt 更新

- [ ] 5.1 更新 linebot-personal prompt 說明記憶管理功能
- [ ] 5.2 更新 linebot-group prompt 說明記憶管理功能
- [ ] 5.3 建立 migration 更新資料庫中的 prompt

## 6. 前端管理 App

- [ ] 6.1 建立 `memory-manager.js` 應用程式模組
- [ ] 6.2 建立 `memory-manager.css` 樣式
- [ ] 6.3 在 `desktop.js` 註冊應用程式
- [ ] 6.4 在 `index.html` 和 `login.html` 引入 JS/CSS
