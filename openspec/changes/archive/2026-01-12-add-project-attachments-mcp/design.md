# Design: 專案附件與連結 MCP 工具

## 架構概要

```
Line 用戶 ──發送檔案──► Line Bot ──► NAS 儲存
                                        │
                                        ▼
AI 助手 ──get_message_attachments──► 查詢 NAS 路徑
    │
    └──add_project_attachment──► project_attachments 表
                                     │
                                     ▼
                               儲存引用路徑 (nas://...)
```

## 現有資料結構

### project_attachments 表
```sql
id           UUID PRIMARY KEY
project_id   UUID REFERENCES projects(id)
filename     VARCHAR(500)
file_type    VARCHAR(50)
file_size    BIGINT
storage_path VARCHAR(1000)  -- 格式：nas://projects/... 或 {project_id}/{filename}
description  TEXT
uploaded_at  TIMESTAMP
uploaded_by  VARCHAR(100)
```

### project_links 表
```sql
id          UUID PRIMARY KEY
project_id  UUID REFERENCES projects(id)
title       VARCHAR(200)
url         VARCHAR(2000)
description TEXT
created_at  TIMESTAMP
```

## MCP 工具設計

### 連結管理

#### add_project_link
```python
async def add_project_link(
    project_id: str,     # 專案 UUID
    title: str,          # 連結標題（必填）
    url: str,            # URL（必填）
    description: str | None = None,  # 描述
) -> str
```

#### update_project_link
```python
async def update_project_link(
    link_id: str,              # 連結 UUID
    project_id: str | None = None,  # 專案 UUID（可選，用於驗證）
    title: str | None = None,       # 新標題
    url: str | None = None,         # 新 URL
    description: str | None = None, # 新描述
) -> str
```

#### delete_project_link
```python
async def delete_project_link(
    link_id: str,              # 連結 UUID
    project_id: str | None = None,  # 專案 UUID（可選，用於驗證）
) -> str
```

#### get_project_links
```python
async def get_project_links(
    project_id: str,  # 專案 UUID
    limit: int = 20,  # 最大數量
) -> str
```

### 附件管理

#### add_project_attachment
```python
async def add_project_attachment(
    project_id: str,         # 專案 UUID
    nas_path: str,           # NAS 檔案路徑（從 get_message_attachments 或 search_nas_files 取得）
    description: str | None = None,  # 描述
) -> str
```

實作細節：
- 驗證 NAS 路徑存在
- 從路徑提取 filename
- 取得 file_size 和 file_type
- 儲存為 `nas://{相對路徑}` 格式

#### update_project_attachment
```python
async def update_project_attachment(
    attachment_id: str,            # 附件 UUID
    project_id: str | None = None, # 專案 UUID（可選，用於驗證）
    description: str | None = None, # 新描述
) -> str
```

#### delete_project_attachment
```python
async def delete_project_attachment(
    attachment_id: str,            # 附件 UUID
    project_id: str | None = None, # 專案 UUID（可選，用於驗證）
) -> str
```

#### get_project_attachments
```python
async def get_project_attachments(
    project_id: str,  # 專案 UUID
    limit: int = 20,  # 最大數量
) -> str
```

## 使用情境

### 情境 1：用戶在 Line 發送圖片並要求加入專案
```
用戶: [發送圖片] 把這張圖加到亦達專案的附件

AI 流程:
1. get_message_attachments(line_user_id=..., days=1) → 取得 NAS 路徑
2. query_project(keyword="亦達") → 取得專案 ID
3. add_project_attachment(project_id=..., nas_path=..., description="用戶上傳")
```

### 情境 2：用戶要求添加 NAS 檔案到專案
```
用戶: 把 NAS 上的 layout.pdf 加到專案附件

AI 流程:
1. search_nas_files(keywords="layout", file_types="pdf")
2. add_project_attachment(project_id=..., nas_path=...)
```

### 情境 3：用戶要求添加連結
```
用戶: 幫我在專案加一個連結，標題是「規格書」，網址是 https://...

AI 流程:
1. add_project_link(project_id=..., title="規格書", url="https://...")
```

## 權限控制

- 所有操作僅限專案成員
- 透過 ctos_user_id 驗證用戶權限

## 分享連結支援

### create_share_link 擴充

支援 `project_attachment` 資源類型：
```python
create_share_link(
    resource_type="project_attachment",
    resource_id=attachment_uuid,
    expires_in="24h"  # 1h, 24h, 7d, null（永久）
)
```

### 路徑解析邏輯

專案附件的 `storage_path` 有多種格式，需要根據格式選擇對應的檔案服務：

```
storage_path 格式                      →  檔案服務
─────────────────────────────────────────────────────
nas://projects/{path}                  →  project_file_service
nas://linebot/files/{path}             →  linebot_file_service
{project_id}/{filename} (舊格式)        →  project_file_service
```

### 公開頁面渲染

`project_attachment` 類型在公開頁面的顯示與 `nas_file` 相同：
- 顯示檔案名稱、大小、類型
- 提供下載按鈕
- 圖片類型可預覽

## 使用情境（分享連結）

### 情境 4：為專案附件建立分享連結
```
用戶: 幫我產生這個附件的分享連結

AI 流程:
1. get_project_attachments(project_id=...) → 取得附件列表
2. create_share_link(resource_type="project_attachment", resource_id=attachment_id)
3. 回傳分享連結給用戶
```
