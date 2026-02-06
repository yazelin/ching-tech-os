## Context

目前 CTOS 採用 Shared Database + Row-Level Isolation 的多租戶架構：
- 23 張資料表都有 `tenant_id` 欄位
- 所有查詢都需要 `WHERE tenant_id = ?` 過濾
- 三層角色系統：`platform_admin` > `tenant_admin` > `user`
- Line Bot 支援每租戶獨立憑證（加密儲存於資料庫）
- 檔案系統按租戶隔離：`/tenants/{tenant_id}/...`

現有租戶：
- `chingtech`（擎添工業）- 主要使用者，需保留所有資料
- 測試租戶 - 可刪除

## Goals / Non-Goals

**Goals:**
- 移除所有多租戶程式碼，簡化系統架構
- 簡化角色系統為 `admin` / `user` 兩種
- 保留 chingtech 租戶的所有現有資料
- 保留 Line Bot UI 設定功能（改為寫入設定檔）
- 確保遷移過程資料零遺失

**Non-Goals:**
- 不建立新的多實例部署自動化（手動 Docker 部署即可）
- 不建立擴充套件框架（ERPNext 整合保持現狀，未來再處理）
- 不處理跨實例資料同步

**附註：**
- 現有的 `tenant_data.py` 資料匯出/匯入功能將保留並簡化為系統備份/還原功能

## Decisions

### Decision 1: 資料庫遷移策略

**選擇：單一 Migration 一次性移除所有 tenant_id**

**理由：**
- 系統目前只有開發/測試環境，沒有多個生產實例需要漸進遷移
- 一次性遷移比漸進式更簡單，避免中間狀態的複雜性
- chingtech 是唯一需要保留的租戶，資料量可控

**替代方案：**
- 漸進式遷移（先標記 deprecated，再移除）→ 增加複雜度，目前不需要

**遷移步驟：**
```sql
-- 1. 記錄 chingtech 租戶 ID
-- 2. 刪除非 chingtech 租戶的資料
-- 3. 移除 tenant_id 欄位
-- 4. 刪除 tenants, tenant_admins 表
-- 5. 更新角色欄位值
```

### Decision 2: 角色系統設計

**選擇：`admin` / `user` 雙角色制**

| 角色 | 權限 |
|------|------|
| `admin` | 所有功能、使用者管理、系統設定 |
| `user` | 依 app_permissions 設定的功能 |

**遷移對應：**
- `platform_admin` → `admin`
- `tenant_admin` → `admin`
- `user` → `user`

**理由：**
- 單一實例不需要平台層級管理
- 租戶管理員和一般管理員在單一租戶下無差異
- 保留 app_permissions 機制提供細粒度控制

### Decision 3: Line Bot 憑證管理

**選擇：環境變數 + 資料庫設定 + UI 管理**

**架構：**
```
┌─────────────────────────────────────────────────────────┐
│                    優先順序                              │
│                                                         │
│  1. 資料庫 bot_settings 表（UI 設定時寫入）              │
│     ↓ 如果沒有                                          │
│  2. 環境變數 LINE_CHANNEL_ACCESS_TOKEN                  │
│     LINE_CHANNEL_SECRET                                 │
│     ↓ 如果沒有                                          │
│  3. 報錯：未設定 Line Bot 憑證                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**新增資料表：**
```sql
CREATE TABLE bot_settings (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,  -- 'line', 'telegram'
    key VARCHAR(100) NOT NULL,
    value TEXT,  -- 加密儲存
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, key)
);
```

**理由：**
- 環境變數提供基本設定方式（適合 Docker 部署）
- 資料庫設定提供 UI 動態更新能力（使用者需求）
- 加密儲存確保憑證安全

**替代方案：**
- 只用環境變數 → 無法透過 UI 更新，需重啟服務
- 只用設定檔 → 需要額外的檔案管理

### Decision 4: 檔案系統路徑結構

**選擇：移除 tenants 層級，扁平化結構**

**Before:**
```
/mnt/nas/ctos/
├── system/
└── tenants/
    └── {tenant-uuid}/
        ├── knowledge/
        ├── linebot/
        └── ai-generated/
