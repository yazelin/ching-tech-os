# Tasks: 建立 Web 桌面作業系統介面

## 1. 專案結構設定
- [x] 1.1 建立 `frontend/` 目錄結構
- [x] 1.2 建立 CSS 目錄結構 (`frontend/css/`)
- [x] 1.3 建立 JavaScript 目錄結構 (`frontend/js/`)
- [x] 1.4 建立資源目錄結構 (`frontend/assets/icons/`, `frontend/assets/images/`)

## 2. Logo 與品牌資源處理
- [x] 2.1 將 `design/ching-tech-os-text-reference.png` 處理為正方形 Logo
- [x] 2.2 建立 Favicon (從六邊形 Logo 裁切)
- [x] 2.3 將處理後的 Logo 放入 `frontend/assets/images/`

## 3. 登入頁面 (`/login`)
- [x] 3.1 建立 `frontend/login.html` 基本結構（獨立路由頁面）
- [x] 3.2 實作登入表單 UI（使用者名稱、密碼輸入框、登入按鈕）
- [x] 3.3 建立 `frontend/css/login.css` 樣式
- [x] 3.4 建立 `frontend/js/login.js` 模擬登入邏輯
- [x] 3.5 登入成功後導向至 `/desktop` (index.html)
- [x] 3.6 檢查 session，若已登入則自動導向 `/desktop`

## 4. 桌面主畫面 (`/desktop`)
- [x] 4.1 建立 `frontend/index.html` 桌面主頁面（獨立路由頁面）
- [x] 4.2 建立 `frontend/css/main.css` 全域樣式與 CSS Variables
- [x] 4.3 建立 `frontend/css/desktop.css` 桌面區域樣式
- [x] 4.4 檢查 session，若未登入則導向至 `/login`

## 5. Header Bar（標題列）
- [x] 5.1 實作 Header Bar HTML 結構
- [x] 5.2 建立 `frontend/css/header.css` 樣式
- [x] 5.3 實作系統時間顯示功能
- [x] 5.4 實作使用者資訊顯示
- [x] 5.5 實作登出按鈕功能（清除 session 並導向 `/login`）
- [x] 5.6 建立 `frontend/js/header.js` 邏輯

## 6. 桌面區域（Desktop Area）
- [x] 6.1 實作桌面容器 HTML 結構
- [x] 6.2 設計應用程式圖示（App Icon）樣式（使用 MDI 圖示）
- [x] 6.3 建立示範用 App Icons（檔案管理、終端機、程式編輯器、專案管理、AI 助手、訊息中心、知識庫、系統設定）
- [x] 6.4 建立 `frontend/js/desktop.js` 桌面邏輯

## 7. Taskbar/Dock（工作列）
- [x] 7.1 實作 Taskbar HTML 結構
- [x] 7.2 建立 `frontend/css/taskbar.css` 樣式
- [x] 7.3 實作 Dock 風格的應用程式圖示列（使用 MDI 圖示）
- [x] 7.4 建立 `frontend/js/taskbar.js` 邏輯

## 8. 整合與測試
- [x] 8.1 整合所有 CSS 檔案
- [x] 8.2 整合所有 JavaScript 模組
- [x] 8.3 測試登入流程（`/login` → `/desktop`）
- [x] 8.4 測試登出流程（`/desktop` → `/login`）
- [x] 8.5 測試未登入存取 `/desktop` 自動導向 `/login`
- [x] 8.6 測試已登入存取 `/login` 自動導向 `/desktop`
- [x] 8.7 跨瀏覽器相容性測試
