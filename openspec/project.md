# Project Context

## Purpose
Ching-Tech OS 是一個 Web-based 統一工作空間，以 AI Agent 系統架構協助使用者處理各種業務需求。此系統提供類似 NAS 或平板介面的作業系統體驗，整合多種功能於單一介面中。

### 主要目標
- 提供直覺的桌面式操作介面
- 整合 AI Agent 協助完成各項任務
- 統一管理多種業務應用程式

### 預計功能範疇
- 業務處理與管理
- PM 專案管理
- 工程師撰寫 PLC、Python 程式
- CI/CD 管理
- LINEBot 聊天訊息整理
- 資料搜尋與知識內容整理

## Tech Stack

### Frontend
- **HTML5**: 語義化標籤結構
- **CSS3**: 自訂樣式，支援 CSS Variables、Flexbox、Grid
- **JavaScript (ES6+)**: 原生 JavaScript，模組化設計
- **無框架**: 不使用 React、Vue 等前端框架

### Backend (預計)
- **Python**: 主要後端語言
- **uv**: Python 套件管理工具
- **FastAPI**: Web API 框架
- **Socket.IO**: 即時通訊
- **httpx**: HTTP 客戶端

### Database & Infrastructure
- **PostgreSQL**: 主要資料庫
- **Docker**: 容器化部署（資料庫）

## Project Conventions

### Code Style
- JavaScript 使用 ES6+ 模組語法
- CSS 使用 BEM 命名規範或自訂命名規則
- 檔案使用 kebab-case 命名
- JavaScript 類別使用 PascalCase
- 函式與變數使用 camelCase

### Architecture Patterns
- 組件化架構 (使用原生 Web Components 或自訂模組)
- MVC / MVP 模式
- 桌面 OS 模擬架構：
  - Desktop (桌面容器)
  - Taskbar (工作列/Dock)
  - Header Bar (標題列/系統列)
  - Window (視窗管理)
  - App (應用程式)

### File Structure (預計)
```
/
├── frontend/
│   ├── index.html
│   ├── css/
│   │   ├── main.css
│   │   ├── desktop.css
│   │   ├── taskbar.css
│   │   └── components/
│   ├── js/
│   │   ├── main.js
│   │   ├── desktop.js
│   │   ├── taskbar.js
│   │   └── modules/
│   └── assets/
│       ├── icons/
│       └── images/
├── backend/
│   └── (FastAPI 應用)
├── docker/
│   └── docker-compose.yml
└── openspec/
```

### Testing Strategy
- 前端：手動測試 + 瀏覽器開發者工具
- 後端：pytest
- E2E：Playwright (後期導入)

### Git Workflow
- 主分支：main
- 功能分支：feature/[feature-name]
- 修復分支：fix/[fix-name]
- Commit 訊息使用 Conventional Commits 格式

## Domain Context
此系統模擬桌面作業系統的使用體驗，主要概念包括：
- **Desktop**: 主要工作區域，可放置應用程式圖示
- **Taskbar/Dock**: 類似 macOS Dock 或 Ubuntu Dock 的應用程式啟動列（位於畫面下方）
- **Header Bar**: 畫面最上方的標題列，包含系統狀態區域
- **System Tray**: 系統狀態區域（時間、使用者資訊、登出功能）
- **App Icon**: 代表不同功能模組的圖示
- **Window**: 應用程式執行時的視窗容器（後期實作）

## Important Constraints
- 第一階段僅實作前端 UI，不包含後端功能
- 登入功能為模擬實作（不連接真實驗證服務）
- 不使用前端框架，純 HTML/CSS/JavaScript
- 優先支援現代瀏覽器 (Chrome, Firefox, Safari, Edge)
- 響應式設計以支援不同螢幕尺寸

## External Dependencies
- **PostgreSQL** (Docker 容器)
- 後續將整合：
  - AI Agent API
  - FastAPI 後端服務
  - 使用者驗證服務