```

**After:**
```
/mnt/nas/ctos/
├── knowledge/
│   ├── entries/
│   └── assets/
├── linebot/
│   ├── groups/
│   ├── users/
│   └── files/
└── ai-generated/
```

**遷移：**
```bash
# 將 chingtech 租戶目錄內容移到根層級
mv /mnt/nas/ctos/tenants/{chingtech-uuid}/* /mnt/nas/ctos/
rm -rf /mnt/nas/ctos/tenants/
```

### Decision 5: API 端點處理

**選擇：直接移除租戶相關端點，不提供兼容**

**移除的端點：**
- `POST /api/auth/login` 的 `tenant_code` 參數
- `/api/tenant/*` 所有端點
- `/api/admin/tenants/*` 所有端點

**保留並修改的端點：**
- `/api/user/me` - 移除 `tenant` 欄位，保留 `role`（值改為 admin/user）
- `/api/admin/users` - 移除租戶過濾邏輯
- `/api/bot/settings` - 新增，用於 Line Bot 憑證管理

**理由：**
- 沒有外部系統依賴這些 API
- 直接移除比維護兼容層簡單

### Decision 6: Session 結構簡化

**Before:**
```python
class SessionData:
    username: str
    password: str
    user_id: int
    tenant_id: UUID | None
    role: str  # platform_admin, tenant_admin, user
    app_permissions: dict
```

**After:**
```python
class SessionData:
    username: str
    password: str
    user_id: int
    role: str  # admin, user
    app_permissions: dict
```

## Risks / Trade-offs

### Risk 1: 資料遷移遺漏
**風險**：遷移時遺漏某些關聯資料導致功能異常
**緩解**：
- 遷移前完整備份資料庫
- 建立遷移前後資料筆數對照表
- 遷移後執行完整功能測試

### Risk 2: 硬編碼的 tenant_id 引用
**風險**：程式碼中可能有硬編碼或動態組合的 tenant_id 查詢被遺漏
**緩解**：
- 使用 grep 搜尋所有 `tenant_id`、`tenant`、`ctos_tenant` 字串
- 程式碼審查確認所有服務層都已更新
- 整合測試覆蓋主要功能路徑

### Risk 3: Line Bot Webhook 憑證驗證失敗
**風險**：遷移後 Line Bot 因憑證讀取邏輯變更而無法驗證 webhook
**緩解**：
- 遷移前記錄現有憑證
- 遷移後立即設定環境變數或透過 UI 設定
- 準備 fallback 到硬編碼憑證的臨時方案

### Risk 4: 前端殘留的租戶邏輯
**風險**：前端 JavaScript 中殘留 tenant 相關邏輯導致錯誤
**緩解**：
- 搜尋並移除所有前端的 tenant 相關程式碼
- 檢查 localStorage 是否有 tenant 相關資料
- 清除瀏覽器快取後測試

### Trade-off: 失去多租戶彈性
**取捨**：移除後無法快速支援新租戶
**接受原因**：
- 目前商業模式不需要 SaaS 多租戶
- 獨立實例部署提供更好的客製彈性
- 未來若需要可重新實作（但目前不預期）

## Migration Plan

### Phase 1: 準備（實作前）
1. 完整備份資料庫：`pg_dump ching_tech_os > backup_before_migration.sql`
2. 記錄 chingtech 租戶的 UUID
3. 備份 NAS 檔案：`rsync -av /mnt/nas/ctos/ /backup/ctos/`

### Phase 2: 資料庫遷移
1. 建立並執行 Alembic migration
2. 驗證資料筆數正確
3. 驗證外鍵關聯正常

### Phase 3: 檔案系統遷移
1. 移動 chingtech 租戶檔案到根層級
2. 更新 config.py 的 PathManager
3. 驗證檔案存取正常

### Phase 4: 程式碼部署
1. 部署更新後的後端程式碼
2. 部署更新後的前端程式碼
3. 設定 Line Bot 環境變數

### Phase 5: 驗證
1. 測試登入功能
2. 測試 Line Bot 功能
3. 測試知識庫功能
4. 測試 AI 對話功能
5. 測試使用者管理功能

### Rollback Strategy
如果遷移失敗：
1. 停止服務
2. 還原資料庫：`psql ching_tech_os < backup_before_migration.sql`
3. 還原檔案：`rsync -av /backup/ctos/ /mnt/nas/ctos/`
4. 切回舊版程式碼
5. 重啟服務

## Open Questions

1. **Line Bot 憑證 UI 的權限控制**
   - 只有 admin 可以修改？還是需要更細的權限？
   - 暫定：只有 admin 可以存取 Bot 設定頁面

2. **現有 ERPNext 整合程式碼的處理**
   - 目前 ERPNext MCP Server 是否有租戶相關邏輯？
   - 需要檢查並移除（如果有的話）

3. **Telegram Bot 憑證是否同樣處理**
   - 是否也改為環境變數 + UI 設定模式？
   - 暫定：是，與 Line Bot 一致
