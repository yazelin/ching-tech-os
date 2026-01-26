# Tasks: add-md-converter-apps

## Task List

### 1. 建立通用外部應用程式模組
- [x] 建立 `frontend/js/external-app.js`
- [x] 實作 `ExternalAppModule` IIFE 模組
- [x] 提供 `open(config)` 工廠函式
- [x] 支援配置項：appId, title, icon, url, width, height

**驗證**：模組可被其他程式碼呼叫並建立視窗 ✓

### 2. 建立外部應用程式樣式
- [x] 建立 `frontend/css/external-app.css`
- [x] 定義 `.external-app-container` 容器樣式
- [x] 定義 `.external-app-loading` 載入狀態樣式
- [x] 定義 `.external-app-iframe` iframe 樣式
- [x] 定義載入動畫

**驗證**：載入狀態正確顯示，iframe 正確填滿容器 ✓

### 3. 新增桌面應用程式定義
- [x] 在 `desktop.js` 的 `applications` 陣列新增 `md2ppt` 和 `md2doc`
- [x] 為每個應用程式定義 id、name、icon
- [x] 使用 `file-powerpoint` 和 `file-word` 圖示

**驗證**：桌面顯示兩個新應用程式圖示 ✓

### 4. 實作應用程式開啟邏輯
- [x] 在 `desktop.js` 的 `openApp` 函式新增 `md2ppt` case
- [x] 在 `desktop.js` 的 `openApp` 函式新增 `md2doc` case
- [x] 呼叫 `ExternalAppModule.open()` 並傳入對應配置

**驗證**：點擊圖示可開啟對應視窗並載入外部服務 ✓

### 5. 更新 HTML 引入
- [x] 在 `index.html` 引入 `css/external-app.css`
- [x] 在 `index.html` 引入 `js/external-app.js`

**驗證**：頁面載入無錯誤，模組可用 ✓

### 6. 新增圖示
- [x] 檢查 `icons.js` 是否有適合的圖示
- [x] 新增 `file-word` 圖示（`file-powerpoint` 已存在）

**驗證**：應用程式圖示正確顯示 ✓

### 7. 整合測試
- [x] 測試 MD2PPT 應用程式開啟和載入
- [x] 測試 MD2Doc 應用程式開啟和載入
- [x] 測試視窗拖曳、縮放、關閉功能
- [x] 測試手機版自動全螢幕

**驗證**：所有功能正常運作 ✓

## 完成的檔案變更

### 新增檔案
- `frontend/js/external-app.js` - 通用外部應用程式模組
- `frontend/css/external-app.css` - 外部應用程式樣式

### 修改檔案
- `frontend/js/desktop.js` - 新增 md2ppt、md2doc 應用程式定義和開啟邏輯
- `frontend/js/icons.js` - 新增 file-word 圖示
- `frontend/index.html` - 引入新的 CSS 和 JS 檔案
