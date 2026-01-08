# Tasks: 手機版 UI/UX 改進

## 1. 移除 Dock 列

- [x] 1.1 刪除 `frontend/js/taskbar.js`
- [x] 1.2 刪除 `frontend/css/taskbar.css`
- [x] 1.3 更新 `frontend/index.html` 移除 Dock 相關 HTML 和引用
- [x] 1.4 更新 `frontend/js/window.js` 移除 TaskbarModule 相關呼叫
- [x] 1.5 調整 `frontend/css/desktop.css` 的 desktop-area 高度計算

## 2. 桌面圖示單擊開啟

- [x] 2.1 修改 `frontend/js/desktop.js` 將雙擊事件改為單擊
- [x] 2.2 移除圖示選取狀態相關程式碼
- [x] 2.3 移除 `handleIconClick` 中的選取邏輯

## 3. 手機版視窗全螢幕

- [x] 3.1 在 `frontend/js/window.js` 加入手機判斷邏輯
- [x] 3.2 手機開啟視窗時自動設為全螢幕尺寸
- [x] 3.3 手機上隱藏拖曳、縮放功能
- [x] 3.4 確保關閉按鈕在手機上易於點擊（≥44px）
- [x] 3.5 在 `frontend/css/window.css` 加入手機版樣式

## 4. 簡化視窗控制按鈕

- [x] 4.1 移除最小化按鈕（桌機與手機皆移除）
- [x] 4.2 手機上隱藏最大化按鈕
- [x] 4.3 更新視窗標題列樣式

## 5. 返回桌面功能

- [x] 5.1 在 `frontend/js/header.js` 為 logo 加入點擊事件
- [x] 5.2 點擊 logo 時關閉當前視窗
- [x] 5.3 實作 `history.pushState` 記錄視窗狀態
- [x] 5.4 監聽 `popstate` 事件處理瀏覽器返回

## 6. 響應式調整

- [x] 6.1 在 `frontend/css/main.css` 定義斷點變數
- [x] 6.2 調整桌面圖示在手機上的排列與大小
- [x] 6.3 調整 Header Bar 在手機上的佈局

## 7. 測試與驗證

- [x] 7.1 手機瀏覽器測試完整流程
- [x] 7.2 桌機瀏覽器測試確保無退化
- [x] 7.3 測試瀏覽器返回鍵功能
- [x] 7.4 測試點擊 logo 返回桌面
