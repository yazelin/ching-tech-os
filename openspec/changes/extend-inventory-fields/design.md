# 技術設計：擴充物料主檔欄位

## Context

物料管理模組目前僅支援基本資訊，需要擴充以支援完整的採購流程追蹤。此變更影響資料庫、後端 API、MCP 工具和前端 UI。

### 現有架構
- 資料庫：`inventory_items`（物料主檔）、`inventory_transactions`（進出貨記錄）
- 後端：FastAPI + asyncpg，Pydantic 模型
- 前端：原生 JavaScript 模組化架構
- AI：MCP 工具透過 Line Bot 和 CTOS Web 使用

## Goals / Non-Goals

### Goals
- 支援物料型號、存放庫位的記錄
- 支援完整的訂購流程追蹤（下單→交貨）
- MCP 工具支援訂購相關操作
- 前端 UI 支援管理訂購記錄

### Non-Goals
- 不實作自動化訂購與 ERP 整合
- 不實作庫位管理（庫位規劃、移動記錄）
- 不實作訂購審核流程

## Decisions

### 1. 資料庫設計

**新增 inventory_orders 表**

```sql
CREATE TABLE inventory_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
    order_quantity NUMERIC(15, 3) NOT NULL,
    order_date DATE,
    expected_delivery_date DATE,
    actual_delivery_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending/ordered/delivered/cancelled
    vendor VARCHAR(200),
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);
```

**inventory_items 表新增欄位**

```sql
ALTER TABLE inventory_items
    ADD COLUMN model VARCHAR(200),
    ADD COLUMN storage_location VARCHAR(200);
```

### 2. 訂購狀態流程

```
pending（待下單）→ ordered（已下單）→ delivered（已交貨）
                                    ↓
                               cancelled（已取消）
```

- `pending`: 計畫訂購但尚未下單
- `ordered`: 已下單等待交貨
- `delivered`: 已交貨（使用者可手動建立進貨記錄）
- `cancelled`: 訂單已取消

### 3. 訂購與進貨的關係

訂購記錄和進出貨記錄保持獨立：
- 訂購記錄追蹤「訂單狀態」
- 進出貨記錄追蹤「實際庫存變動」
- 交貨後，使用者自行決定是否建立進貨記錄

**理由**：
1. 訂購可能部分交貨
2. 進貨可能不來自訂購（如贈品、庫存轉移）
3. 簡化系統複雜度

### 4. API 端點設計

```
GET    /api/inventory/items/{id}/orders     # 取得物料的訂購記錄
POST   /api/inventory/items/{id}/orders     # 建立訂購記錄
PUT    /api/inventory/orders/{order_id}     # 更新訂購記錄
DELETE /api/inventory/orders/{order_id}     # 刪除訂購記錄
```

### 5. MCP 工具設計

新增工具：
- `add_inventory_order(item_id, order_quantity, ...)` - 建立訂購記錄
- `update_inventory_order(order_id, ...)` - 更新訂購記錄
- `get_inventory_orders(item_id, status, ...)` - 查詢訂購記錄

修改工具：
- `add_inventory_item` - 新增 model、storage_location 參數
- `query_inventory` - 回傳新欄位（型號、庫位）

### 6. 前端 UI 設計

物料詳情頁新增「訂購記錄」標籤頁，布局與「進出貨記錄」一致：
- 列表顯示：訂購數量、下單日期、預計交貨日、狀態、廠商、關聯專案
- 支援新增、編輯、刪除操作
- 狀態使用顏色標示：pending=灰色、ordered=藍色、delivered=綠色、cancelled=紅色

## Risks / Trade-offs

| 風險 | 緩解措施 |
|------|----------|
| 訂購與進貨記錄不同步 | UI 提示使用者交貨後建立進貨記錄 |
| 欄位過多導致 UI 複雜 | 新欄位為選填，不影響現有流程 |

## Migration Plan

1. 建立 Alembic migration 新增欄位和表格
2. 現有資料不受影響（新欄位皆為選填/有預設值）
3. 無需資料遷移

## Open Questions

（無）
