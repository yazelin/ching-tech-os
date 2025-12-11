# Design: 專案里程碑管理

## Context

工業專案通常有多個關鍵時間點需要追蹤：
- 設計完成
- 製造完成
- 交機（出貨）
- 場測（現場測試）
- 驗收
- 其他自訂里程碑

目前專案只有開始/結束日期，無法追蹤這些中間階段。

## Goals / Non-Goals

### Goals
- 支援專案里程碑的 CRUD 管理
- 追蹤預計日期與實際完成日期
- 自動判斷里程碑狀態（延遲、進行中等）
- 在概覽頁面以時間軸方式呈現

### Non-Goals
- 不做甘特圖功能
- 不做里程碑間的依賴關係
- 不做自動提醒/通知功能（可後續擴充）

## Decisions

### 資料表結構

```sql
CREATE TABLE project_milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    milestone_type VARCHAR(50),  -- 'design', 'manufacture', 'delivery', 'field_test', 'acceptance', 'custom'
    planned_date DATE,           -- 預計日期
    actual_date DATE,            -- 實際完成日期
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'delayed'
    notes TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_milestones_project ON project_milestones(project_id);
CREATE INDEX idx_milestones_status ON project_milestones(status);
```

### 狀態自動計算邏輯

```python
def calculate_milestone_status(milestone):
    today = date.today()

    if milestone.actual_date:
        return 'completed'
    elif milestone.planned_date and milestone.planned_date < today:
        return 'delayed'
    elif milestone.planned_date and milestone.planned_date <= today + timedelta(days=7):
        return 'in_progress'
    else:
        return 'pending'
```

### 預設里程碑類型

| 類型 | 中文名稱 | 圖示 |
|------|----------|------|
| design | 設計完成 | 📐 |
| manufacture | 製造完成 | 🏭 |
| delivery | 交機 | 🚚 |
| field_test | 場測 | 🔧 |
| acceptance | 驗收 | ✅ |
| custom | 自訂 | 📌 |

### UI 設計

在「概覽」標籤頁中，里程碑以垂直時間軸方式呈現：

```
里程碑
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
○ 設計完成      預計: 01/15  實際: 01/14  ✅ 已完成
│
○ 製造完成      預計: 02/28  實際: -      🔵 進行中
│
○ 交機          預計: 03/15  實際: -      ⚪ 待處理
│
○ 場測          預計: 03/30  實際: -      ⚪ 待處理
│
○ 驗收          預計: 04/15  實際: -      ⚪ 待處理

                              [+ 新增里程碑]
```

### API 設計

```
GET    /api/projects/{id}/milestones         # 里程碑列表
POST   /api/projects/{id}/milestones         # 新增里程碑
PUT    /api/projects/{id}/milestones/{mid}   # 更新里程碑
DELETE /api/projects/{id}/milestones/{mid}   # 刪除里程碑
```

## Risks / Trade-offs

### 風險：狀態自動計算
- 自動計算的狀態可能與實際情況不符
- **緩解**：允許用戶手動覆寫狀態

### Trade-off：里程碑類型
- 預設類型可能不夠彈性
- **緩解**：提供「自訂」類型，允許自由輸入名稱

## Open Questions

- 是否需要里程碑完成時自動發送通知？（暫定：Phase 2）
- 是否需要里程碑與會議記錄關聯？（暫定：Phase 2）
