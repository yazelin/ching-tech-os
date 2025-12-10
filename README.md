# ChingTech OS

擎添工業的次世代企業級 Web 桌面作業系統介面。

## 專案概述

ChingTech OS 是擎添工業打造的整合式智慧工作空間，以 Web 技術實現類桌面作業系統的使用體驗。系統設計目標是串接業務、專案、工程、AI 與自動化流程，讓所有部門在同一平台協作、執行與追蹤。

## 目前狀態

**開發階段：早期原型**

### 已完成功能

- **登入頁面** (`login.html`)
  - 使用者名稱/密碼登入表單
  - Session 狀態管理
  - 品牌視覺呈現

- **桌面介面** (`index.html`)
  - Header Bar（Logo、系統時間、使用者資訊、登出按鈕）
  - 桌面區域（應用程式圖示）
  - Taskbar / Dock

- **桌面應用程式圖示**（UI 已完成，功能開發中）
  - 檔案管理
  - 終端機
  - 程式編輯器
  - 專案管理
  - AI 助手
  - 訊息中心
  - 知識庫
  - 系統設定

- **UI 基礎建設**
  - 模組化 CSS 架構
  - SVG 圖示系統（MDI 風格）
  - 品牌色票與設計規範
  - 深色主題

## 專案結構

```
ching-tech-os/
├── frontend/
│   ├── assets/
│   │   ├── icons/          # 應用程式圖示
│   │   └── images/         # Logo、背景、Favicon
│   ├── css/
│   │   ├── main.css        # 全域樣式、變數、基礎元件
│   │   ├── login.css       # 登入頁面樣式
│   │   ├── header.css      # Header Bar 樣式
│   │   ├── desktop.css     # 桌面區域樣式
│   │   └── taskbar.css     # Taskbar 樣式
│   ├── js/
│   │   ├── icons.js        # SVG 圖示庫
│   │   ├── login.js        # 登入模組
│   │   ├── header.js       # Header 模組
│   │   ├── desktop.js      # 桌面模組
│   │   └── taskbar.js      # Taskbar 模組
│   ├── index.html          # 桌面主頁
│   └── login.html          # 登入頁面
├── design/
│   └── brand.md            # 品牌設計指南
└── openspec/               # OpenSpec 變更管理
```

## 技術架構

- **前端**：純 HTML5 / CSS3 / JavaScript（Vanilla JS）
- **模組化**：使用 IIFE 模式封裝各功能模組
- **狀態管理**：localStorage Session
- **圖示**：內建 SVG 圖示（Material Design Icons 風格）
- **設計系統**：CSS Custom Properties（變數）

## 品牌色票

| 用途 | 色碼 |
|------|------|
| ChingTech Blue | `#1C4FA8` |
| Deep Industrial Navy | `#0F1C2E` |
| AI Neon Cyan | `#21D4FD` |
| Action Green | `#4CC577` |
| Warning Amber | `#FFC557` |
| Error Red | `#E65050` |

## 開發指南

### 啟動開發環境

由於是純靜態前端，可使用任何靜態伺服器：

```bash
# 使用 Python
cd frontend
python3 -m http.server 8080

# 使用 Node.js
npx serve frontend
```

然後開啟瀏覽器訪問 `http://localhost:8080`

### 登入說明

目前為模擬登入模式，接受任意有效憑證：
- 使用者名稱：至少 2 個字元
- 密碼：至少 4 個字元

## 後續規劃

系統以 AI Agent 架構為核心，預計支援：

- 專案流程與 PM 工時管理
- PLC、Python 程式編寫與版本控管
- CI/CD Pipeline 佈署與監控
- LINE Bot 訊息整合與客服支援
- 企業內部資料搜尋與知識整理

## 授權

&copy; 2024 擎添工業 Ching Tech Industrial Co., Ltd.
