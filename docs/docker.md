# Docker 服務設定

## 概覽

ChingTech OS 使用 Docker Compose 管理以下服務：
- **PostgreSQL** - 資料庫
- **code-server** - Web-based VS Code

## 檔案結構

```
docker/
├── docker-compose.yml            # 服務定義（單租戶模式）
├── docker-compose.multi-tenant.yml  # 多租戶模式 override
├── init.sql                      # 資料庫初始化（僅基本表）
├── .env.example                  # 環境變數範例
├── .env                          # 環境變數（不進入 git）
├── code-server.gitconfig         # code-server 的 Git 設定
└── code-server.git-credentials   # code-server 的 Git 憑證
```

---

## 快速開始

### 1. 設定環境變數

```bash
cd docker
cp .env.example .env
# 編輯 .env 設定密碼
```

### 2. 啟動服務

```bash
docker compose up -d
```

### 3. 檢查狀態

```bash
docker compose ps
docker compose logs -f
```

### 4. 停止服務

```bash
docker compose down
```

---

## 服務說明

### PostgreSQL

| 項目 | 值 |
|------|---|
| Image | `postgres:16-alpine` |
| Container | `ching-tech-os-db` |
| Port | `5432` |
| Volume | `postgres_data` |

**環境變數：**

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `DB_USER` | `ching_tech` | 資料庫使用者 |
| `DB_PASSWORD` | `REMOVED_PASSWORD` | 資料庫密碼 |
| `DB_NAME` | `ching_tech_os` | 資料庫名稱 |
| `DB_PORT` | `5432` | 對外埠號 |

**初始化：**

`init.sql` 會在容器首次啟動時執行，建立基本的 `users` 表。

> 注意：其他資料表應透過 Alembic migration 建立，不要修改 `init.sql`。

### code-server

| 項目 | 值 |
|------|---|
| Image | `codercom/code-server:latest` |
| Container | `ching-tech-os-code` |
| Port | `8443` (對外) → `8080` (內部) |
| Volume | `code_server_data` |

**掛載目錄：**

| 主機路徑 | 容器路徑 | 說明 |
|----------|----------|------|
| `$HOME/SDD` | `/home/coder/SDD` | 專案目錄 |
| `code_server_data` | `/home/coder/.local` | 擴充功能和設定 |
| `code-server.gitconfig` | `/home/coder/.gitconfig` | Git 設定 |
| `code-server.git-credentials` | `/home/coder/.git-credentials` | Git 憑證 |

**存取方式：**

- URL: `http://localhost:8443`
- 認證: 無（auth: none）

**工作目錄：**

預設開啟 `/home/coder/SDD/ching-tech-os`

---

## docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: ching-tech-os-db
    environment:
      POSTGRES_USER: ${DB_USER:-ching_tech}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-REMOVED_PASSWORD}
      POSTGRES_DB: ${DB_NAME:-ching_tech_os}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "${DB_PORT:-5432}:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-ching_tech} -d ${DB_NAME:-ching_tech_os}"]
      interval: 10s
      timeout: 5s
      retries: 5

  code-server:
    image: codercom/code-server:latest
    container_name: ching-tech-os-code
    command: ["--auth", "none", "--bind-addr", "0.0.0.0:8080"]
    volumes:
      - ${HOME}/SDD:/home/coder/SDD
      - code_server_data:/home/coder/.local
      - ./code-server.gitconfig:/home/coder/.gitconfig:ro
      - ./code-server.git-credentials:/home/coder/.git-credentials:rw
    ports:
      - "${CODE_PORT:-8443}:8080"
    restart: unless-stopped
    working_dir: /home/coder/SDD/ching-tech-os

volumes:
  postgres_data:
  code_server_data:
```

---

## 環境變數

### .env.example

```bash
# PostgreSQL 設定
DB_USER=ching_tech
DB_PASSWORD=your_secure_password_here
DB_NAME=ching_tech_os
DB_PORT=5432

