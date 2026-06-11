# 開發環境上手指南（Dev Onboarding）

> 給新加入 CTOS 開發的同事。目標：從零到本機跑起後端 + 資料庫 + 前端。
> 本文件只講「跑起來」；架構與改動定位請接著讀 `docs/module-index.md` 與 `docs/extends-module.md`。

## 1. 系統需求

CTOS 的開發腳本（`scripts/*.sh`）與工具鏈以 Linux 為準：

- **Windows 機器**：請使用 **WSL2**（建議 Ubuntu）+ **Docker Desktop**（設定中開啟 WSL2 backend 與對應 distro 的 WSL Integration）。所有指令都在 WSL2 終端機內執行。
- **原生 Linux（Ubuntu/Debian）**：直接照 README 安裝。

必要工具（版本依 `README.md`）：

| 工具 | 最低版本 | 用途 |
|------|---------|------|
| Git | latest | 版本控制（含 submodule） |
| Python | 3.11+ | 後端（由 uv 管理） |
| uv | latest | Python 套件管理 |
| Node.js | 20+（建議 nvm 裝） | 前端建置（esbuild） |
| Docker + Compose v2 | latest | PostgreSQL 16、code-server 容器 |

可選但建議：`gh`（GitHub CLI）。NAS 相關功能另需系統套件 `cifs-utils`、`smbclient`、`ripgrep`、`psmisc`（見 README「系統套件」一節；開發機沒接公司 NAS 也能跑主系統，相關功能不可用而已）。

安裝指令請直接照根目錄 `README.md` 的「安裝指令」區塊執行（uv、nvm、Docker、Claude Code 等）。

## 2. Clone 專案與 submodule

```bash
git clone --recurse-submodules https://github.com/yazelin/ching-tech-os.git
cd ching-tech-os
```

### 沒有 private submodule 權限怎麼辦

`.gitmodules` 中有三個 **private** submodule：

- `extends/his`（ching-tech-his）
- `extends/erpnext`（ching-tech-erpnext）
- `extends/law`（ching-tech-law）

沒有權限時 `--recurse-submodules` 會對拿不到的 repo 報錯。改成先普通 clone，再**逐個**初始化拿得到的：

```bash
git clone https://github.com/yazelin/ching-tech-os.git
cd ching-tech-os
# 有哪個 repo 的權限就初始化哪個，沒有的直接跳過
git submodule update --init extends/his
git submodule update --init extends/law
git submodule update --init extends/erpnext
```

**跳過拿不到的 submodule 不影響主系統**：主系統啟動時掃描 `extends/*/contributes.yaml`，目錄是空的就不會載入該模組；另外 `.env` 的 `ENABLED_MODULES` 也能明確控制啟用哪些模組（見下一節）。`extends/voice` 與 `extends/printer` 是主 repo 內的原生目錄，不是 submodule，所有人都拿得到。

## 3. `.env` 設定

```bash
cp .env.example .env
```

**最小可跑的必填項**（資料庫連線，需與 `docker/docker-compose.yml` 的環境變數一致）：

```bash
DB_HOST=localhost
DB_PORT=5432
DB_USER=ching_tech
DB_PASSWORD=（自訂一組本機開發密碼）
DB_NAME=ching_tech_os
```

docker compose 會用同一份 `.env` 的 `DB_USER` / `DB_PASSWORD` / `DB_NAME` 初始化 PostgreSQL 容器，所以後端與容器自然一致。

其餘項目首次上手**可以維持範本值或留空**，對應功能不可用但主系統照常啟動：

- `NAS_*`：檔案管理、知識庫附件等 NAS 功能（開發機沒 NAS 就先不管）
- `LINE_*` / `TELEGRAM_*`：Bot 整合
- `GEMINI_API_KEY`、`NANOBANANA_*`、`HUGGINGFACE_API_TOKEN` 等：AI 圖片/語音功能
- `ERPNEXT_*`：ERPNext 整合

建議開發機把模組範圍縮小，啟動更快、雜訊更少：

```bash
ENABLED_MODULES=core,knowledge-base,file-manager,ai-agent,skills
```

可用模組清單與說明見 `.env.example` 的「系統設定」區塊。

**注意**：`.env.example` 中 `FRONTEND_DIR`、`PROJECT_ATTACHMENTS_PATH` 預設寫的是 `/home/ct/SDD/ching-tech-os/...`，請改成你自己的 repo 路徑。

**安全規則**：`.env` 已在 `.gitignore`，任何真實密碼、token 都不准寫進文件或 commit。

## 4. 啟動

### 一鍵（建議）

```bash
./scripts/start.sh dev
```

會依序：啟動 Docker 服務（PostgreSQL + code-server）→ `uv sync`（首次）→ `alembic upgrade head` → 以 `--reload` 啟動後端於 8088 port。

### 分步（理解每一步在做什麼）

