# Tasks: 統一路徑管理器

## Phase 1: 建立 PathManager（不改現有邏輯）

### 後端

- [x] 建立 `backend/src/ching_tech_os/services/path_manager.py`
  - [x] 實作 `StorageZone` enum
  - [x] 實作 `ParsedPath` dataclass
  - [x] 實作 `PathManager` 類別
    - [x] `parse()` - 解析路徑，支援新舊格式
    - [x] `to_filesystem()` - 轉換為實際檔案系統路徑
    - [x] `to_api()` - 轉換為前端 API 路徑
    - [x] `to_storage()` - 轉換為資料庫儲存格式
    - [x] `from_legacy()` - 從舊格式轉換
  - [x] 支援舊格式自動識別與轉換

### 前端

- [x] 建立 `frontend/js/path-utils.js`
  - [x] 實作 `PathUtils.parse()` - 解析路徑
  - [x] 實作 `PathUtils.toApiUrl()` - 轉換為 API URL
  - [x] 實作 `PathUtils.isImage()` - 判斷是否為圖片
  - [x] 實作 `PathUtils.isPdf()` - 判斷是否為 PDF
- [x] 在 `index.html` 和 `login.html` 引入 `path-utils.js`

### 測試

- [ ] 後端單元測試（可選，視需求）
- [ ] 手動測試舊格式轉換

---

## Phase 2: 新功能使用新格式

### 後端

- [x] 建立 `backend/src/ching_tech_os/api/files.py`
  - [x] `GET /api/files/{zone}/{path}` - 讀取/預覽檔案
  - [x] `GET /api/files/{zone}/{path}/download` - 下載檔案
  - [x] 支援四種 zone: ctos, shared, temp, local
  - [x] 路徑穿越攻擊防護
- [x] 在 `main.py` 註冊 files router

### 待整合

- [ ] 前端 `PathUtils.toApiUrl()` 已可產生正確的 API 路徑
- [ ] 等待現有程式碼逐步遷移使用新 API

---

## 驗收標準

### Phase 1
1. PathManager 可正確解析所有舊格式路徑
2. PathManager 可正確轉換為新格式
3. 前端 PathUtils 與後端邏輯一致
4. 不影響現有功能（Phase 1 不修改現有程式碼）

### Phase 2
1. `/api/files/{zone}/{path}` 可正確存取四種區域的檔案
2. 新 API 使用 PathManager 處理路徑
