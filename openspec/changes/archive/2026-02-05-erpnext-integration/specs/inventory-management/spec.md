## REMOVED Requirements

### Requirement: 物料管理視窗佈局
**Reason**: 物料管理功能遷移至 ERPNext，前端應用程式不再需要
**Migration**: 使用 ERPNext 網頁介面（http://ct.erp）管理物料

### Requirement: 物料主檔 CRUD 操作
**Reason**: 物料管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext Item DocType

### Requirement: 進出貨記錄管理
**Reason**: 物料管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext Stock Entry DocType

### Requirement: 庫存計算
**Reason**: 物料管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext 庫存報表或 get_stock_balance MCP 工具

### Requirement: 物料搜尋與過濾
**Reason**: 前端應用程式移除
**Migration**: 使用 ERPNext 物料列表搜尋功能

### Requirement: 物料管理 API
**Reason**: 前端應用程式移除，API 不再需要
**Migration**: 使用 ERPNext REST API 或 MCP 工具

### Requirement: 物料管理資料庫儲存
**Reason**: 資料遷移至 ERPNext
**Migration**: 原資料表標記 deprecated，不再使用

### Requirement: 訂購記錄管理
**Reason**: 物料管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext Purchase Order DocType
