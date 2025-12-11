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

- **桌面應用程式圖示**
  - 檔案管理（功能已完成）
  - 終端機（開發中）
  - 程式編輯器（開發中）
  - 專案管理（開發中）
  - AI 助手（功能已完成）
  - 訊息中心（開發中）
  - 知識庫（功能已完成）
  - 系統設定（開發中）

- **知識庫系統**
  - 支援 Markdown 格式知識文件
  - YAML Front Matter 元資料管理
  - 多維度標籤分類（專案、角色、主題、難度）
  - ripgrep 全文搜尋
  - Git 版本歷史追蹤
  - NAS 附件儲存整合

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
│   │   ├── taskbar.css     # Taskbar 樣式
│   │   └── knowledge-base.css  # 知識庫樣式
│   ├── js/
│   │   ├── icons.js        # SVG 圖示庫
│   │   ├── login.js        # 登入模組
│   │   ├── header.js       # Header 模組
│   │   ├── desktop.js      # 桌面模組
│   │   ├── taskbar.js      # Taskbar 模組
│   │   └── knowledge-base.js   # 知識庫模組
│   ├── index.html          # 桌面主頁
│   └── login.html          # 登入頁面
├── backend/
│   └── src/ching_tech_os/
│       ├── api/            # FastAPI 路由
│       ├── models/         # Pydantic 模型
│       ├── services/       # 業務邏輯
│       └── main.py         # 應用程式入口
├── data/
│   └── knowledge/
│       ├── entries/        # 知識文件（Markdown）
│       ├── assets/images/  # 小型附件（<1MB）
│       └── index.json      # 知識索引
├── design/
│   └── brand.md            # 品牌設計指南
└── openspec/               # OpenSpec 變更管理
```

## 技術架構

- **前端**：純 HTML5 / CSS3 / JavaScript（Vanilla JS）
- **後端**：Python FastAPI + Pydantic
- **模組化**：使用 IIFE 模式封裝各功能模組
- **狀態管理**：localStorage Session
- **圖示**：內建 SVG 圖示（Material Design Icons 風格）
- **設計系統**：CSS Custom Properties（變數）
- **知識庫**：Markdown + YAML Front Matter、ripgrep 搜尋、Git 版本控制
- **附件儲存**：本機（<1MB）+ NAS（≥1MB）

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

### 啟動後端服務

```bash
cd backend
uv run uvicorn ching_tech_os.main:socket_app --host 0.0.0.0 --port 8089
```

### 登入說明

目前為模擬登入模式，接受任意有效憑證：
- 使用者名稱：至少 2 個字元
- 密碼：至少 4 個字元

## 知識庫

知識庫系統用於集中管理公司技術文件、操作指南與專案知識。

### 知識類型

| 類型 | 說明 |
|------|------|
| `context` | 背景脈絡 - 專案概覽、架構說明 |
| `knowledge` | 領域知識 - 技術細節、協議文件 |
| `operations` | 操作指導 - 開發流程、故障排除 |
| `reference` | 參考文件 - 使用手冊、規格說明 |

### 標籤分類

- **projects**: 所屬專案（rosagv, ching-tech-os, jaba, fish-cv 等）
- **roles**: 適用角色（engineer, pm, manager, all）
- **topics**: 主題標籤（architecture, ros2, troubleshooting 等）
- **level**: 難度等級（beginner, intermediate, advanced）

### API 端點

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/knowledge` | 搜尋/列表知識 |
| GET | `/api/knowledge/{id}` | 取得單一知識 |
| POST | `/api/knowledge` | 新增知識 |
| PUT | `/api/knowledge/{id}` | 更新知識 |
| DELETE | `/api/knowledge/{id}` | 刪除知識 |
| GET | `/api/knowledge/tags` | 取得所有標籤 |
| GET | `/api/knowledge/{id}/history` | 取得版本歷史 |
| POST | `/api/knowledge/{id}/attachments` | 上傳附件 |

### 目前知識內容

系統已整理以下專案的知識：

- **RosAGV** (9 篇): 專案概覽、車型特性、狀態機、ROS 2 介面、PLC 協議、故障排除等
- **ChingTech OS** (2 篇): 專案架構、知識庫使用說明
- **Jaba** (1 篇): 菜單圖片辨識功能設計
- **Jaba LINE Bot** (1 篇): 系統架構
- **Fish-CV** (1 篇): YOLO 魚苗偵測訓練手冊

## 後續規劃

系統以 AI Agent 架構為核心，預計支援：

- 專案流程與 PM 工時管理
- PLC、Python 程式編寫與版本控管
- CI/CD Pipeline 佈署與監控
- LINE Bot 訊息整合與客服支援
- 企業內部資料搜尋與知識整理

## 授權

&copy; 2024 擎添工業 Ching Tech Industrial Co., Ltd.
