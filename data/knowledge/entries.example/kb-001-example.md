---
id: kb-001
title: 知識庫格式說明
type: guide
category: technical
scope: global
owner: null
tags:
  projects: []
  roles: []
  topics:
  - 知識庫
  - 格式說明
  - 範例
  level: beginner
source:
  project: null
  path: null
  commit: null
related: []
attachments:
- type: image
  path: ../assets/images/kb-001-example-diagram.png
  size: 128.5KB
  description: 圖1 知識庫架構示意圖
- type: file
  path: nas://knowledge/attachments/kb-001/sample.pdf
  size: 1.2MB
  description: 附件1 參考文件
author: system
created_at: '2025-12-31'
updated_at: '2025-12-31'
---

# 知識庫格式說明

這是知識庫文件的格式範例，說明如何建立和管理知識庫內容。

## 檔案格式

每個知識條目是一個 Markdown 檔案，使用 YAML front matter 儲存元資料。

### 檔名規則

```
kb-{序號}-{標題}.md
```

例如：
- `kb-001-getting-started.md`
- `kb-002-api-reference.md`

## 文件結構

```markdown
---
id: kb-001
title: 文件標題
type: note|spec|guide
category: technical|process|tool|note
tags:
  projects: [專案名稱]
  roles: [適用角色]
  topics: [主題標籤]
  level: beginner|intermediate|advanced
attachments:
- type: image|file|video|document
  path: ../assets/images/kb-001-xxx.jpg
  size: 123.4KB
  description: 圖1 說明文字
---

# 標題

Markdown 內容...
```

## 欄位說明

| 欄位 | 說明 |
|------|------|
| id | 知識庫 ID，如 kb-001 |
| title | 文件標題 |
| type | 類型：note（筆記）、spec（規格）、guide（指南） |
| category | 分類：technical、process、tool、note |
| tags.projects | 關聯的專案名稱列表 |
| tags.roles | 適用角色列表 |
| tags.topics | 主題標籤列表 |
| tags.level | 難度層級 |
| attachments | 附件列表 |

## 附件管理

附件儲存位置：
- 本地圖片：`data/knowledge/assets/images/kb-{id}-{filename}`
- NAS 檔案：`nas://knowledge/attachments/kb-{id}/{filename}`

附件的 `description` 欄位用於描述附件內容，方便識別「圖1」「圖2」等：

```yaml
attachments:
- type: image
  path: ../assets/images/kb-002-abc123.jpg
  description: 圖1 系統架構圖
- type: image
  path: ../assets/images/kb-002-def456.jpg
  description: 圖2 流程示意圖
```

## 索引檔案

`data/knowledge/index.json` 記錄所有知識條目的元資料，系統會自動更新。
