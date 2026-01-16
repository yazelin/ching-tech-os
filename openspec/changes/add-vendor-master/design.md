# Design: 廠商主檔與關聯整合

## Context
- 現有發包功能（`project_delivery_schedules`）使用純文字儲存廠商和料件
- 現有物料管理（`inventory_items`）也使用純文字儲存預設廠商
- 需要與外部 ERP 系統的廠商編號對照
- 需要避免同一廠商有多種寫法造成的資料混亂

## Goals
- 建立統一的廠商主檔
- 發包和物料管理可關聯到廠商主檔
- 發包的料件可關聯到物料主檔
- 向後相容現有資料
- 支援 ERP 廠商編號對照

## Non-Goals
- 完整的 ERP 整合（如自動同步）
- 強制所有記錄必須關聯（保留彈性）

## Decisions

### 1. 廠商主檔資料表結構
```sql
CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    erp_code VARCHAR(50) UNIQUE,        -- ERP 系統廠商編號（可為空）
    name VARCHAR(200) NOT NULL,         -- 廠商名稱
    short_name VARCHAR(100),            -- 簡稱
    contact_person VARCHAR(100),        -- 聯絡人
    phone VARCHAR(50),                  -- 電話
    fax VARCHAR(50),                    -- 傳真
    email VARCHAR(200),                 -- Email
    address TEXT,                       -- 地址
    tax_id VARCHAR(20),                 -- 統一編號
    payment_terms VARCHAR(200),         -- 付款條件
    notes TEXT,                         -- 備註
    is_active BOOLEAN DEFAULT true,     -- 是否啟用
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100)
);
```

**Rationale**:
- `erp_code` 可為空，因為不是所有廠商都在 ERP 中
- `erp_code` 設為 UNIQUE，確保對照的唯一性
- 包含常見的廠商聯絡資訊欄位

### 2. 發包記錄修改
```sql
ALTER TABLE project_delivery_schedules
ADD COLUMN vendor_id UUID REFERENCES vendors(id) ON DELETE SET NULL,
ADD COLUMN item_id UUID REFERENCES inventory_items(id) ON DELETE SET NULL;
```

**Rationale**:
- 使用 `ON DELETE SET NULL` 而非 `CASCADE`，避免誤刪廠商/物料時連帶刪除發包記錄
- 保留原有 `vendor` 和 `item` 文字欄位，確保向後相容

### 3. 物料主檔修改
```sql
ALTER TABLE inventory_items
ADD COLUMN default_vendor_id UUID REFERENCES vendors(id) ON DELETE SET NULL;
```

**Rationale**:
- 物料可以有預設廠商，但廠商被刪除時不應影響物料記錄

### 4. UI 互動設計

#### 發包表單
- 廠商欄位改為 combo box（可選擇或手動輸入）
- 選擇已存在的廠商時，自動填入 `vendor` 文字欄位和設定 `vendor_id`
- 手動輸入時，只設定 `vendor` 文字欄位，`vendor_id` 為 null
- 料件欄位同理

#### 廠商管理
- 在「設定」或獨立應用中提供廠商管理介面
- 列表顯示：ERP 編號、名稱、聯絡人、電話、狀態
- 支援搜尋、新增、編輯、停用（非刪除）

### 5. API 設計

```
GET    /api/vendors              # 廠商列表（支援搜尋）
POST   /api/vendors              # 新增廠商
GET    /api/vendors/{id}         # 廠商詳情
PUT    /api/vendors/{id}         # 更新廠商
DELETE /api/vendors/{id}         # 停用廠商（軟刪除）
```

### 6. MCP 工具設計

```python
# 查詢廠商
query_vendors(keyword: str, erp_code: str = None) -> list

# 新增廠商
add_vendor(name: str, erp_code: str = None, ...) -> dict

# 更新廠商
update_vendor(vendor_id: str, ...) -> dict
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| 現有資料無法自動關聯 | 提供批次關聯工具或手動逐筆修正 |
| UI 複雜度增加 | combo box 設計兼顧彈性與便利性 |
| 廠商重複建立 | 名稱唯一性檢查 + 搜尋建議 |

## Migration Plan

1. 建立 `vendors` 資料表
2. 新增 `vendor_id`、`item_id` 欄位到 `project_delivery_schedules`
3. 新增 `default_vendor_id` 欄位到 `inventory_items`
4. 部署後端 API 和 MCP 工具
5. 部署前端 UI
6. （可選）執行資料遷移腳本，將現有文字欄位匹配到廠商主檔

## Decisions Made

1. **廠商管理 UI 位置**：選項 B - 獨立的「廠商管理」應用
   - 在桌面上新增「廠商管理」應用程式圖示
   - 與專案管理、知識庫等應用並列

## Open Questions (Deferred)

1. ~~廠商管理 UI 要放在哪裡？~~ → 已決定：獨立應用

2. 是否需要廠商分類功能？（如：加工廠、材料商、設備商）→ 之後再議

3. 是否需要支援批次匯入廠商資料？（從 Excel/CSV）→ 之後再議
