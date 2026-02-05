# project-management Specification

## Purpose
專案管理功能（已遷移至 ERPNext）

> **DEPRECATED**: 此模組的功能已於 2026-02 遷移至 ERPNext。
> 使用 ERPNext 網頁介面（http://ct.erp）管理專案。

## Migration Notes

| 原 CTOS 功能 | ERPNext 對應 |
|-------------|-------------|
| 專案管理視窗 | ERPNext Project 介面 |
| 專案 CRUD | ERPNext Project DocType |
| 專案成員 | Project.users 子表 |
| 會議記錄 | Event DocType |
| 專案附件 | File DocType |
| 專案連結 | Comment DocType |
| 里程碑 | Task DocType |
| 發包/交貨 | Purchase Order DocType |

## Archived Requirements

以下需求已標記為 deprecated，保留作為歷史參考：

### Requirement: 專案管理視窗佈局 [DEPRECATED]
專案管理應用程式 SHALL 提供雙欄式介面佈局與標籤頁切換。

**Migration**: 使用 ERPNext 網頁介面（http://ct.erp）管理專案

---

### Requirement: 專案 CRUD 操作 [DEPRECATED]
專案管理 SHALL 支援專案的新增、讀取、更新、刪除操作。

**Migration**: 使用 ERPNext Project DocType

---

### Requirement: 專案成員管理 [DEPRECATED]
專案管理 SHALL 支援管理專案相關成員與聯絡人。

**Migration**: 使用 ERPNext Project.users 子表

---

### Requirement: 會議記錄管理 [DEPRECATED]
專案管理 SHALL 支援記錄與管理專案會議。

**Migration**: 使用 ERPNext Event DocType

---

### Requirement: 專案附件管理 [DEPRECATED]
專案管理 SHALL 支援上傳與管理專案相關檔案。

**Migration**: 使用 ERPNext File DocType

---

### Requirement: 專案連結管理 [DEPRECATED]
專案管理 SHALL 支援管理專案相關連結。

**Migration**: 使用 ERPNext Comment DocType

---

### Requirement: 專案里程碑管理 [DEPRECATED]
專案管理 SHALL 支援管理專案關鍵里程碑。

**Migration**: 使用 ERPNext Task DocType

---

### Requirement: 專案發包/交貨管理 [DEPRECATED]
專案管理 SHALL 支援管理專案的發包與交貨期程。

**Migration**: 使用 ERPNext Purchase Order DocType

---

### Requirement: 專案管理 API [DEPRECATED]
後端 SHALL 提供 RESTful API 供前端操作專案管理。

**Migration**: 使用 ERPNext REST API 或 MCP 工具

---

### Requirement: 資料庫儲存 [DEPRECATED]
專案管理 SHALL 使用 PostgreSQL 資料庫儲存專案結構化資料。

**Migration**: 資料已遷移至 ERPNext，原資料表標記 deprecated
