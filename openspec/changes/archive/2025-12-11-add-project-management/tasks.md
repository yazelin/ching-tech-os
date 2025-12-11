# Tasks: 專案管理應用實作

## 1. 資料庫設計與建立

- [x] 1.1 設計專案資料表結構 (projects)
- [x] 1.2 設計專案成員資料表 (project_members)
- [x] 1.3 設計會議記錄資料表 (project_meetings)
- [x] 1.4 設計專案附件資料表 (project_attachments)
- [x] 1.5 設計專案連結資料表 (project_links)
- [x] 1.6 更新 docker/init.sql 建立資料表

## 2. 後端 API 開發

- [x] 2.1 建立專案資料模型 (models/project.py)
- [x] 2.2 建立專案服務層 (services/project.py)
- [x] 2.3 實作專案 CRUD API
- [x] 2.4 實作專案成員管理 API
- [x] 2.5 實作會議記錄 CRUD API
- [x] 2.6 實作附件上傳/下載 API（本機 + NAS）
- [x] 2.7 實作連結管理 API（自動識別 NAS/外部連結）
- [x] 2.8 註冊路由至 main.py

## 3. 前端視窗開發

- [x] 3.1 建立專案管理模組 (project-management.js)
- [x] 3.2 實作左側專案列表面板
- [x] 3.3 實作右側專案詳情面板
- [x] 3.4 實作專案編輯表單
- [x] 3.5 實作標籤頁切換 (概覽/成員/會議/附件/連結)
- [x] 3.6 整合 desktop.js 視窗建立

## 4. 專案功能模組

- [x] 4.1 實作專案成員管理 UI
- [x] 4.2 實作會議記錄編輯器 (Markdown)
- [x] 4.3 實作附件上傳/預覽功能
- [x] 4.4 實作附件預覽器（圖片/PDF iframe 預覽）
- [x] 4.5 實作連結管理 UI（NAS 連結開啟檔案管理器）

## 5. 樣式與整合

- [x] 5.1 建立專案管理 CSS (project-management.css)
- [x] 5.2 更新 index.html 載入模組
- [x] 5.3 測試完整功能流程
