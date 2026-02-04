## 1. 資料遷移腳本

- [x] 1.1 建立遷移腳本目錄結構 `scripts/migrate_to_erpnext/`
- [x] 1.2 實作廠商遷移 `migrate_vendors.py`（vendors → Supplier）
- [x] 1.3 實作物料遷移 `migrate_items.py`（inventory_items → Item）
- [x] 1.4 實作期初庫存建立（Stock Entry - Material Receipt）
- [x] 1.5 實作專案遷移 `migrate_projects.py`（projects → Project）
- [x] 1.6 實作專案子資料遷移（members、milestones、meetings、attachments、links）
- [x] 1.7 實作 ID 映射表保存功能
- [x] 1.8 實作 dry-run 模式
- [x] 1.9 實作遷移驗證腳本

## 2. MCP 工具移除

- [x] 2.1 移除專案管理 MCP 工具（mcp_server.py 中 23 個工具）
- [x] 2.2 移除廠商管理 MCP 工具（3 個工具）
- [x] 2.3 移除物料管理 MCP 工具（10 個工具）
- [x] 2.4 更新 `permissions.py` 移除相關權限對應

## 3. AI Agent Prompt 更新

- [x] 3.1 更新 `agents.py` 移除 CTOS 工具說明
- [x] 3.2 新增 ERPNext DocType 操作指引
- [x] 3.3 新增 ERPNext MCP 工具使用範例
- [x] 3.4 更新權限群組與 ERPNext 工具對應

## 4. 前端調整

- [x] 4.1 移除 `project-manager.js`（檔案不存在，跳過）
- [x] 4.2 移除 `inventory-manager.js`（檔案不存在，跳過）
- [x] 4.3 新增 ERPNext icon 到 `icons.js`
- [x] 4.4 更新 `desktop.js` 移除 3 個 app，新增 ERPNext app
- [x] 4.5 更新 `index.html` 移除相關 JS 引用（無相關引用）
- [x] 4.6 移除 `project-manager.css` 和 `inventory-manager.css`（檔案不存在，跳過）

## 5. API 清理

- [x] 5.1 移除或標記 deprecated：`api/project.py`（標記 deprecated）
- [x] 5.2 移除或標記 deprecated：`api/inventory.py`（標記 deprecated）
- [x] 5.3 移除或標記 deprecated：`api/vendor.py`（標記 deprecated）
- [x] 5.4 更新 `main.py` 移除相關路由註冊（保留路由，避免破壞現有功能）

## 6. 資料庫清理

- [x] 6.1 建立 migration 標記資料表 deprecated
- [x] 6.2 加入 migration 註解說明資料已遷移至 ERPNext

## 7. 測試與驗證

- [x] 7.1 執行遷移腳本 dry-run
- [x] 7.2 執行正式遷移
- [x] 7.3 驗證遷移結果（筆數比對）
- [ ] 7.4 測試 ERPNext MCP 工具操作
- [ ] 7.5 測試 Line Bot 使用 ERPNext 功能
- [ ] 7.6 測試前端 ERPNext 入口
