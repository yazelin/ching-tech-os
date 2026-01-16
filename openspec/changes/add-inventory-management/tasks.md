# Tasks: 物料管理功能實作

## 1. 資料庫設計
- [x] 1.1 建立 `inventory_items` 資料表（物料主檔）
- [x] 1.2 建立 `inventory_transactions` 資料表（進出貨記錄）
- [x] 1.3 建立 Alembic migration 檔案
- [x] 1.4 執行 migration 並驗證

## 2. 後端 API
- [x] 2.1 建立 Pydantic 資料模型 (`models/inventory.py`)
- [x] 2.2 建立業務邏輯層 (`services/inventory.py`)
- [x] 2.3 建立 API 路由 (`api/inventory.py`)
- [x] 2.4 在 `main.py` 註冊路由
- [x] 2.5 測試 API 端點

## 3. MCP 工具
- [x] 3.1 新增 `query_inventory` 工具（查詢物料/庫存）
- [x] 3.2 新增 `add_inventory_item` 工具（新增物料）
- [x] 3.3 新增 `record_inventory_in` 工具（進貨記錄）
- [x] 3.4 新增 `record_inventory_out` 工具（出貨記錄）
- [x] 3.5 新增 `adjust_inventory` 工具（庫存調整）
- [x] 3.6 更新 Line Bot prompt（`linebot_agents.py`）
- [ ] 3.7 建立 migration 更新資料庫 prompt（選用：prompt 已在程式碼中更新）

## 4. 前端應用
- [x] 4.1 建立 `inventory-management.js` 模組
- [x] 4.2 建立 `inventory-management.css` 樣式
- [x] 4.3 在 `desktop.js` 註冊應用
- [x] 4.4 在 `index.html` 引入檔案
- [x] 4.5 實作物料列表介面
- [x] 4.6 實作物料 CRUD 表單
- [x] 4.7 實作進出貨記錄列表
- [x] 4.8 實作進出貨記錄表單

## 5. 驗證與測試
- [x] 5.1 前端功能測試（語法檢查通過）
- [ ] 5.2 Line Bot 功能測試（待實際環境測試）
- [ ] 5.3 整合測試（待實際環境測試）
