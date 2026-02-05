# inventory-management Specification

## Purpose
物料管理功能（已遷移至 ERPNext）

> **DEPRECATED**: 此模組的功能已於 2026-02 遷移至 ERPNext。
> 使用 ERPNext 網頁介面（http://ct.erp）管理物料。

## Migration Notes

| 原 CTOS 功能 | ERPNext 對應 |
|-------------|-------------|
| 物料管理視窗 | ERPNext Item 介面 |
| 物料 CRUD | Item DocType |
| 進出貨記錄 | Stock Entry DocType |
| 庫存計算 | ERPNext 庫存報表或 get_stock_balance MCP 工具 |
| 訂購記錄 | Purchase Order DocType |

## Archived Requirements

以下需求已標記為 deprecated，保留作為歷史參考：

### Requirement: 物料管理視窗佈局 [DEPRECATED]
物料管理應用程式 SHALL 提供雙欄式介面佈局與標籤頁切換。

**Migration**: 使用 ERPNext 網頁介面（http://ct.erp）管理物料

---

### Requirement: 物料主檔 CRUD 操作 [DEPRECATED]
物料管理 SHALL 支援物料主檔的新增、讀取、更新、刪除操作。

**Migration**: 使用 ERPNext Item DocType

---

### Requirement: 進出貨記錄管理 [DEPRECATED]
物料管理 SHALL 支援記錄物料的進貨與出貨。

**Migration**: 使用 ERPNext Stock Entry DocType

---

### Requirement: 庫存計算 [DEPRECATED]
物料管理 SHALL 自動計算並顯示物料的目前庫存。

**Migration**: 使用 ERPNext 庫存報表或 get_stock_balance MCP 工具

---

### Requirement: 物料搜尋與過濾 [DEPRECATED]
物料管理 SHALL 支援搜尋與過濾物料列表。

**Migration**: 使用 ERPNext 物料列表搜尋功能

---

### Requirement: 物料管理 API [DEPRECATED]
後端 SHALL 提供 RESTful API 供前端操作物料管理。

**Migration**: 使用 ERPNext REST API 或 MCP 工具

---

### Requirement: 物料管理資料庫儲存 [DEPRECATED]
物料管理 SHALL 使用 PostgreSQL 資料庫儲存物料資料。

**Migration**: 資料已遷移至 ERPNext，原資料表標記 deprecated

---

### Requirement: 訂購記錄管理 [DEPRECATED]
物料管理 SHALL 支援記錄物料的訂購狀態。

**Migration**: 使用 ERPNext Purchase Order DocType