```bash
# 1. 啟動資料庫（與 code-server）
cd docker && docker compose up -d && cd ..

# 2. 安裝後端依賴 + migration
cd backend
uv sync
uv run alembic upgrade head

# 3. 啟動後端
uv run uvicorn ching_tech_os.main:socket_app --host 0.0.0.0 --port 8088
```

前端建置與啟動（另開終端）：

```bash
# 根目錄與 frontend 各有 package.json
npm install            # 根目錄：esbuild 建置工具
cd frontend && npm install && cd ..
npm run build          # 即 node scripts/build-frontend.mjs

# 簡易靜態伺服器
cd frontend && python3 -m http.server 8080
```

瀏覽器開 `http://localhost:8080`。API 文件在 `http://localhost:8088/docs`（Swagger）/ `http://localhost:8088/redoc`。

## 5. 預設 admin 帳號

預設管理員由 migration `backend/migrations/versions/007_seed_admin_user.py` 建立：使用者名稱 `ct`、角色 `admin`、**首次登入強制變更密碼**（`must_change_password = TRUE`）。

預設密碼請**向管理者索取**，或自行查看 007 migration 內容。本文件不記載密碼。登入後可在「使用者管理」建立自己的帳號。

## 6. 測試與 CI

### 本機跑測試

```bash
cd backend && uv run pytest

# 單一檔案 / 關鍵字
uv run pytest tests/test_bot_api_routes.py -v
uv run pytest -k permissions -v

# 含 coverage（根目錄）
npm run test:backend:cov

# push 前完整檢查（前端 build + 後端 coverage）
npm run ci:check
```

### CI（`.github/workflows/backend-tests.yml`）

- 觸發：push 到 `main`、PR 到 `main`、手動 dispatch
- 內容：Python 3.11 + `uv sync` + pytest coverage
- **CI coverage 門檻：85%**（workflow 的 `COVERAGE_FAIL_UNDER: "85"`，以 `--cov-fail-under` 強制）；CI 會 `--ignore=tests/test_his`（his 是 private submodule，CI 環境拿不到）
- 注意：本機 `npm run test:backend:cov` 的門檻是 90%，比 CI 嚴，過了本機就不會卡 CI

### PR 流程

`main` 不直接 push。流程：

1. 從**最新的** `main` 開短命 branch
2. 開發、本機 `npm run ci:check` 通過
3. 開 PR → CI 綠 → merge
4. merge 後即刪 branch，下一件事再從新的 main 開新 branch

```bash
git push origin <branch-name>
gh run list --limit 5      # 確認 CI 狀態
```

## 7. 常見坑

| 坑 | 說明 / 解法 |
|----|------------|
| repo 放在 `/mnt/c/...`（Windows 路徑） | WSL2 跨檔案系統 I/O 極慢且檔案監看不可靠。repo 請 clone 在 WSL2 自己的檔案系統（如 `~/SDD/ching-tech-os`） |
| Line endings（CRLF） | `scripts/*.sh` 是 bash 腳本，被 Windows 工具改成 CRLF 會出現 `bad interpreter` 之類錯誤。在 WSL2 內設 `git config --global core.autocrlf input`，編輯器用 LF |
| Docker 沒啟動 | 後端啟動報資料庫連線錯誤時，先確認 Docker Desktop 在跑、WSL Integration 有開，再 `cd docker && docker compose ps` 確認 `ching-tech-os-db` 是 running |
| Port 衝突 | 預設佔用 5432（DB）、8443（code-server）、8088（後端）、8080（前端）。DB 與 code-server 的 port 可在 `.env` 用 `DB_PORT` / `CODE_PORT` 改 |
| code-server 掛載路徑 | `docker/docker-compose.yml` 把 `${HOME}/SDD` 掛進容器、工作目錄設 `/home/coder/SDD/ching-tech-os`。repo 不在 `~/SDD/` 下時 code-server 會看不到專案（不影響主系統，可忽略或自行調整 compose） |
| `.env` 範本路徑 | `FRONTEND_DIR`、`PROJECT_ATTACHMENTS_PATH` 預設是 `/home/ct/...`，忘記改會找不到前端目錄 |
| submodule 目錄是空的 | 表示該 submodule 沒初始化。有權限就 `git submodule update --init extends/<name>`；沒權限就確認 `ENABLED_MODULES` 沒列到對應模組即可 |
| voice 模組裝不起來 | 語音模組需要額外依賴：`uv sync --extra voice`（見 `.env.example` 模組清單註記） |
| migration 沒跑 | 啟動後 API 報表格不存在 → `cd backend && uv run alembic upgrade head`。schema 變更一律走 Alembic，`docker/init.sql` 已停用 |

## 下一步

- 架構與「改哪些檔」：`docs/module-index.md`
- extends 外部模組開發：`docs/extends-module.md`
- 專案規範（migration、版本號、CSS 變數、子路徑部署）：根目錄 `CLAUDE.md`
- 測試與 CI 細節：`docs/testing-ci.md`
