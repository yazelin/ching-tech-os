# Change: 新增廠商主檔與關聯整合

## Why
目前發包功能和物料管理功能的廠商都是純文字欄位，無法：
1. 與現有 ERP 系統的廠商編號對照
2. 統一管理廠商資訊（聯絡人、電話、地址等）
3. 確保資料一致性（避免同一廠商有多種寫法）

另外，發包的料件（item）與物料主檔（inventory_items）目前也是獨立的，無法追蹤同一料件的發包與庫存狀況。

## What Changes
- **ADDED** 廠商主檔資料表（`vendors`）
  - 包含廠商編號（對應 ERP）、名稱、聯絡人、電話、地址、備註等
  - 廠商編號為唯一索引，方便與 ERP 對照
- **MODIFIED** 發包記錄（`project_delivery_schedules`）
  - 新增 `vendor_id` 外鍵關聯到 `vendors`
  - 保留 `vendor` 文字欄位作為備援/快速輸入
  - 新增 `item_id` 外鍵，可選擇性關聯到 `inventory_items`
  - 保留 `item` 文字欄位作為備援/快速輸入
- **MODIFIED** 物料主檔（`inventory_items`）
  - `default_vendor` 改為可選擇性關聯到 `vendors`（新增 `default_vendor_id`）
  - 保留 `default_vendor` 文字欄位作為備援
- **ADDED** 廠商管理 UI（前端）
- **ADDED** 廠商管理 API（後端）
- **ADDED** 廠商相關 MCP 工具（AI 可操作）

## Impact
- Affected specs: `project-management`, `mcp-tools`
- Affected code:
  - `backend/migrations/versions/` - 新增 migration
  - `backend/services/mcp_server.py` - 新增廠商工具
  - `backend/api/` - 新增廠商 API
  - `frontend/js/` - 新增廠商管理 UI、修改發包 UI

## 設計考量

### 向後相容性
為確保現有資料不受影響：
1. `vendor` 和 `item` 文字欄位保留，新的外鍵欄位為可選
2. 現有記錄的外鍵預設為 NULL
3. UI 支援兩種輸入方式：選擇已存在的廠商/物料，或手動輸入文字

### ERP 整合
- `vendors.erp_code` 欄位對應 ERP 系統的廠商編號
- 可透過此編號進行資料同步或對照

### 資料一致性
- 當選擇廠商時，自動填入對應的文字欄位
- 當選擇物料時，自動填入物料名稱到 item 欄位
