# Change: 新增倉庫/物料管理功能

## Why
公司需要追蹤物料的進貨與出貨，目前沒有統一的系統記錄，導致庫存狀況不透明。需要一個可以透過前端介面和 Line Bot 操作的物料管理系統。

## What Changes
- 新增「物料管理」桌面應用程式
- 建立物料主檔資料表（可跨專案共用）
- 建立進出貨記錄資料表（可選關聯專案）
- 新增 MCP 工具供 Line Bot 操作物料
- 新增後端 API 支援物料 CRUD 操作

## Impact
- Affected specs: `inventory-management`（新增）, `mcp-tools`（新增工具）
- Affected code:
  - `backend/migrations/versions/` - 新增資料表
  - `backend/src/ching_tech_os/models/` - 新增 Pydantic 模型
  - `backend/src/ching_tech_os/services/` - 新增業務邏輯
  - `backend/src/ching_tech_os/api/` - 新增 API 路由
  - `backend/src/ching_tech_os/services/mcp_server.py` - 新增 MCP 工具
  - `backend/src/ching_tech_os/services/linebot_agents.py` - 更新 prompt
  - `frontend/js/inventory-management.js` - 新增前端模組
  - `frontend/css/inventory-management.css` - 新增樣式
  - `frontend/js/desktop.js` - 註冊應用
  - `frontend/index.html` - 引入檔案
