# Tasks: 統一檔案檢視器

## 任務列表

### 1. 建立 FileOpener 統一入口
- [x] 建立 `frontend/js/file-opener.js`
- [x] 實作檔案類型判斷邏輯
- [x] 實作 `open()`, `canOpen()`, `getViewerType()` API
- [x] 在 `index.html` 引入

### 2. 建立 PDF Viewer
- [x] 引入 PDF.js 函式庫（CDN）
- [x] 建立 `frontend/js/pdf-viewer.js`
- [x] 在 `frontend/css/viewer.css` 新增 PDF Viewer 樣式
- [x] 實作頁面導航（上/下頁、跳頁）
- [x] 實作縮放功能
- [x] 實作狀態列顯示
- [x] 在 `index.html` 引入

### 3. 重構現有調用處
- [x] 修改 `file-manager.js` - 改用 FileOpener
- [x] 修改 `knowledge-base.js` - 改用 FileOpener

### 4. 調整現有 Viewer 模組
- [x] `ImageViewerModule` - 確認符合統一契約（已符合）
- [x] `TextViewerModule` - 確認符合統一契約（已符合）

### 5. 更新 Specs
- [x] 建立 `file-viewer` spec - FileOpener 統一入口
- [x] 建立 `image-viewer` spec - 從 file-manager 分離
- [x] 建立 `pdf-viewer` spec - PDF 檢視器
- [x] 更新 `file-manager` spec delta - 移除 viewer 相關

### 6. 驗證測試
- [x] 測試從檔案管理開啟各類型檔案
- [x] 測試從知識庫開啟圖片和文字檔
- [x] 測試 PDF 檢視器功能（導航、縮放）
- [x] 測試 `FileOpener.canOpen()` 判斷邏輯
