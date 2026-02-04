## Context

CTOS 目前有自建的專案管理、物料管理、廠商管理模組，功能簡單但難以擴展。ERPNext 已部署於 `http://ct.erp`，具備完整的 ERP 功能。ERPNext MCP Server（v0.2.0）已提供 24 個工具，包含新增的檔案操作功能。

現況：
- CTOS 有 33 個相關 MCP 工具（專案 23 + 廠商 3 + 物料 10）
- ERPNext MCP 有 24 個通用工具，可覆蓋所有需求
- 資料分散在 CTOS PostgreSQL 與 ERPNext MariaDB

## Goals / Non-Goals

**Goals:**
- 將專案、物料、廠商資料一次性遷移至 ERPNext
- 移除 CTOS 的 33 個相關 MCP 工具，改用 ERPNext MCP
- 簡化前端，用單一 ERPNext 入口取代 3 個 app
- 更新 AI Agent prompt 引導使用 ERPNext

**Non-Goals:**
- 不修改 ERPNext 核心功能或建立 Custom DocType
- 不保留 CTOS 與 ERPNext 雙軌運行
- 不遷移知識庫、檔案管理等其他功能

## Decisions

### 1. 資料遷移策略

**決策**: 使用一次性 Python 腳本遷移，不做持續同步

**理由**:
- 資料量不大（預估 < 1000 筆）
- 一次性遷移較簡單，不需維護同步機制
- 遷移後 CTOS 相關資料表標記 deprecated，不再使用

**替代方案**:
- ❌ 雙向同步：複雜度高，需處理衝突
- ❌ 漸進遷移：延長過渡期，增加維護成本

### 2. 遷移順序

**決策**: 廠商 → 物料 → 專案

**理由**:
- 廠商（Supplier）無相依性，最簡單
- 物料（Item）依賴廠商（default_vendor）
- 專案（Project）依賴物料（發包交貨）和廠商

### 3. ID 對應處理

**決策**: 建立 ID 映射表，遷移完成後保存對照

**理由**:
- CTOS 用 UUID，ERPNext 用自動命名（如 PROJ-0001）
- 需要對照表處理子資料的 foreign key
- 遷移後可用於驗證和除錯

**實作**:
```python
# 遷移時建立映射
id_mapping = {
    "vendors": {},      # ctos_id -> erpnext_name
    "items": {},        # ctos_id -> erpnext_item_code
    "projects": {},     # ctos_id -> erpnext_project_name
}
```

### 4. 專案子資料處理

**決策**: 依序遷移，使用 ERPNext 原生機制

| CTOS 子資料 | ERPNext 處理方式 |
|------------|------------------|
| project_members | 更新 Project.users[] 子表 |
| project_milestones | 建立 Task，設定 project 欄位 |
| project_meetings | 建立 Event，設定 reference_doctype=Project |
| project_attachments | 用 upload_file 上傳，設定 attached_to |
| project_links | 建立 Comment，設定 reference_doctype=Project |
| project_delivery_schedules | 建立 Purchase Order |

### 5. 庫存遷移策略

**決策**: 只遷移物料主檔，不遷移歷史交易

**理由**:
- ERPNext 庫存有完整的估值、批次、序號邏輯
- 遷移歷史交易會破壞 ERPNext 的庫存計算
- 建議在 ERPNext 做一次期初盤點

**實作**:
- 遷移 `inventory_items` → `Item`
- 不遷移 `inventory_transactions`
- 訂購記錄視需求決定是否遷移

### 6. 前端處理

**決策**: 移除 3 個 app，新增 ERPNext 外連

**實作**:
```javascript
// desktop.js
{
    id: 'erpnext',
    name: 'ERPNext',
    icon: 'erpnext',  // 需新增 icon
    action: () => window.open('http://ct.erp', '_blank')
}
```

### 7. MCP 工具移除策略

**決策**: 分階段移除，先移除工具再移除 API

**Phase 1**: 移除 MCP 工具定義（mcp_server.py）
**Phase 2**: 移除 API endpoints（api/*.py）
**Phase 3**: 移除前端 JS 模組
**Phase 4**: 標記資料表 deprecated

### 8. AI Agent Prompt 更新

**決策**: 更新 prompt 引導使用 ERPNext MCP

**變更**:
- 移除 CTOS 專案/物料/廠商工具的說明
- 新增 ERPNext DocType 說明（Project, Item, Supplier 等）
- 提供常用操作範例

## Risks / Trade-offs

| 風險 | 緩解措施 |
|------|---------|
| 遷移資料遺失 | 遷移前備份 CTOS 資料庫，保留原資料表 |
| ERPNext 權限不足 | 預先設定 API Key 用戶角色（已完成） |
| 遷移腳本錯誤 | 先在測試環境驗證，提供 dry-run 模式 |
| 用戶不熟悉 ERPNext | 提供操作指引，初期協助轉換 |
| 庫存數量不一致 | 遷移後在 ERPNext 做期初盤點調整 |

## Migration Plan

### 執行順序

1. **備份**
   - 匯出 CTOS 資料庫
   - 記錄現有資料筆數

2. **遷移資料**（使用 Python 腳本）
   ```bash
   python scripts/migrate_to_erpnext.py --dry-run  # 先測試
   python scripts/migrate_to_erpnext.py            # 正式執行
   ```

3. **驗證**
   - 比對筆數
   - 抽查關鍵資料
   - 測試 ERPNext MCP 工具

4. **移除 CTOS 程式碼**
   - 移除 MCP 工具
   - 移除 API endpoints
   - 移除前端模組

5. **更新 AI Agent**
   - 更新 prompt
   - 測試 Line Bot 操作

### Rollback 策略

- 資料庫有備份，可還原
- Git 可回復程式碼變更
- ERPNext 資料可手動刪除（有 _MCP_MIGRATED_ prefix）

## Resolved Questions

| 問題 | 決策 |
|------|------|
| 庫存期初值 | 只需目前總數量正確，用期初 Stock Entry 調整 |
| 歷史訂購記錄 | 不遷移 |
| 專案附件（NAS） | 大型附件保留 NAS 連結，不上傳 ERPNext |
