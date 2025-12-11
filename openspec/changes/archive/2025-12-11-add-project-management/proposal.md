# Change: 新增專案管理應用

## Why

公司需要一個整合式專案管理工具，讓專案經理 (PM) 能夠集中管理專案相關資料，包括專案知識庫、技術文件 (CAD/PDF)、會議記錄、聯絡人資訊、以及 NAS 檔案連結。目前這些資訊分散在不同系統中，造成管理困難。

## What Changes

- 新增專案管理應用程式視窗 (project-management)
- 建立專案資料模型與資料庫結構 (PostgreSQL)
- 實作專案 CRUD API
- 實作專案成員與聯絡人管理
- 實作會議記錄功能
- 實作檔案附件管理（支援 PDF、CAD、圖片等）
- 整合 PDF 預覽功能（知識庫亦可使用）
- 支援 NAS 連結管理

## Impact

- Affected specs: 新增 `project-management` spec
- Affected code:
  - `frontend/js/project-management.js` - 新增
  - `frontend/css/project-management.css` - 新增
  - `frontend/index.html` - 新增模組載入
  - `frontend/js/desktop.js` - 新增 app case
  - `backend/src/ching_tech_os/routes/project.py` - 新增 API routes
  - `backend/src/ching_tech_os/models/project.py` - 新增資料模型
  - `backend/src/ching_tech_os/services/project.py` - 新增業務邏輯
  - `docker/init.sql` - 新增專案相關資料表
