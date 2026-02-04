## REMOVED Requirements

### Requirement: 專案管理視窗佈局
**Reason**: 專案管理功能遷移至 ERPNext，前端應用程式不再需要
**Migration**: 使用 ERPNext 網頁介面（http://ct.erp）管理專案

### Requirement: 專案 CRUD 操作
**Reason**: 專案管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext Project DocType

### Requirement: 專案成員管理
**Reason**: 專案管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext Project.users 子表

### Requirement: 會議記錄管理
**Reason**: 專案管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext Event DocType

### Requirement: 專案附件管理
**Reason**: 專案管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext File DocType

### Requirement: PDF 預覽功能
**Reason**: 專案管理應用程式移除
**Migration**: ERPNext 內建檔案預覽

### Requirement: 專案連結管理
**Reason**: 專案管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext Comment DocType

### Requirement: 專案管理 API
**Reason**: 前端應用程式移除，API 不再需要
**Migration**: 使用 ERPNext REST API 或 MCP 工具

### Requirement: 資料庫儲存
**Reason**: 資料遷移至 ERPNext
**Migration**: 原資料表標記 deprecated，不再使用

### Requirement: 專案里程碑管理
**Reason**: 專案管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext Task DocType

### Requirement: 專案發包/交貨管理
**Reason**: 專案管理功能遷移至 ERPNext
**Migration**: 使用 ERPNext Purchase Order DocType
