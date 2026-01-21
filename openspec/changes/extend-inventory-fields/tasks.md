# 實作任務清單

## 1. 資料庫變更

- [x] 1.1 建立 Alembic migration：`inventory_items` 新增 `model`、`storage_location` 欄位
- [x] 1.2 建立 Alembic migration：新增 `inventory_orders` 資料表
- [x] 1.3 執行 migration 並驗證資料庫結構

## 2. 後端 Pydantic 模型

- [x] 2.1 更新 `InventoryItemBase`：新增 `model`、`storage_location` 欄位
- [x] 2.2 更新 `InventoryItemCreate`、`InventoryItemUpdate`：支援新欄位
- [x] 2.3 更新 `InventoryItemResponse`、`InventoryItemListItem`：包含新欄位
- [x] 2.4 新增訂購記錄模型：`InventoryOrderCreate`、`InventoryOrderUpdate`、`InventoryOrderResponse`、`InventoryOrderListItem`

## 3. 後端 Service 層

- [x] 3.1 更新 `inventory.py`：`create_inventory_item`、`update_inventory_item` 支援新欄位
- [x] 3.2 新增訂購記錄函式：`create_inventory_order`、`update_inventory_order`、`delete_inventory_order`
- [x] 3.3 新增查詢函式：`list_inventory_orders`、`get_inventory_order`

## 4. 後端 API 路由

- [x] 4.1 確認現有物料 API 回傳新欄位
- [x] 4.2 新增 `GET /api/inventory/items/{id}/orders`
- [x] 4.3 新增 `POST /api/inventory/items/{id}/orders`
- [x] 4.4 新增 `PUT /api/inventory/orders/{order_id}`
- [x] 4.5 新增 `DELETE /api/inventory/orders/{order_id}`

## 5. MCP 工具

- [x] 5.1 更新 `add_inventory_item`：新增 `model`、`storage_location` 參數
- [x] 5.2 更新 `query_inventory`：回傳新欄位
- [x] 5.3 新增 `add_inventory_order` 工具
- [x] 5.4 新增 `update_inventory_order` 工具
- [x] 5.5 新增 `get_inventory_orders` 工具

## 6. Line Bot Prompt 更新

- [x] 6.1 更新 `linebot_agents.py` 的 prompt：說明新欄位和訂購工具
- [ ] 6.2 建立 migration 更新資料庫中的 prompt（注意：程式碼中的 prompt 已更新，資料庫需重啟服務自動同步）

## 7. 前端 UI

- [x] 7.1 更新物料編輯表單：新增型號、存放庫位欄位
- [x] 7.2 更新物料列表顯示：顯示型號、存放庫位
- [x] 7.3 新增「訂購記錄」標籤頁
- [x] 7.4 實作訂購記錄列表顯示
- [x] 7.5 實作訂購記錄新增表單
- [x] 7.6 實作訂購記錄編輯功能
- [x] 7.7 實作訂購記錄刪除功能
- [x] 7.8 訂購狀態顏色樣式

## 8. 測試與驗證

- [x] 8.1 測試物料 CRUD（含新欄位）- 模型和 API 驗證通過
- [x] 8.2 測試訂購記錄 CRUD - API 路由和服務函式驗證通過
- [x] 8.3 測試 MCP 工具功能 - 工具定義驗證通過
- [ ] 8.4 測試 Line Bot 對話 - 需要實際對話測試
