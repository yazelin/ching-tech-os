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

- [x] 後端單元測試（102 個測試通過）
- [x] 手動測試舊格式轉換

---

## Phase 2: 新功能使用新格式

### 後端

- [x] 建立 `backend/src/ching_tech_os/api/files.py`
  - [x] `GET /api/files/{zone}/{path}` - 讀取/預覽檔案
  - [x] `GET /api/files/{zone}/{path}/download` - 下載檔案
  - [x] 支援四種 zone: ctos, shared, temp, local
  - [x] 路徑穿越攻擊防護
- [x] 在 `main.py` 註冊 files router

### 前端遷移（已完成）

- [x] `image-viewer.js` - 改用 `PathUtils.toApiUrl()`
- [x] `text-viewer.js` - 改用 `PathUtils.toApiUrl()`
- [x] `pdf-viewer.js` - 改用 `PathUtils.toApiUrl()`
- [x] `file-manager.js` - 圖片/文字預覽改用 `PathUtils.toApiUrl()`
- [x] `path-utils.js` - 新增檔案管理器路徑支援（`/擎添共用區/...`）
- [x] `knowledge-base.js` - 不需修改（使用知識庫專用 API）
- [x] `project-management.js` - 不需修改（使用專案專用 API）

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

- [x] `GET /api/files/shared/test.txt` - 讀取 shared 區檔案（手動）
- [x] `GET /api/files/ctos/linebot/files/test.jpg` - 讀取 ctos 區檔案（手動）
- [x] `GET /api/files/temp/xxx/page.png` - 讀取 temp 區檔案（手動）
- [x] `GET /api/files/nas/home/xxx.jpg` - 讀取 nas 區檔案（手動）
- [x] `GET /api/files/shared/test.txt/download` - 下載檔案（手動）
- [x] `GET /api/files/invalid/test.txt` - 應回傳 400 錯誤 ✅ 單元測試
- [x] `GET /api/files/shared/../etc/passwd` - 路徑穿越應被阻擋 ✅ 單元測試
- [x] 未授權請求應回傳 401 ✅ E2E 測試

### 3. MCP 工具測試（透過 Line Bot 或 Claude Code 測試）

- [x] `read_document` - 讀取 shared:// 區文件（三橋簡報）
- [x] `read_document` - 讀取 ctos:// 區文件
- [x] `read_document` - 讀取舊格式路徑（應自動轉換）
- [x] `read_document` - 嘗試讀取 temp:// 區應被拒絕
- [x] `convert_pdf_to_images` - 轉換 ctos:// 區 PDF（Banana PDF）
- [x] `convert_pdf_to_images` - 輸出到 ctos:// 區（linebot/files/pdf-converted）

### 4. 檔案管理器預覽測試（原始問題）

- [x] 圖片預覽：開啟檔案管理器 → 點擊 `/home/xxx.jpg` → 確認圖片正確顯示
- [x] 文字預覽：開啟檔案管理器 → 點擊文字檔案 → 確認內容正確顯示
- [x] PDF 預覽：開啟檔案管理器 → 點擊 PDF 檔案 → 確認 PDF 正確載入

### 5. 分享功能測試

- [x] 從檔案管理器建立 NAS 檔案分享連結
- [x] 透過分享連結下載檔案
- [x] 分享連結過期後應無法存取

### 6. 前端 PathUtils 測試

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

### 測試結果（2026-01-16 更新）

| 測試類別 | 測試數量 | 結果 |
|---------|---------|------|
| PathManager 單元測試 | 43 | ✅ 全部通過 |
| Files API 單元測試 | 19 | ✅ 全部通過 |
| PathUtils 前端測試 | 40 | ✅ 全部通過 |

**總計：102 個測試全部通過**

### 前端遷移完成（2026-01-16）

已遷移的檔案：
- `image-viewer.js` - 圖片載入改用 PathUtils
- `text-viewer.js` - 文字檔載入改用 PathUtils
- `pdf-viewer.js` - PDF 載入改用 PathUtils
- `file-manager.js` - 側邊預覽（圖片/文字）改用 PathUtils
- `path-utils.js` - 新增檔案管理器虛擬路徑支援

PathUtils 新增支援：
- `/擎添共用區/在案資料分享/xxx` → `shared://xxx`
- `/擎添共用區/CTOS資料區/xxx` → `ctos://xxx`

### Phase 4: NAS Zone 支援（2026-01-16）

新增 NAS zone 支援檔案管理器的 SMB 共享存取：

後端：
- `path_manager.py` - 新增 `StorageZone.NAS`，支援 `/home/...` 等 NAS 共享路徑
- `files.py` - 新增 `/api/files/nas/{path}` 端點，透過 SMB 讀取檔案

前端：
- `path-utils.js` - 新增 NAS zone 識別
- `file-manager.js` - 改用 `PathUtils.toApiUrl()` 統一路徑處理

路徑格式：
- `/home/xxx.jpg` → `nas://home/xxx.jpg` → `/api/files/nas/home/xxx.jpg`
- 舊的 `nas://knowledge/...` 格式保持向後相容，轉換為 `ctos://...`

### 舊格式資料遷移（2026-01-16）

執行 `backend/scripts/migrate_paths_to_new_format.py` 完成資料遷移：

- 知識庫 markdown 檔案：3 個檔案，24 個路徑轉換
- 資料庫 project_attachments：6 筆記錄更新

轉換規則：
- `nas://knowledge/attachments/xxx` → `ctos://knowledge/xxx`
- `nas://linebot/files/xxx` → `ctos://linebot/xxx`
- `nas://projects/attachments/xxx` → `ctos://projects/attachments/xxx`
- `../assets/images/xxx` → `local://knowledge/images/xxx`

### MCP 工具路徑修復（2026-01-16）

修復 `search_nas_files` 返回格式問題：
- 原本返回 `/{rel_path}`（如 `/陶式/擎添資料/三橋簡報.pptx`）
- PathManager 誤解析為 NAS zone（無本地掛載點）
- 修改為返回 `shared://{rel_path}` 格式
- 現在 `read_document` 和 `convert_pdf_to_images` 可正確讀取 SHARED 區檔案
