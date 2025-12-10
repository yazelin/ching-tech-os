# Tasks: add-backend-nas-auth

## Section 1: 基礎設施建置

- [x] 1.1 建立 `docker/docker-compose.yml` 設定 PostgreSQL 容器
- [x] 1.2 建立 `docker/.env.example` 環境變數範例檔
- [x] 1.3 建立 `docker/init.sql` 初始化 users 表
- [x] 1.4 測試 PostgreSQL 容器可正常啟動並建立表

## Section 2: 後端專案初始化

- [x] 2.1 建立 `backend/` 目錄結構
- [x] 2.2 使用 uv 初始化 Python 專案 (`pyproject.toml`)
- [x] 2.3 安裝核心依賴：FastAPI, uvicorn, python-socketio, smbprotocol, pydantic, psycopg, asyncpg
- [x] 2.4 建立 `src/ching_tech_os/main.py` FastAPI 應用程式入口
- [x] 2.5 建立 `src/ching_tech_os/config.py` 設定檔（NAS IP、DB 連線等）
- [x] 2.6 建立 `src/ching_tech_os/database.py` 資料庫連線管理
- [x] 2.7 測試 FastAPI 服務可啟動 (`uv run uvicorn`)

## Section 3: Session 管理服務

- [x] 3.1 建立 `src/ching_tech_os/models/auth.py` Pydantic models
- [x] 3.2 建立 `src/ching_tech_os/services/session.py` Session 管理
- [x] 3.3 實作 session 建立、取得、刪除功能
- [x] 3.4 實作 session 過期清理背景任務

## Section 4: SMB 連線服務

- [x] 4.1 建立 `src/ching_tech_os/services/smb.py` SMB 服務
- [x] 4.2 實作 SMB 認證測試功能（驗證帳密是否正確）
- [x] 4.3 實作列出共享資料夾功能
- [x] 4.4 實作瀏覽資料夾內容功能
- [x] 4.5 測試 SMB 服務與 NAS 連線

## Section 5: 認證 API

- [x] 5.1 建立 `src/ching_tech_os/api/auth.py` 認證路由
- [x] 5.2 建立 `src/ching_tech_os/services/user.py` 使用者服務
- [x] 5.3 實作 `POST /api/auth/login` 登入 API（含使用者記錄）
- [x] 5.4 實作 `POST /api/auth/logout` 登出 API
- [x] 5.5 實作 token 驗證 middleware/dependency
- [x] 5.6 測試登入/登出 API（確認 users 表有記錄）

## Section 6: NAS 操作 API

- [x] 6.1 建立 `src/ching_tech_os/api/nas.py` NAS 路由
- [x] 6.2 實作 `GET /api/nas/shares` 列出共享資料夾
- [x] 6.3 實作 `GET /api/nas/browse` 瀏覽資料夾內容
- [x] 6.4 測試 NAS API（需先登入取得 token）

## Section 7: 前端整合

- [x] 7.1 修改 `frontend/js/login.js` 呼叫真實登入 API
- [x] 7.2 實作 token 儲存（localStorage）
- [x] 7.3 修改 `frontend/js/header.js` 登出呼叫真實 API
- [x] 7.4 處理 API 錯誤顯示
- [x] 7.5 端對端測試：登入 → 進入桌面 → 登出

## Section 8: 文件與清理

- [x] 8.1 建立 `backend/README.md` 說明如何啟動開發環境
- [x] 8.2 清理測試用程式碼
- [x] 8.3 確認所有功能正常運作

---

## Verification Checklist
- [x] `docker compose up -d` 可啟動 PostgreSQL 並建立 users 表
- [x] `uv run uvicorn ching_tech_os.main:app` 可啟動後端
- [x] 使用 NAS 帳密可成功登入
- [x] 前端登入頁面可正常使用
- [x] 登入後 users 表有該使用者記錄
- [x] 登入後可看到 NAS 共享資料夾列表（API 已實作，前端 UI 待整合）
- [x] 登出後 token 失效
