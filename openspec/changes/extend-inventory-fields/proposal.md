# Change: 擴充物料主檔欄位

## Why

目前物料管理系統僅支援基本的物料資訊（名稱、規格、單位、類別、預設廠商、最低庫存量、備註），無法追蹤訂購相關資訊。使用者需要完整的物料採購與存放管理能力，包含型號、訂購數量、下單日期、交貨日期、存放庫位以及專案使用狀態等資訊。

## What Changes

- **資料庫變更**
  - `inventory_items` 表新增欄位：model（型號）、storage_location（存放庫位）
  - 新增 `inventory_orders` 表追蹤訂購記錄：訂購數量、下單日期、預計交貨日期、實際交貨日期、狀態

- **前端 UI 變更**
  - 新增物料表單新增：型號、存放庫位欄位
  - 新增「訂購記錄」標籤頁（在概覽、進出貨記錄之外）
  - 支援建立、編輯、刪除訂購記錄

- **MCP 工具變更**
  - `add_inventory_item` 新增 model、storage_location 參數
  - 新增 `add_inventory_order` 工具
  - 新增 `update_inventory_order` 工具
  - 新增 `get_inventory_orders` 工具
  - 修改 `query_inventory` 回傳新欄位

- **API 變更**
  - 新增訂購記錄相關 API 端點
  - 修改現有物料 API 支援新欄位

## Impact

- Affected specs: `inventory-management`, `mcp-tools`
- Affected code:
  - `backend/migrations/versions/` - 新增 migration
  - `backend/src/ching_tech_os/models/inventory.py`
  - `backend/src/ching_tech_os/services/inventory.py`
  - `backend/src/ching_tech_os/api/inventory.py`
  - `backend/src/ching_tech_os/services/mcp_server.py`
  - `backend/src/ching_tech_os/services/linebot_agents.py`
  - `frontend/js/inventory-management.js`
  - `frontend/css/inventory-management.css`

## Scope

### 欄位定義

| 欄位 | 資料庫欄位名 | 類型 | 必填 | 說明 |
|------|-------------|------|------|------|
| 型號 | model | varchar(200) | 否 | 物料的型號規格 |
| 存放庫位 | storage_location | varchar(200) | 否 | 存放位置（如 A-1-3 表示 A 區 1 排 3 號） |

### 訂購記錄欄位

| 欄位 | 資料庫欄位名 | 類型 | 必填 | 說明 |
|------|-------------|------|------|------|
| 訂購數量 | order_quantity | numeric(15,3) | 是 | 訂購數量 |
| 下單日期 | order_date | date | 否 | 下單日期 |
| 預計交貨日 | expected_delivery_date | date | 否 | 預計交貨日期 |
| 實際交貨日 | actual_delivery_date | date | 否 | 實際交貨日期 |
| 狀態 | status | varchar(20) | 是 | pending/ordered/delivered/cancelled |
| 廠商 | vendor | varchar(200) | 否 | 訂購廠商 |
| 關聯專案 | project_id | uuid | 否 | 物料使用的專案 |
| 備註 | notes | text | 否 | 備註說明 |

## Design Decisions

1. **訂購記錄獨立於進出貨記錄**：訂購記錄追蹤的是「計畫」和「訂單狀態」，進出貨記錄追蹤的是「實際庫存變動」。交貨完成後，使用者可以手動建立進貨記錄。

2. **專案關聯為選填**：物料可能尚未分配給特定專案，或是通用備品。

3. **存放庫位使用文字欄位**：各公司庫位命名規則不同，使用自由文字而非預設選項。
