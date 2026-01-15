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

---

## Phase 3: 遷移現有程式碼

### MCP Server

- [x] `read_document` 工具改用 `path_manager`
  - [x] 使用 `path_manager.parse()` 解析路徑
  - [x] 使用 `path_manager.to_filesystem()` 轉換路徑
  - [x] 加入 zone 安全檢查（只允許 CTOS/SHARED）
- [x] `convert_pdf_to_images` 工具改用 `path_manager`
  - [x] 使用 `path_manager.parse()` 解析路徑
  - [x] 使用 `path_manager.to_filesystem()` 轉換路徑
  - [x] 加入 zone 安全檢查（允許 CTOS/SHARED/TEMP）
- [x] 移除 `resolve_nas_path()` 函數

### 其他模組

- [x] `share.py` - `validate_nas_file_path()` 改用 `path_manager`
  - [x] 使用 `path_manager.parse()` 解析路徑
  - [x] 使用 `path_manager.to_filesystem()` 轉換路徑
  - [x] 加入 zone 安全檢查（只允許 CTOS/SHARED）
- [x] `linebot.py` - `generate_nas_path()` - 不需修改（生成路徑，非解析）
- [x] `knowledge.py` - 附件路徑處理 - 不需修改（PathManager 支援舊格式）
- [x] `project.py` - 專案附件路徑 - 不需修改（PathManager 支援舊格式）
- [x] 前端 `file-manager.js` - `toSystemMountPath()` - 不需修改（產生的路徑 PathManager 可解析）

---

## 驗收標準

### Phase 3
1. 現有 MCP 工具正常運作
2. 路徑解析邏輯統一使用 PathManager

---

## 測試清單

### 1. PathManager 路徑解析（後端）

測試 `path_manager.parse()` 支援的格式：

| 輸入格式 | 預期 Zone | 預期路徑 |
|---------|----------|---------|
| `ctos://linebot/files/xxx.pdf` | CTOS | `linebot/files/xxx.pdf` |
| `shared://亦達光學/doc.pdf` | SHARED | `亦達光學/doc.pdf` |
| `temp://abc123/page1.png` | TEMP | `abc123/page1.png` |
| `local://knowledge/assets/x.jpg` | LOCAL | `knowledge/assets/x.jpg` |
| `nas://亦達光學/xxx.pdf`（舊格式） | SHARED | `亦達光學/xxx.pdf` |
| `/mnt/nas/projects/xxx.pdf`（舊格式） | SHARED | `xxx.pdf` |
| `/mnt/nas/ctos/xxx.pdf`（舊格式） | CTOS | `xxx.pdf` |
| `/tmp/ctos/xxx.pdf`（舊格式） | TEMP | `xxx.pdf` |
| `../assets/xxx.jpg`（舊格式） | LOCAL | `knowledge/assets/xxx.jpg` |

### 2. 統一檔案 API（Phase 2）

測試 `/api/files/{zone}/{path}` 端點：

- [ ] `GET /api/files/shared/test.txt` - 讀取 shared 區檔案
- [ ] `GET /api/files/ctos/linebot/files/test.jpg` - 讀取 ctos 區檔案
- [ ] `GET /api/files/temp/xxx/page.png` - 讀取 temp 區檔案
- [ ] `GET /api/files/shared/test.txt/download` - 下載檔案
- [ ] `GET /api/files/invalid/test.txt` - 應回傳 400 錯誤
- [ ] `GET /api/files/shared/../etc/passwd` - 路徑穿越應被阻擋
- [ ] 未授權請求應回傳 401

### 3. MCP 工具測試

- [ ] `read_document` - 讀取 shared:// 區文件
- [ ] `read_document` - 讀取 ctos:// 區文件
- [ ] `read_document` - 讀取舊格式路徑（應自動轉換）
- [ ] `read_document` - 嘗試讀取 temp:// 區應被拒絕
- [ ] `convert_pdf_to_images` - 轉換 shared:// 區 PDF
- [ ] `convert_pdf_to_images` - 輸出到 temp:// 區

### 4. 分享功能測試

- [ ] 從檔案管理器建立 NAS 檔案分享連結
- [ ] 透過分享連結下載檔案
- [ ] 分享連結過期後應無法存取

### 5. 前端 PathUtils 測試

在瀏覽器 Console 測試：

```javascript
// 解析測試
PathUtils.parse('shared://test/doc.pdf')
// 應回傳 { zone: 'shared', path: 'test/doc.pdf', raw: '...' }

// API URL 生成
PathUtils.toApiUrl('shared://test/doc.pdf')
// 應回傳 '/api/files/shared/test/doc.pdf'

// 檔案類型判斷
PathUtils.isImage('shared://test/photo.jpg')  // true
PathUtils.isPdf('shared://test/doc.pdf')      // true
```

---

## 自動化測試

### 執行所有單元測試

```bash
# 後端測試（PathManager + Files API）
cd backend && uv run pytest tests/test_path_manager.py tests/test_files_api.py -v

# 前端測試（PathUtils）
node frontend/tests/path-utils.test.js
```

### 執行 E2E 測試

```bash
# PathManager E2E 測試（不需要後端運行）
cd backend && uv run python tests/e2e/test_path_manager_e2e.py

# Files API E2E 測試（需要後端運行）
export AUTH_TOKEN='your_token_here'
cd backend && uv run python tests/e2e/test_files_api_e2e.py
```

### 測試結果（2026-01-16）

| 測試類別 | 測試數量 | 結果 |
|---------|---------|------|
| PathManager 單元測試 | 39 | ✅ 全部通過 |
| Files API 單元測試 | 19 | ✅ 全部通過 |
| PathUtils 前端測試 | 36 | ✅ 全部通過 |
| PathManager E2E 測試 | 24 | ✅ 全部通過 |

**總計：118 個測試全部通過**
