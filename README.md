# ChingTech OS

擎添工業的次世代企業級 Web 桌面作業系統介面。

## 專案概述

ChingTech OS 是擎添工業打造的整合式智慧工作空間，以 Web 技術實現類桌面作業系統的使用體驗。系統以 AI Agent 架構為核心，串接業務、專案、工程、AI 與自動化流程，讓所有部門在同一平台協作、執行與追蹤。

## 功能總覽

| 應用程式 | 狀態 | 說明 |
|----------|------|------|
| 桌面系統 | 完成 | 登入頁面、桌面佈局、視窗管理、Window Snap |
| 檔案管理 | 完成 | NAS 檔案瀏覽、上傳、下載、刪除、搜尋、預覽 |
| 終端機 | 完成 | PTY shell session、WebSocket 即時通訊、多終端機 |
| AI 助手 | 完成 | 對話介面、多對話管理、歷史持久化、Markdown 渲染 |
| AI 管理 | 完成 | Agent 設定、Prompt 管理、AI Log 查詢 |
| 知識庫 | 完成 | Markdown 知識管理、全文搜尋、版本歷史、附件管理 |
| 程式編輯器 | 完成 | code-server 整合（VS Code 體驗） |
| 文字檢視器 | 完成 | Markdown/JSON/YAML/XML 格式化顯示、語法色彩 |
| 專案管理 | 完成 | 專案、成員、會議、附件、連結、里程碑管理 |
| Line Bot | 完成 | 群組管理、訊息記錄、用戶綁定、AI 對話整合 |
| 訊息中心 | 完成 | 系統訊息、登入記錄追蹤、未讀狀態管理 |
| 使用者管理 | 完成 | 使用者列表、功能權限設定（管理員） |
| 系統設定 | 完成 | 亮色/暗色主題切換 |

## 快速開始

### 需求

- Python 3.11+
- uv (Python 套件管理)
- Docker & Docker Compose
- Node.js (選用，用於前端開發伺服器)

### 啟動服務

```bash
# 1. 啟動資料庫
cd docker
docker compose up -d

# 2. 安裝後端依賴並執行 migration
cd backend
uv sync
uv run alembic upgrade head

# 3. 啟動後端服務
uv run uvicorn ching_tech_os.main:socket_app --host 0.0.0.0 --port 8088

# 4. 啟動前端（另開終端）
cd frontend
python3 -m http.server 8080
# 或使用 npx serve frontend
```

然後開啟瀏覽器訪問 `http://localhost:8080`

### 登入說明

使用 NAS SMB 帳號密碼進行登入驗證。

## 技術架構

### 前端
- 純 HTML5 / CSS3 / JavaScript（Vanilla JS）
- IIFE 模組化封裝
- CSS Custom Properties 設計系統

### 後端
- Python FastAPI + Pydantic
- asyncpg (PostgreSQL 非同步驅動)
- Socket.IO (終端機、AI 即時通訊)
- SMB/CIFS (NAS 檔案存取)
- Alembic (資料庫 migration)
- Line Bot SDK v3 (Line Messaging API)
- Claude CLI (AI 對話處理)
- MCP Server (AI 工具整合)

### 基礎設施
- PostgreSQL (Docker 容器)
- code-server (程式編輯器)
- NAS 檔案儲存

## 專案結構

```
ching-tech-os/
├── frontend/
│   ├── index.html          # 桌面主頁
│   ├── login.html          # 登入頁面
│   ├── css/                # 樣式檔案
│   ├── js/                 # JavaScript 模組
│   └── assets/             # 圖片、圖示
├── backend/
│   ├── src/ching_tech_os/  # FastAPI 應用程式
│   ├── migrations/         # Alembic migrations
│   └── pyproject.toml
├── docker/
│   └── docker-compose.yml  # PostgreSQL、code-server
├── data/
│   └── knowledge/          # 知識庫資料
├── docs/                   # 技術文件
│   ├── backend.md          # 後端開發指南
│   ├── database-design.md  # 資料庫設計
│   ├── ai-agent-design.md  # AI Agent 設計
│   └── ...
└── openspec/               # 規格與變更管理
    ├── project.md          # 專案規範
    ├── specs/              # 功能規格
    └── changes/            # 變更提案
```

## 文件

### 開發指南

| 文件 | 說明 |
|------|------|
| [docs/backend.md](docs/backend.md) | 後端開發指南、API 參考 |
| [docs/frontend.md](docs/frontend.md) | 前端開發指南、IIFE 模組 |
| [docs/design-system.md](docs/design-system.md) | CSS 設計系統、變數參考 |

### 架構設計

| 文件 | 說明 |
|------|------|
| [docs/database-design.md](docs/database-design.md) | 資料庫設計、Alembic Migration |
| [docs/ai-agent-design.md](docs/ai-agent-design.md) | AI Agent 架構設計 |
| [docs/ai-management.md](docs/ai-management.md) | AI 管理系統（Agent、Prompt、Log） |
| [docs/realtime.md](docs/realtime.md) | Socket.IO 即時通訊、終端機 PTY |
| [docs/smb-nas-architecture.md](docs/smb-nas-architecture.md) | SMB/NAS 檔案系統架構 |
| [docs/file-manager.md](docs/file-manager.md) | 檔案管理器設計 |
| [docs/linebot.md](docs/linebot.md) | Line Bot 整合設計 |
| [docs/mcp-server.md](docs/mcp-server.md) | MCP Server（AI 工具） |

### 部署與安全

| 文件 | 說明 |
|------|------|
| [docs/docker.md](docs/docker.md) | Docker 服務設定 |
| [docs/security.md](docs/security.md) | 認證、Session、登入追蹤 |

### 規範

| 文件 | 說明 |
|------|------|
| [design/brand.md](design/brand.md) | 品牌與色彩指南 |
| [openspec/project.md](openspec/project.md) | 專案規範與慣例 |

## API 文件

啟動後端後，訪問：
- Swagger UI: http://localhost:8088/docs
- ReDoc: http://localhost:8088/redoc

## 授權

MIT License

Copyright (c) 2024-2025 擎添工業 Ching Tech Industrial Co., Ltd.
