# Design: 專案管理應用

## Context

公司需要管理多個專案的相關資料，包括：
- 專案基本資訊（名稱、狀態、時程）
- 專案知識與參考資料
- 技術文件（CAD 圖、PDF 說明書）
- 會議記錄
- 相關人員聯絡資訊
- NAS 檔案連結

目前這些資料分散在不同地方，需要整合到單一介面。

## Goals / Non-Goals

### Goals
- 提供統一的專案資料管理介面
- 支援專案成員與聯絡人管理
- 支援會議記錄（Markdown 格式）
- 支援多種檔案類型預覽（圖片、PDF）
- 支援大型檔案 NAS 儲存

### Non-Goals
- 不做甘特圖或專案排程功能
- 不做專案工時追蹤
- 不做即時協作編輯
- 不整合第三方專案管理工具

## Decisions

### 資料儲存：PostgreSQL + NAS

選擇使用 PostgreSQL 儲存專案結構化資料，而非知識庫使用的檔案系統方式。

**原因**：
- 專案資料關聯性強（專案-成員-會議-附件）
- 需要高效查詢和過濾
- 支援事務操作確保資料一致性

**附件儲存策略**（同知識庫）：
- 小於 1MB：存本機 `data/projects/attachments/`
- 大於等於 1MB：存 NAS

### UI 架構：雙欄式 + 標籤頁

```
+------------------------------------------+
| 工具列 [搜尋] [新增專案]                  |
+----------+-------------------------------+
|          |  [概覽][成員][會議][附件][連結] |
| 專案列表  |                               |
|          |  專案詳情內容                   |
|  - 專案A |                               |
|  - 專案B |                               |
|          |                               |
+----------+-------------------------------+
```

### PDF 預覽：PDF.js

使用 Mozilla 的 pdf.js 函式庫，透過 iframe 或 canvas 渲染 PDF。

```javascript
// 載入 pdf.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = '/js/lib/pdf.worker.min.js';

// 渲染 PDF
const pdf = await pdfjsLib.getDocument(url).promise;
const page = await pdf.getPage(1);
// ...
```

### 資料表結構

```sql
-- 專案主表
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',  -- active, completed, on_hold, cancelled
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- 專案成員/聯絡人
CREATE TABLE project_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(100),           -- PM, 工程師, 客戶等
    company VARCHAR(200),
    email VARCHAR(200),
    phone VARCHAR(50),
    notes TEXT,
    is_internal BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 會議記錄
CREATE TABLE project_meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    meeting_date TIMESTAMP NOT NULL,
    location VARCHAR(200),
    attendees TEXT[],            -- 參與人員名單
    content TEXT,                -- Markdown 內容
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- 專案附件
CREATE TABLE project_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(50),       -- image, pdf, cad, document, other
    file_size BIGINT,
    storage_path VARCHAR(1000),  -- 本機路徑或 nas://...
    description TEXT,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    uploaded_by VARCHAR(100)
);

-- 專案連結（類型由 URL 格式自動判斷）
CREATE TABLE project_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    url VARCHAR(2000) NOT NULL,  -- NAS 路徑 (/) 或 HTTP URL (https://)
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
-- 連結類型自動判斷邏輯：
--   以 / 或 nas:// 開頭 → NAS 連結 → 開啟檔案管理器
--   以 http:// 或 https:// 開頭 → 外部連結 → 開新視窗
```

## Risks / Trade-offs

### 風險：PDF.js 檔案大小
- pdf.js 完整版約 2MB
- **緩解**：使用 CDN 或按需載入

### 風險：NAS 連線不穩定
- NAS 離線時無法存取大型附件
- **緩解**：顯示友善錯誤訊息，本機快取預覽縮圖

### Trade-off：PostgreSQL vs 檔案系統
- PostgreSQL 需要維護資料庫
- 但提供更好的查詢效能和資料完整性

## API 設計

```
# 專案 CRUD
GET    /api/projects                    # 列表
POST   /api/projects                    # 新增
GET    /api/projects/{id}               # 詳情
PUT    /api/projects/{id}               # 更新
DELETE /api/projects/{id}               # 刪除

# 專案成員
GET    /api/projects/{id}/members       # 成員列表
POST   /api/projects/{id}/members       # 新增成員
PUT    /api/projects/{id}/members/{mid} # 更新成員
DELETE /api/projects/{id}/members/{mid} # 刪除成員

# 會議記錄
GET    /api/projects/{id}/meetings      # 會議列表
POST   /api/projects/{id}/meetings      # 新增會議
GET    /api/projects/{id}/meetings/{mid}# 會議詳情
PUT    /api/projects/{id}/meetings/{mid}# 更新會議
DELETE /api/projects/{id}/meetings/{mid}# 刪除會議

# 附件
GET    /api/projects/{id}/attachments   # 附件列表
POST   /api/projects/{id}/attachments   # 上傳附件
GET    /api/projects/attachments/{path} # 下載/預覽附件
DELETE /api/projects/{id}/attachments/{aid} # 刪除附件

# 連結
GET    /api/projects/{id}/links         # 連結列表
POST   /api/projects/{id}/links         # 新增連結
PUT    /api/projects/{id}/links/{lid}   # 更新連結
DELETE /api/projects/{id}/links/{lid}   # 刪除連結
```

## Migration Plan

1. 執行資料庫 migration 建立新資料表
2. 部署後端 API
3. 部署前端模組
4. 測試完整流程

## Open Questions

- PDF.js 是否需要支援 PDF 編輯/註解？（暫定：僅預覽）
- CAD 圖檔是否需要線上預覽？（暫定：提供下載，使用原生應用開啟）
