# Spec: data-migration

舊系統資料遷移到多租戶架構的規格。

## ADDED Requirements

### Requirement: 遷移腳本支援 dry-run 模式

遷移腳本 **MUST** 支援 dry-run（驗證）模式，在不實際寫入資料的情況下
驗證遷移流程是否正確。

#### Scenario: 執行 dry-run 遷移

```
Given 遠端舊系統資料庫可連線
And 本機新系統資料庫可連線
When 執行遷移腳本並加上 --dry-run 參數
Then 執行所有遷移步驟但不提交變更
And 顯示將要遷移的記錄數量
And 顯示可能的衝突或問題
And 最後回滾所有變更
And 輸出驗證報告
```

### Requirement: 使用者資料遷移並補上多租戶欄位

遷移腳本 **MUST** 將舊系統的 users 表格遷移到新系統，
並 **SHALL** 補上必要的多租戶欄位（tenant_id, role, is_active）。

#### Scenario: 遷移使用者到 chingtech 租戶

```
Given 舊系統有 10 位使用者
And 新系統已建立 "chingtech" 租戶
When 執行使用者遷移
Then 所有使用者記錄插入新系統
And tenant_id 設為 chingtech 租戶 ID
And role 預設為 "user"
And is_active 預設為 true
And 原有的 username, display_name, preferences 保留
And 原有的 created_at, last_login_at 保留
```

#### Scenario: 處理使用者名稱衝突

```
Given 舊系統有使用者 "yazelin"
And 新系統已存在使用者 "yazelin" 屬於其他租戶
When 執行使用者遷移
Then 在 chingtech 租戶建立新的 "yazelin" 記錄
And 使用者可同時存在於多個租戶（依 tenant_id 區分）
```

### Requirement: 專案及相關資料遷移

遷移腳本 **MUST** 將專案及所有相關子表格的資料遷移，
**SHALL** 保留原有的 UUID 和關聯關係。

#### Scenario: 遷移專案資料

```
Given 舊系統有 7 個專案
When 執行專案遷移
Then 所有專案記錄插入新系統
And 保留原有的專案 UUID（id 欄位）
And tenant_id 設為 chingtech 租戶 ID
And 所有子表格資料也一併遷移：
  - project_members（使用新的 user_id）
  - project_meetings
  - project_milestones
  - project_attachments
  - project_links
  - project_delivery_schedules
```

### Requirement: Line Bot 資料遷移

遷移腳本 **MUST** 將 Line Bot 相關資料遷移，
**SHALL** 保持群組和使用者的關聯。

#### Scenario: 遷移 Line 群組和使用者

```
Given 舊系統有 6 個 Line 群組和 14 個 Line 使用者
When 執行 Line Bot 資料遷移
Then 所有 line_groups 記錄插入新系統
And 所有 line_users 記錄插入新系統
And tenant_id 設為 chingtech 租戶 ID
And project_id 關聯保持正確
And line_users.user_id 更新為新系統的使用者 ID
```

#### Scenario: 遷移 Line 訊息和檔案

```
Given 舊系統有 Line 訊息和檔案記錄
When 執行 Line 訊息遷移
Then line_messages 分區表資料正確遷移
And line_files 記錄正確遷移
And 訊息的 line_group_id 和 line_user_id 關聯正確
```

### Requirement: AI 相關資料遷移

遷移腳本 **MUST** 將 AI Agent、Prompts、對話記錄遷移到新租戶。

#### Scenario: 遷移 AI 設定

```
Given 舊系統有 AI Agents 和 Prompts 設定
When 執行 AI 資料遷移
Then ai_agents 記錄插入新系統
And ai_prompts 記錄插入新系統
And tenant_id 設為 chingtech 租戶 ID
```

#### Scenario: 遷移 AI 對話歷史

```
Given 舊系統有 AI 對話記錄
When 執行 AI 對話遷移
Then ai_chats 記錄插入新系統
And user_id 更新為新系統的使用者 ID
And tenant_id 設為 chingtech 租戶 ID
```

### Requirement: 檔案遷移到租戶目錄

遷移腳本 **MUST** 將舊系統的檔案遷移到新系統的多租戶目錄結構。

#### Scenario: 遷移知識庫檔案

```
Given 舊系統 data/knowledge/ 目錄有知識庫檔案
And chingtech 租戶 ID 為 {tid}
When 執行檔案遷移
Then 所有 entries/*.md 複製到 /mnt/nas/ctos/tenants/{tid}/knowledge/entries/
And 所有 assets/images/* 複製到 /mnt/nas/ctos/tenants/{tid}/knowledge/assets/images/
And index.json 複製並更新內部路徑
```

### Requirement: 產生遷移報告

遷移腳本 **MUST** 在完成後產生詳細的報告，記錄遷移結果。

#### Scenario: 產生遷移報告

```
Given 遷移流程已完成
When 產生遷移報告
Then 報告包含：
  - 遷移的租戶資訊
  - 各表格遷移的記錄數
  - 使用者 ID 對應表
  - 檔案遷移清單
  - 遇到的問題和警告
  - 遷移耗時
```

## Cross References

- backend-auth: 使用者模型和認證
- project-management: 專案相關表格
- line-bot: Line Bot 相關表格
- ai-management: AI 相關表格
- knowledge-base: 知識庫檔案結構