# code-server 設定
CODE_PORT=8443
```

---

## 多租戶模式

ChingTech OS 支援多租戶部署模式，允許多個組織在同一系統上運作。

### 啟用方式

**方法 1：環境變數**

在 `.env` 中設定：

```bash
MULTI_TENANT_MODE=true
DEFAULT_TENANT_ID=00000000-0000-0000-0000-000000000000
```

然後正常啟動：

```bash
docker compose up -d
```

**方法 2：使用 override 檔案**

```bash
docker compose -f docker-compose.yml -f docker-compose.multi-tenant.yml up -d
```

### 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `MULTI_TENANT_MODE` | 是否啟用多租戶模式 | `false` |
| `DEFAULT_TENANT_ID` | 預設租戶 UUID | `00000000-0000-0000-0000-000000000000` |

### 資料庫遷移

首次啟用多租戶模式前，需執行資料庫遷移：

```bash
cd backend
uv run alembic upgrade head
```

遷移會自動將現有資料歸屬到預設租戶。

### 詳細說明

- [多租戶架構](multi-tenant.md) - 完整技術文件
- [租戶管理員操作手冊](tenant-admin-guide.md) - 管理員指南

---

## 常用指令

### 服務管理

```bash
# 啟動所有服務
docker compose up -d

# 停止所有服務
docker compose down

# 重啟特定服務
docker compose restart postgres

# 查看日誌
docker compose logs -f postgres
docker compose logs -f code-server
```

### 資料庫操作

```bash
# 連線到 PostgreSQL
docker compose exec postgres psql -U ching_tech -d ching_tech_os

# 備份資料庫
docker compose exec postgres pg_dump -U ching_tech ching_tech_os > backup.sql

# 還原資料庫
docker compose exec -T postgres psql -U ching_tech ching_tech_os < backup.sql
```

### 清理

```bash
# 停止並移除容器（保留 volumes）
docker compose down

# 停止並移除容器和 volumes（資料會遺失！）
docker compose down -v

# 清理未使用的資源
docker system prune
```

---

## code-server Git 設定

### code-server.gitconfig

```ini
[user]
    name = Your Name
    email = your.email@example.com
[credential]
    helper = store
```

### code-server.git-credentials

```
https://username:token@github.com
```

> 注意：這些檔案不應進入版本控制。

---

## 整合前端程式編輯器

前端的程式編輯器應用程式透過 iframe 載入 code-server：

```javascript
// frontend/js/code-editor.js
function open(windowElement) {
  const iframe = document.createElement('iframe');
  iframe.src = 'http://localhost:8443';
  iframe.style.width = '100%';
  iframe.style.height = '100%';
  iframe.style.border = 'none';

  const contentArea = windowElement.querySelector('.window-content');
  contentArea.appendChild(iframe);
}
```

---

## 故障排除

### PostgreSQL 無法啟動

```bash
# 檢查日誌
docker compose logs postgres

# 常見原因：
# 1. 埠號被佔用 → 修改 DB_PORT
# 2. Volume 權限問題 → docker compose down -v 重建
```

### code-server 無法存取

```bash
# 檢查容器狀態
docker compose ps

# 檢查日誌
docker compose logs code-server

# 常見原因：
# 1. 埠號被佔用 → 修改 CODE_PORT
# 2. 目錄不存在 → 確認 $HOME/SDD 存在
```

### 連線資料庫失敗

```bash
# 確認 PostgreSQL 正在運行
docker compose ps postgres

# 測試連線
docker compose exec postgres pg_isready

# 檢查網路
docker compose exec postgres ping localhost
```

---

## 相關檔案

| 位置 | 說明 |
|------|------|
| `docker/docker-compose.yml` | 服務定義（單租戶模式） |
| `docker/docker-compose.multi-tenant.yml` | 多租戶模式 override |
| `docker/init.sql` | 資料庫初始化 |
| `docker/.env` | 環境變數 |
| `backend/src/ching_tech_os/config.py` | 後端連線設定 |
| `frontend/js/code-editor.js` | code-server 整合 |
| `docs/multi-tenant.md` | 多租戶架構文件 |
| `docs/tenant-admin-guide.md` | 租戶管理員手冊 |
