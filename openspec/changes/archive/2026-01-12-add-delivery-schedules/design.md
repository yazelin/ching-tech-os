# Design: add-delivery-schedules

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     專案管理 App                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  [概覽] [成員] [會議] [附件] [連結] [發包/交貨]               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     發包/交貨列表                             │ │
│  │  ┌───────────────────────────────────────────────────────┐   │ │
│  │  │ 廠商    │ 料件    │ 數量  │ 發包日 │ 交貨日 │ 狀態   │   │ │
│  │  ├───────────────────────────────────────────────────────┤   │ │
│  │  │ A 公司  │ 水切爐  │ 2 台  │ 01/10 │ 02/15 │ 已發包 │   │ │
│  │  │ B 公司  │ 控制箱  │ 5 組  │ 01/12 │ 01/30 │ 已到貨 │   │ │
│  │  └───────────────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema

### 新增資料表：project_delivery_schedules

```sql
CREATE TABLE project_delivery_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    vendor VARCHAR(200) NOT NULL,           -- 廠商名稱
    item VARCHAR(500) NOT NULL,             -- 料件名稱
    quantity VARCHAR(100),                   -- 數量（含單位，如「2 台」）
    order_date DATE,                         -- 發包日期
    expected_delivery_date DATE,             -- 預計交貨日期
    actual_delivery_date DATE,               -- 實際到貨日期（可選）
    status VARCHAR(50) DEFAULT 'pending',    -- 狀態
    notes TEXT,                              -- 備註
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100)
);

CREATE INDEX idx_delivery_schedules_project_id ON project_delivery_schedules(project_id);
CREATE INDEX idx_delivery_schedules_status ON project_delivery_schedules(status);
CREATE INDEX idx_delivery_schedules_vendor ON project_delivery_schedules(vendor);
```

### 狀態值
- `pending`：待發包
- `ordered`：已發包
- `delivered`：已到貨
- `completed`：已完成

## API Design

### RESTful Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/{id}/deliveries` | 取得專案發包列表 |
| POST | `/api/projects/{id}/deliveries` | 新增發包記錄 |
| PUT | `/api/projects/{id}/deliveries/{did}` | 更新發包記錄 |
| DELETE | `/api/projects/{id}/deliveries/{did}` | 刪除發包記錄 |

### Request/Response Models

```python
class DeliveryScheduleCreate(BaseModel):
    vendor: str
    item: str
    quantity: str | None = None
    order_date: date | None = None
    expected_delivery_date: date | None = None
    status: str = "pending"
    notes: str | None = None

class DeliveryScheduleUpdate(BaseModel):
    vendor: str | None = None
    item: str | None = None
    quantity: str | None = None
    order_date: date | None = None
    expected_delivery_date: date | None = None
    actual_delivery_date: date | None = None
    status: str | None = None
    notes: str | None = None
```

## MCP Tools Design

### 1. add_delivery_schedule
新增發包記錄。

```python
@mcp.tool()
async def add_delivery_schedule(
    project_id: str,
    vendor: str,
    item: str,
    quantity: str | None = None,
    order_date: str | None = None,        # YYYY-MM-DD
    expected_delivery_date: str | None = None,
    status: str = "pending",
    notes: str | None = None,
) -> str:
    """新增專案發包/交貨記錄"""
```

### 2. update_delivery_schedule
更新發包記錄（支援模糊匹配廠商+料件）。

```python
@mcp.tool()
async def update_delivery_schedule(
    project_id: str,
    delivery_id: str | None = None,       # 直接指定 ID
    vendor: str | None = None,            # 或用廠商+料件匹配
    item: str | None = None,
    # 要更新的欄位
    new_status: str | None = None,
    actual_delivery_date: str | None = None,
    expected_delivery_date: str | None = None,
    new_notes: str | None = None,
) -> str:
    """更新專案發包/交貨記錄"""
```

### 3. get_delivery_schedules
查詢專案發包列表。

```python
@mcp.tool()
async def get_delivery_schedules(
    project_id: str,
    status: str | None = None,            # 狀態過濾
    vendor: str | None = None,            # 廠商過濾
    limit: int = 20,
) -> str:
    """取得專案的發包/交貨記錄"""
```

## Frontend Design

### 標籤頁結構
在 `project-management.js` 中新增 `deliveries` 標籤頁：

```javascript
const TABS = [
  { id: 'overview', label: '概覽', icon: 'view-dashboard' },
  { id: 'members', label: '成員', icon: 'account-group' },
  { id: 'meetings', label: '會議', icon: 'calendar-text' },
  { id: 'attachments', label: '附件', icon: 'attachment' },
  { id: 'links', label: '連結', icon: 'link' },
  { id: 'deliveries', label: '發包/交貨', icon: 'truck-delivery' },
];
```

### 列表顯示
表格形式顯示，欄位：
- 廠商
- 料件
- 數量
- 發包日
- 預計交貨
- 實際到貨
- 狀態（帶顏色標籤）
- 操作（編輯/刪除）

### 狀態顏色
- `pending`（待發包）：灰色
- `ordered`（已發包）：藍色
- `delivered`（已到貨）：橙色
- `completed`（已完成）：綠色

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `backend/migrations/versions/025_create_delivery_schedules.py` | 新增 | 資料庫 migration |
| `backend/src/ching_tech_os/models/project.py` | 修改 | 新增 Pydantic models |
| `backend/src/ching_tech_os/api/projects.py` | 修改 | 新增 API endpoints |
| `backend/src/ching_tech_os/services/mcp_server.py` | 修改 | 新增 MCP 工具 |
| `backend/src/ching_tech_os/services/linebot_agents.py` | 修改 | 更新 prompt |
| `backend/migrations/versions/026_update_linebot_prompts_delivery.py` | 新增 | 更新 prompt migration |
| `frontend/js/project-management.js` | 修改 | 新增發包/交貨標籤頁 |
| `frontend/css/project-management.css` | 修改 | 新增樣式 |
