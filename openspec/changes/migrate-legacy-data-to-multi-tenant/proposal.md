# Proposal: migrate-legacy-data-to-multi-tenant

## 摘要

將舊系統（192.168.11.11 上的單租戶版本）的所有資料完整遷移到新的多租戶架構，
並新增租戶可選擇使用 NAS SMB 帳號進行登入驗證的功能。

## 背景

目前有兩套系統：

1. **舊系統**（192.168.11.11）
   - 單租戶架構（無 `tenant_id` 欄位）
   - 資料庫：10 位使用者、7 個專案、6 個 Line 群組、14 位 Line 使用者
   - 檔案：知識庫文件（`data/knowledge/`）、附件圖片
   - 認證：僅支援 NAS SMB 驗證

2. **新系統**（本機）
   - 多租戶架構（所有主要表格都有 `tenant_id` 欄位）
   - 已有租戶：default、demo1、trial1、corina
   - 檔案儲存：`/mnt/nas/ctos/tenants/{tenant_id}/` 多租戶隔離結構
   - 認證：支援密碼驗證 + NAS SMB 驗證（fallback）

## 需求

### 主要需求

1. **資料遷移**
   - 將舊系統資料庫的所有資料遷移到新系統的「chingtech」租戶（新建）
   - 所有記錄加上正確的 `tenant_id`
   - 保留原有的 UUID 和關聯關係

2. **檔案遷移**
   - 知識庫檔案：遷移到 `/mnt/nas/ctos/tenants/{chingtech_tenant_id}/knowledge/`
   - Line Bot 檔案：遷移到對應的租戶目錄
   - 專案附件：遷移到租戶附件目錄

3. **NAS 登入設定**
   - 新增租戶設定選項：允許使用 NAS SMB 帳號登入
   - 當租戶啟用此選項時，使用者可以用 NAS 帳密登入（無需在系統中先建立帳號）
   - 首次登入時自動建立使用者記錄

### 次要需求

4. **遷移工具**
   - 提供遷移腳本，支援驗證模式（dry-run）
   - 遷移完成後產生報告

5. **向後相容**
   - 遷移後的資料可以正常運作
   - 原有的知識庫路徑格式需要轉換

## 遷移範圍

### 資料庫表格（需要遷移）

| 表格 | 遠端記錄數 | 說明 |
|------|-----------|------|
| users | 10 | 使用者（需補上 tenant_id, role 等新欄位）|
| projects | 7 | 專案 |
| project_members | ? | 專案成員 |
| project_meetings | ? | 會議記錄 |
| project_milestones | ? | 里程碑 |
| project_attachments | ? | 專案附件 |
| project_links | ? | 專案連結 |
| project_delivery_schedules | ? | 發包/交貨記錄 |
| line_groups | 6 | Line 群組 |
| line_users | 14 | Line 使用者 |
| line_messages | ? | Line 訊息（分區表）|
| line_files | ? | Line 檔案 |
| line_group_memories | ? | 群組記憶 |
| line_user_memories | ? | 使用者記憶 |
| ai_chats | ? | AI 對話 |
| ai_logs | ? | AI 日誌（分區表）|
| ai_agents | ? | AI Agent 設定 |
| ai_prompts | ? | AI Prompts |
| vendors | ? | 廠商 |
| inventory_items | ? | 物料 |
| inventory_transactions | ? | 庫存交易 |
| inventory_orders | ? | 訂購記錄 |
| public_share_links | ? | 分享連結 |
| login_records | ? | 登入記錄（分區表）|
| messages | ? | 系統訊息（分區表）|

### 檔案（需要遷移）

- `data/knowledge/entries/` - 知識庫 Markdown 文件
- `data/knowledge/index.json` - 知識庫索引
- `data/knowledge/assets/images/` - 知識庫附件圖片

## 設計決策

### 1. 建立新租戶「chingtech」

- 不使用 default 租戶，避免與測試資料混淆
- 新租戶代碼：`chingtech`
- 新租戶名稱：`擎添科技`
- 方案：`enterprise`
- 啟用 NAS 登入驗證

### 2. NAS 登入設定

在 `TenantSettings` 新增欄位：

```python
class TenantSettings:
    # ... 現有欄位 ...

    # NAS SMB 登入設定
    enable_nas_auth: bool = False  # 允許 NAS 帳號登入
    nas_auth_host: str | None = None  # NAS 主機（預設使用系統設定）
    nas_auth_share: str | None = None  # NAS 共享名稱（用於驗證）
```

### 3. 檔案路徑轉換

舊格式 → 新格式對照：

| 舊路徑 | 新路徑 |
|--------|--------|
| `data/knowledge/entries/kb-001.md` | `/mnt/nas/ctos/tenants/{tid}/knowledge/entries/kb-001.md` |
| `data/knowledge/assets/images/kb-001-*.jpg` | `/mnt/nas/ctos/tenants/{tid}/knowledge/assets/images/kb-001-*.jpg` |
| `nas://knowledge/attachments/...` | `ctos://knowledge/...`（資料庫內路徑格式）|

## 風險評估

| 風險 | 等級 | 緩解措施 |
|------|------|----------|
| 資料遺失 | 高 | 遷移前備份、dry-run 驗證 |
| 關聯斷裂 | 中 | 使用交易確保原子性、事後驗證 |
| 路徑錯誤 | 中 | 遷移後批量檢查、路徑轉換測試 |
| 權限問題 | 低 | 確認 NAS 掛載點權限 |

## 成功標準

1. 所有使用者可以用原有 NAS 帳號登入 chingtech 租戶
2. 所有專案、會議記錄、里程碑完整呈現
3. 知識庫文件和附件可正常瀏覽
4. Line Bot 群組和訊息記錄完整
5. AI 對話歷史可查詢
