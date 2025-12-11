# Change: 新增知識庫應用程式（第一階段）

## Why

ChingTech OS 需要一個企業級知識庫系統，以支援：
- **多專案管理**：RosAGV、ChingTech-OS、Jaba、Jaba-Line-Bot、Fish-CV 等多個專案的知識集中管理
- **跨角色使用**：工程師、PM、管理層等不同角色皆可使用
- **通用知識沉澱**：公司規範、技術標準、SOP 等通用知識統一管理
- **完整追蹤**：知識來源、關聯、版本歷史完整記錄

第一階段專注於 UI 介面、檔案儲存，並整理現有專案知識作為初始內容。

## What Changes

### 前端
- 新增知識庫應用程式視窗
  - 上方：搜尋框 + 標籤過濾（專案、類型、角色、主題）
  - 左側：搜尋結果列表
  - 右側：知識內容檢視/編輯區
- 支援 Markdown 渲染與圖片顯示
- 支援知識 CRUD 操作
- 支援標籤管理
- **支援 Git 版本歷史檢視**
- **支援附件顯示與上傳**
  - 顯示附件列表（類型、大小、儲存位置）
  - 支援附件下載/預覽
  - 支援拖放或選擇檔案上傳

### 後端
- 新增知識庫 API 端點
  - `GET /api/knowledge` - 搜尋/列表
  - `GET /api/knowledge/{id}` - 取得單一知識
  - `POST /api/knowledge` - 新增知識
  - `PUT /api/knowledge/{id}` - 更新知識
  - `DELETE /api/knowledge/{id}` - 刪除知識
  - `GET /api/knowledge/tags` - 取得所有標籤
  - `POST /api/knowledge/rebuild-index` - 重建索引
  - **`GET /api/knowledge/{id}/history` - 取得版本歷史**
  - **`GET /api/knowledge/{id}/version/{commit}` - 取得特定版本**
  - **`POST /api/knowledge/{id}/attachments` - 上傳附件**
  - **`DELETE /api/knowledge/{id}/attachments/{idx}` - 刪除附件**
  - **`GET /api/knowledge/attachments/{path}` - 代理 NAS 附件**
- 使用 ripgrep (rg) 進行全文搜尋
- 維護 `index.json` 作為標籤索引

### 知識儲存架構

採用**扁平化 + 標籤系統**（詳見 design.md）：

```
# Git 追蹤（本機）
data/knowledge/
├── entries/                    # 所有知識條目
│   ├── kb-001-xxx.md
│   ├── kb-002-xxx.md
│   └── ...
├── assets/                     # 小型附件（< 1MB）
│   └── images/
└── index.json                  # 知識索引

# NAS 儲存（大型附件，不進 Git）
//192.168.11.50/擎添開發/ching-tech-os/knowledge/
├── attachments/               # 大型附件（≥ 1MB）
│   ├── kb-001/
│   └── kb-002/
└── exports/                   # 備份
```

### 初始知識整理

本提案將從以下專案整理知識作為知識庫初始內容：

| 專案 | 路徑 | 知識來源 |
|------|------|----------|
| RosAGV | `~/RosAGV` | `docs-ai/` 三層架構文件 |
| ChingTech-OS | `~/SDD/ching-tech-os` | 專案文件、設計文件 |
| Jaba | `~/SDD/jaba` | 專案文件 |
| Jaba-Line-Bot | `~/SDD/jaba-line-bot` | LINE Bot 相關知識 |
| Fish-CV | `~/SDD/fish-cv` | 電腦視覺相關知識 |

### 知識檔案格式

每個知識使用 YAML Front Matter 儲存完整元資料：

```yaml
---
id: kb-002
title: 知識標題
type: knowledge
category: technical
tags:
  projects: [rosagv]
  roles: [engineer]
  topics: [agv, vehicle]
  level: intermediate
source:
  project: rosagv
  path: ~/RosAGV/docs-ai/knowledge/xxx.md
  commit: abc1234
related: [kb-015, kb-023]
attachments:
  - type: video
    path: nas://knowledge/attachments/kb-002/demo.mp4
    size: 25MB
author: ct                      # 可為 ai:knowledge-agent
created_at: 2024-12-01
updated_at: 2024-12-01
---

（Markdown 內容）
```

### 知識命名規則

- **ID**：`kb-{序號}`，由系統自動分配
- **Slug**：由建立者（人類或 AI Agent）決定，系統確保唯一性
- **檔名**：`kb-{序號}-{slug}.md`

## Out of Scope（本提案不包含）

- **AI Agents 系統架構**：MCP server/client、LangChain/LangGraph 整合將另開提案
- **知識庫 AI Agent**：智慧查詢、自動整理將另開提案
- **權限控制**：第一階段知識全部公開
- **PostgreSQL 索引**：視檔案量後續評估

## Impact

- Affected specs:
  - 新增 `knowledge-base` spec
- Affected code:
  - `frontend/js/knowledge-base.js`（新增）
  - `frontend/css/knowledge-base.css`（新增）
  - `backend/src/ching_tech_os/api/knowledge.py`（新增）
  - `backend/src/ching_tech_os/services/knowledge.py`（新增）
  - `backend/src/ching_tech_os/models/knowledge.py`（新增）
  - `data/knowledge/`（新增知識儲存目錄）
  - `frontend/js/desktop.js`（修改：啟用知識庫圖示）
- Affected NAS:
  - 建立 `//192.168.11.50/擎添開發/ching-tech-os/knowledge/` 資料夾

## Dependencies

- 依賴現有 Window System（`ai-assistant-ui` spec）
- 依賴後端認證系統（`backend-auth` spec）
- 依賴 NAS 檔案存取（`backend-auth` spec）

## Future Considerations

本提案完成後，將另開提案處理：
1. **AI Agents 系統架構**：定義 MCP-like 架構、Agent 通訊協定
2. **知識庫 AI Agent**：整合上述架構，智慧查詢與自動整理
3. **知識庫 PostgreSQL 索引**：當檔案量過大時，建立資料庫元資料索引
