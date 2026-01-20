# Knowledge Base Specification - Multi-Tenant Changes

## MODIFIED Requirements

### Requirement: Knowledge Item Storage
系統 SHALL 儲存知識項目於租戶隔離的目錄：
- 知識檔案儲存於 **/mnt/nas/ctos/tenants/{tenant_id}/knowledge/entries/**
- 附件儲存於 **/mnt/nas/ctos/tenants/{tenant_id}/knowledge/assets/**
- 索引檔案儲存於 **/mnt/nas/ctos/tenants/{tenant_id}/knowledge/index.json**
- 檔案命名格式：kb-{id}-{title-slug}.md

#### Scenario: 建立知識項目
- **WHEN** 用戶建立新知識項目
- **THEN** 檔案儲存於當前租戶的 knowledge/entries/ 目錄
- **AND** 索引更新僅影響該租戶

#### Scenario: 知識庫搜尋
- **WHEN** 用戶搜尋知識庫
- **THEN** 僅搜尋當前租戶的知識項目
- **AND** 不顯示其他租戶的知識

### Requirement: Knowledge Scope
系統 SHALL 支援知識項目的存取範圍：
- global：**租戶內**所有用戶可見
- personal：僅擁有者可見
- **不支援跨租戶共享**

#### Scenario: Global 範圍
- **WHEN** 知識項目 scope 為 global
- **THEN** 該租戶所有用戶可存取
- **AND** 其他租戶用戶無法存取

#### Scenario: Personal 範圍
- **WHEN** 知識項目 scope 為 personal
- **THEN** 僅擁有者可存取
- **AND** 同租戶其他用戶也無法存取

### Requirement: Knowledge Attachments
系統 SHALL 管理知識項目的附件：
- 附件儲存於租戶專屬目錄
- **路徑格式：/mnt/nas/ctos/tenants/{tenant_id}/knowledge/assets/{kb_id}/**
- 支援圖片、PDF、文件等格式

#### Scenario: 上傳知識附件
- **WHEN** 用戶上傳知識附件
- **THEN** 檔案儲存於租戶的 knowledge/assets/ 目錄
- **AND** 附件路徑記錄包含租戶資訊

### Requirement: Knowledge Index
系統 SHALL 維護每個租戶獨立的知識索引：
- **每租戶獨立的 index.json 檔案**
- 索引包含：kb_id, title, category, topics, scope, owner
- 支援快速搜尋和過濾

#### Scenario: 索引更新
- **WHEN** 知識項目被修改
- **THEN** 更新對應租戶的索引
- **AND** 不影響其他租戶的索引

## ADDED Requirements

### Requirement: Knowledge Migration
系統 SHALL 支援知識庫的租戶遷移：
- 匯出租戶所有知識項目和附件
- 在目標租戶匯入知識項目
- 保持 kb_id 的唯一性

#### Scenario: 知識庫匯出
- **WHEN** 管理員匯出租戶知識庫
- **THEN** 產生包含所有 .md 檔案和附件的 ZIP
- **AND** 包含 index.json 索引

#### Scenario: 知識庫匯入
- **WHEN** 管理員匯入知識庫 ZIP
- **THEN** 知識項目儲存於目標租戶目錄
- **AND** 更新目標租戶索引
