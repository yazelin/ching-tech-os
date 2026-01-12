# Tasks: sync-knowledge-projects-from-db

## 實作任務

### 1. 修改 `get_all_tags()` 函數
**檔案**：`backend/src/ching_tech_os/services/knowledge.py`

- [ ] 引入資料庫連線（`database.py`）
- [ ] 修改 `get_all_tags()` 為 async 函數
- [ ] 新增查詢 `projects` 表取得專案名稱的邏輯
- [ ] 合併資料庫專案與現有靜態標籤

### 2. 更新 API 路由
**檔案**：`backend/src/ching_tech_os/api/knowledge.py`

- [ ] 將 `get_tags()` endpoint 改為 async
- [ ] 呼叫修改後的 `get_all_tags()` 函數

### 3. 清理硬編碼預設值
**檔案**：`backend/src/ching_tech_os/models/knowledge.py`

- [ ] 移除 `TagsResponse` 預設值中的硬編碼專案列表
- [ ] 改為空列表或保留少數通用專案（如 "common"）

## 驗證項目

- [ ] 啟動後端服務，無啟動錯誤
- [ ] 呼叫 `GET /api/knowledge/tags`，確認返回專案管理中的專案名稱
- [ ] 開啟知識庫視窗，確認篩選器下拉選單顯示正確專案
- [ ] 編輯知識，確認專案多選選項顯示正確專案
- [ ] 在專案管理新增專案後，知識庫能立即看到新專案

## 依賴關係

- 無需資料庫 migration（使用現有 `projects` 表）
- 無需前端修改（API 介面不變）
