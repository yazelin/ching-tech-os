# Tasks: 檔案管理應用程式

## Section 0: 視窗系統擴充（前置工作）

- [x] 0.1 在 `window.js` 新增最大化功能 `maximizeWindow(windowId)`
- [x] 0.2 新增最大化按鈕到視窗標題列（在最小化和關閉之間）
- [x] 0.3 實作雙擊標題列切換最大化/還原
- [x] 0.4 在 `window.css` 新增 `.window.maximized` 樣式（全螢幕無圓角）
- [x] 0.5 儲存最大化前的位置和大小以便還原

## Section 1: 後端檔案操作 API

- [x] 1.1 擴充 `services/smb.py` 新增 `read_file(share, path)` 方法
- [x] 1.2 擴充 `services/smb.py` 新增 `write_file(share, path, data)` 方法
- [x] 1.3 擴充 `services/smb.py` 新增 `delete_item(share, path, recursive)` 方法（支援遞迴刪除）
- [x] 1.4 擴充 `services/smb.py` 新增 `rename_item(share, old_path, new_name)` 方法
- [x] 1.5 擴充 `services/smb.py` 新增 `create_directory(share, path)` 方法
- [x] 1.6 新增 `GET /api/nas/file` 讀取檔案內容 API
- [x] 1.7 新增 `GET /api/nas/download` 下載檔案 API（回傳 attachment）
- [x] 1.8 新增 `POST /api/nas/upload` 上傳檔案 API
- [x] 1.9 新增 `DELETE /api/nas/file` 刪除檔案/資料夾 API（支援遞迴）
- [x] 1.10 新增 `PATCH /api/nas/rename` 重命名 API
- [x] 1.11 新增 `POST /api/nas/mkdir` 建立資料夾 API
- [x] 1.12 測試所有新增 API

## Section 2: 檔案管理前端視窗

- [x] 2.1 建立 `frontend/css/file-manager.css` 樣式（左側檔案列表 + 右側預覽面板）
- [x] 2.2 建立 `frontend/js/file-manager.js` 模組骨架
- [x] 2.3 實作視窗開啟/關閉邏輯
- [x] 2.4 實作工具列（返回、上一層、重新整理、上傳、新增資料夾）
- [x] 2.5 實作路徑導航列（顯示目前路徑）
- [x] 2.6 實作檔案列表顯示（圖示、名稱、大小、修改日期）
- [x] 2.7 實作資料夾進入（雙擊）
- [x] 2.8 實作單選功能（點擊選取）
- [x] 2.9 實作多選功能（Ctrl+點擊、Shift+點擊範圍選取）
- [x] 2.10 實作右鍵選單（開啟、下載、刪除、重命名）
- [x] 2.11 實作刪除確認對話框（非空資料夾顯示警告）
- [x] 2.12 實作上傳檔案功能
- [x] 2.13 實作下載檔案功能
- [x] 2.14 實作右側預覽面板
- [x] 2.15 實作文字檔預覽（讀取內容顯示前 N 行）
- [x] 2.16 實作圖片預覽（顯示縮圖）
- [x] 2.17 實作狀態列（項目數、選取數）
- [x] 2.18 在 `desktop.js` 修改 file-manager 開啟邏輯
- [x] 2.19 在 `index.html` 引入新的 CSS 和 JS

## Section 3: 獨立檢視器 App

- [x] 3.1 建立 `frontend/css/viewer.css` 共用檢視器樣式
- [x] 3.2 建立 `frontend/js/image-viewer.js` 圖片檢視器模組
- [x] 3.3 實作圖片顯示、縮放（放大/縮小/原始大小）
- [x] 3.4 建立 `frontend/js/text-viewer.js` 文字檢視器模組
- [x] 3.5 實作文字內容顯示、捲動
- [x] 3.6 從檔案管理雙擊開啟對應檢視器
- [x] 3.7 在 `index.html` 引入檢視器 CSS 和 JS

## Section 4: 整合與驗證

- [x] 4.1 測試瀏覽 NAS 資料夾（多層級）
- [x] 4.2 測試右側預覽面板顯示文字檔（txt, md, json）
- [x] 4.3 測試右側預覽面板顯示圖片檔（jpg, png, gif, svg）
- [x] 4.4 測試上傳檔案
- [x] 4.5 測試下載檔案
- [x] 4.6 測試刪除單一檔案
- [x] 4.7 測試遞迴刪除非空資料夾（確認警告對話框）
- [x] 4.8 測試多選刪除
- [x] 4.9 測試重命名檔案和資料夾
- [x] 4.10 測試建立新資料夾
- [x] 4.11 測試雙擊開啟圖片檢視器
- [x] 4.12 測試雙擊開啟文字檢視器
- [x] 4.13 測試無權限資料夾的錯誤處理

---

## Verification Checklist
- [x] 點擊桌面「檔案管理」圖示可開啟視窗
- [x] 可瀏覽 NAS 上使用者有權限的資料夾
- [x] 選取檔案後右側面板顯示預覽
- [x] 文字檔和圖片檔可正確預覽
- [x] 支援 Ctrl+點擊 多選、Shift+點擊 範圍選取
- [x] 可上傳檔案到目前資料夾
- [x] 可下載檔案到本機
- [x] 可刪除檔案和資料夾（非空資料夾顯示警告）
- [x] 可批次刪除多選的檔案
- [x] 可重命名檔案和資料夾
- [x] 可建立新資料夾
- [x] 雙擊圖片開啟圖片檢視器
- [x] 雙擊文字檔開啟文字檢視器
