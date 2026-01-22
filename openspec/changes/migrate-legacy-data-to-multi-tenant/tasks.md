# Tasks: migrate-legacy-data-to-multi-tenant

## 階段一：準備工作

### 1.1 備份舊系統資料
- [ ] 匯出遠端資料庫完整備份
- [ ] 複製遠端 `data/knowledge/` 目錄到本機暫存
- [ ] 記錄舊系統各表格記錄數（用於驗證）

### 1.2 建立 chingtech 租戶
- [ ] 在本機資料庫建立 `chingtech` 租戶記錄
- [ ] 設定 `enable_nas_auth = true`
- [ ] 建立租戶目錄結構：`/mnt/nas/ctos/tenants/{tid}/`

## 階段二：NAS 登入功能開發

### 2.1 後端：租戶設定模型更新
- [ ] 在 `TenantSettings` 新增 `enable_nas_auth` 欄位
- [ ] 新增 `nas_auth_host`, `nas_auth_port`, `nas_auth_share` 欄位
- [ ] 建立 Alembic migration（若需要資料庫變更）

### 2.2 後端：登入驗證邏輯修改
- [ ] 修改 `api/auth.py` 的 `login` 函數
- [ ] 依據租戶設定決定是否啟用 NAS 驗證
- [ ] 支援租戶自訂 NAS 主機設定

### 2.3 前端：租戶設定介面
- [ ] 在平台設定 > 租戶設定新增「NAS 登入驗證」區塊
- [ ] 新增測試連線按鈕
- [ ] 儲存設定功能

### 2.4 測試
- [ ] 測試 chingtech 租戶的 NAS 登入功能
- [ ] 驗證使用 yazelin 帳號可以登入
- [ ] 驗證首次登入會自動建立使用者記錄

## 階段三：資料遷移腳本開發

### 3.1 建立遷移腳本框架
- [ ] 建立 `backend/scripts/migrate_legacy_data.py`
- [ ] 實作資料庫連線（本機 + 遠端）
- [ ] 實作 dry-run 模式

### 3.2 使用者遷移
- [ ] 遷移 `users` 表格
- [ ] 建立 user_id 對應表（old → new）
- [ ] 處理使用者名稱衝突

### 3.3 專案相關遷移
- [ ] 遷移 `projects` 表格
- [ ] 遷移 `project_members`（使用 user_id 對應）
- [ ] 遷移 `project_meetings`
- [ ] 遷移 `project_milestones`
- [ ] 遷移 `project_attachments`
- [ ] 遷移 `project_links`
- [ ] 遷移 `project_delivery_schedules`

### 3.4 Line Bot 資料遷移
- [ ] 遷移 `line_groups`
- [ ] 遷移 `line_users`（使用 user_id 對應）
- [ ] 遷移 `line_messages`（分區表）
- [ ] 遷移 `line_files`
- [ ] 遷移 `line_group_memories`
- [ ] 遷移 `line_user_memories`

### 3.5 AI 相關遷移
- [ ] 遷移 `ai_agents`
- [ ] 遷移 `ai_prompts`
- [ ] 遷移 `ai_chats`（使用 user_id 對應）
- [ ] 遷移 `ai_logs`（分區表，可選擇性遷移）

### 3.6 其他資料遷移
- [ ] 遷移 `vendors`
- [ ] 遷移 `inventory_items`
- [ ] 遷移 `inventory_transactions`
- [ ] 遷移 `inventory_orders`
- [ ] 遷移 `public_share_links`
- [ ] 遷移 `login_records`（分區表，可選擇性遷移）
- [ ] 遷移 `messages`（分區表）
- [ ] 遷移 `line_binding_codes`

## 階段四：檔案遷移

### 4.1 知識庫檔案遷移
- [ ] 複製知識庫 entries 到租戶目錄
- [ ] 複製知識庫 assets 到租戶目錄
- [ ] 更新 `index.json` 中的路徑
- [ ] 驗證附件圖片可正常顯示

### 4.2 資料庫路徑更新
- [ ] 更新知識庫中的附件路徑格式
- [ ] 更新專案附件路徑
- [ ] 更新 Line 檔案路徑

## 階段五：驗證與收尾

### 5.1 資料完整性驗證
- [ ] 比對遷移前後記錄數
- [ ] 驗證關聯關係完整性
- [ ] 檢查分區表資料

### 5.2 功能測試
- [ ] 使用 yazelin 登入並瀏覽專案
- [ ] 查看會議記錄和里程碑
- [ ] 瀏覽知識庫和附件
- [ ] 檢查 Line Bot 群組設定
- [ ] 驗證 AI 對話歷史

### 5.3 文件更新
- [ ] 更新 README.md（說明 chingtech 租戶）
- [ ] 記錄遷移流程供日後參考

### 5.4 清理
- [ ] 刪除本機暫存檔案
- [ ] 歸檔遷移腳本
- [ ] 關閉此 OpenSpec 變更

## 執行順序依賴關係

```
階段一 (準備) → 階段二 (NAS 登入) → 階段三 (資料遷移) → 階段四 (檔案遷移) → 階段五 (驗證)
                     ↓
           可與階段三並行開發
```

## 預估工作量

| 階段 | 預估時間 |
|------|---------|
| 階段一：準備工作 | 0.5 天 |
| 階段二：NAS 登入功能 | 1 天 |
| 階段三：資料遷移腳本 | 2 天 |
| 階段四：檔案遷移 | 0.5 天 |
| 階段五：驗證與收尾 | 0.5 天 |
| **合計** | **4.5 天** |
