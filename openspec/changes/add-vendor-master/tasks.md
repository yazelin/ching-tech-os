# Tasks: 廠商主檔與關聯整合

## 1. 資料庫 Migration
- [ ] 1.1 建立 `vendors` 廠商主檔資料表
- [ ] 1.2 新增 `project_delivery_schedules.vendor_id` 外鍵
- [ ] 1.3 新增 `project_delivery_schedules.item_id` 外鍵
- [ ] 1.4 新增 `inventory_items.default_vendor_id` 外鍵
- [ ] 1.5 建立相關索引

## 2. 後端 API
- [ ] 2.1 建立 `/api/vendors` CRUD API
- [ ] 2.2 更新 `/api/projects/{id}/deliveries` 支援 vendor_id 和 item_id
- [ ] 2.3 更新 inventory API 支援 default_vendor_id

## 3. MCP 工具
- [ ] 3.1 新增 `query_vendors` 工具
- [ ] 3.2 新增 `add_vendor` 工具
- [ ] 3.3 新增 `update_vendor` 工具
- [ ] 3.4 更新 `add_delivery_schedule` 支援 vendor_id
- [ ] 3.5 更新 `update_delivery_schedule` 支援 vendor_id
- [ ] 3.6 更新 Line Bot prompts

## 4. 前端 - 廠商管理應用（獨立應用）
- [ ] 4.1 在 desktop.js 註冊「廠商管理」應用
- [ ] 4.2 建立 vendor-manager.js 模組
- [ ] 4.3 建立 vendor-manager.css 樣式
- [ ] 4.4 實作廠商列表頁面
- [ ] 4.5 實作廠商新增/編輯表單
- [ ] 4.6 實作廠商搜尋功能

## 5. 前端 - 發包/交貨 UI 修改
- [ ] 5.1 廠商欄位改為 combo box（可選擇或手動輸入）
- [ ] 5.2 料件欄位改為 combo box（可選擇物料或手動輸入）
- [ ] 5.3 顯示已關聯的廠商/物料資訊

## 6. 前端 - 物料管理 UI 修改
- [ ] 6.1 預設廠商欄位改為可選擇

## 7. 測試與文件
- [ ] 7.1 測試 API 功能
- [ ] 7.2 測試 MCP 工具功能
- [ ] 7.3 測試前端 UI 功能
- [ ] 7.4 更新相關文件
