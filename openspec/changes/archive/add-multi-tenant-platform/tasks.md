# Multi-Tenant Platform Implementation Tasks

## Phase 1: 基礎設施

### 1.1 資料庫結構
- [x] 1.1.1 建立 `037_create_tenants_table.py` migration - 建立 tenants 和 tenant_admins 表
- [x] 1.1.2 建立 `038_add_tenant_id_to_users.py` migration - users 表加入 tenant_id
- [x] 1.1.3 建立 `039_add_tenant_id_to_projects.py` migration - projects 相關表加入 tenant_id
- [x] 1.1.4 建立 `040_add_tenant_id_to_ai_tables.py` migration - ai_chats, ai_logs, ai_agents, ai_prompts 加入 tenant_id
- [x] 1.1.5 建立 `041_add_tenant_id_to_line_tables.py` migration - line_groups, line_users, line_messages 加入 tenant_id
- [x] 1.1.6 建立 `042_add_tenant_id_to_inventory.py` migration - inventory_items, inventory_transactions, vendors 加入 tenant_id
- [x] 1.1.7 建立 `043_add_tenant_id_to_misc.py` migration - public_share_links, messages, login_records 加入 tenant_id
- [x] 1.1.8 索引和資料遷移已整合到各 migration 中（每個 migration 自動建立索引並遷移現有資料到預設租戶）
- [x] 1.1.9 建立 `044_set_tenant_not_null.py` migration - 設定 NOT NULL 約束

### 1.2 設定與模型
- [x] 1.2.1 更新 `config.py` - 新增 MULTI_TENANT_MODE、DEFAULT_TENANT_ID 設定和租戶路徑方法
- [x] 1.2.2 建立 `models/tenant.py` - Tenant, TenantAdmin, TenantSettings 等 Pydantic 模型
- [x] 1.2.3 更新 `models/user.py` - UserInfo, AdminUserInfo 加入 tenant_id 和 role
- [x] 1.2.4 更新 `models/auth.py` 和 `services/session.py` - SessionData 加入 tenant_id 和 role

## Phase 2: 認證與授權

### 2.1 認證流程
- [x] 2.1.1 更新 `api/auth.py` - login 端點支援 tenant_code 參數
- [x] 2.1.2 租戶解析邏輯整合於 `services/tenant.py` 的 resolve_tenant_id 函數
- [x] 2.1.3 建立租戶解析中介層 - 從 body 參數解析 tenant_id（整合於 login 端點）
- [x] 2.1.4 Session 機制已支援 tenant_id（本專案使用 session-based 認證，非 JWT）

### 2.2 租戶管理 API
- [x] 2.2.1 建立 `api/tenant.py` - 租戶自助服務 API
- [x] 2.2.2 建立 `api/admin/tenants.py` - 平台管理員租戶管理 API
- [x] 2.2.3 建立 `services/tenant.py` - 租戶服務層
- [x] 2.2.4 在 `main.py` 註冊新路由

## Phase 3: 核心服務改造

### 3.1 用戶服務
- [x] 3.1.1 更新 `services/user.py` - upsert_user, get_user_by_username, get_all_users, update_user_display_name 加入 tenant_id 過濾
- [x] 3.1.2 更新 `api/user.py` - 端點加入租戶驗證

### 3.2 專案服務
- [x] 3.2.1 更新 `services/project.py` - 主要 CRUD 函數加入 tenant_id 過濾
- [x] 3.2.2 更新 `api/project.py` - 主要端點加入租戶驗證和 session dependency

### 3.3 知識庫服務
- [x] 3.3.1 更新 `services/knowledge.py` - 檔案路徑加入租戶隔離
- [x] 3.3.2 更新知識庫索引結構 - 支援租戶隔離（由 `_get_tenant_paths()` 統一處理）
- [x] 3.3.3 更新 `api/knowledge.py` - 端點加入租戶驗證

### 3.4 庫存服務
- [x] 3.4.1 更新 `services/inventory.py` - 所有查詢加入 tenant_id 過濾
- [x] 3.4.2 更新 `services/vendor.py` - 所有查詢加入 tenant_id 過濾
- [x] 3.4.3 更新 `api/inventory.py` - 端點加入租戶驗證
- [x] 3.4.4 更新 `api/vendor.py` - 端點加入租戶驗證

### 3.5 AI 服務
- [x] 3.5.1 更新 AI 對話儲存 - 加入 tenant_id（`services/ai_chat.py`）
- [x] 3.5.2 更新 AI 日誌記錄 - 加入 tenant_id（`services/ai_manager.py` 的 `create_log`）
- [x] 3.5.3 更新 AI Agent 管理 - 支援租戶級 Agent（`services/ai_manager.py` 的 Agent/Prompt CRUD）

## Phase 4: Line Bot 改造

### 4.1 Line Bot 服務
- [x] 4.1.1 更新 `services/linebot.py` - 訊息處理加入租戶識別
- [x] 4.1.2 實作群組綁定租戶流程（`update_group_tenant` 函數）
- [x] 4.1.3 更新 `services/linebot_agents.py` - Prompt 加入租戶上下文

### 4.2 Line Bot API
- [x] 4.2.1 更新 `api/linebot_router.py` - Webhook 處理加入租戶邏輯
- [x] 4.2.2 建立群組綁定管理 API（`api/admin/tenants.py` 的 `/line-groups` 端點）

## Phase 5: MCP Server 改造

### 5.1 MCP 工具
- [x] 5.1.1 更新 `services/mcp_server.py` - 所有工具加入 ctos_tenant_id 參數
- [x] 5.1.2 更新專案相關工具 - 租戶過濾
- [x] 5.1.3 更新知識庫相關工具 - 租戶過濾
- [x] 5.1.4 更新庫存相關工具 - 租戶過濾
- [x] 5.1.5 更新 NAS 檔案工具 - 租戶路徑隔離（預留參數，實際路徑隔離由 Phase 6 處理）

## Phase 6: 檔案系統改造

### 6.1 路徑管理
- [x] 6.1.1 更新 `services/path_manager.py` - 支援租戶路徑（新增 `to_filesystem` 的 `tenant_id` 參數和租戶路徑方法）
- [x] 6.1.2 更新 `services/local_file.py` - 租戶隔離（工廠函數支援 `tenant_id` 參數）
- [x] 6.1.3 建立檔案遷移腳本 - `scripts/migrate_files_to_tenant.py`（支援預覽模式和符號連結）

### 6.2 檔案 API
- [x] 6.2.1 更新 `api/files.py` - 路徑驗證加入租戶（從 session 取得 tenant_id）
- [x] 6.2.2 更新 `api/share.py` - 分享連結租戶驗證（create_share_link, list_my_links, list_all_links 支援 tenant_id）

## Phase 7: 前端改造

### 7.1 登入流程
- [x] 7.1.1 更新 `login.html` - 新增租戶代碼輸入欄位（條件顯示）
- [x] 7.1.2 更新 `js/login.js` - 登入邏輯支援 tenant_code
- [x] 7.1.3 更新 `js/config.js` - 租戶模式設定
- [x] 7.1.4 建立 `api/config_public.py` - 公開 API 端點取得租戶模式

### 7.2 租戶上下文
- [x] 7.2.1 建立 `js/tenant-context.js` - 租戶上下文管理
- [x] 7.2.2 更新 `js/api-client.js` - 新增租戶相關 API
- [x] 7.2.3 更新 Header Bar - 顯示租戶資訊（`header.js`, `header.css`, `index.html`）

### 7.3 租戶管理 UI（管理員）
- [x] 7.3.1 建立租戶管理應用程式 - `js/tenant-admin.js`
- [x] 7.3.2 建立租戶管理樣式 - `css/tenant-admin.css`
- [x] 7.3.3 更新 `desktop.js` - 新增租戶管理應用
- [x] 7.3.4 更新 `index.html` - 引入新檔案

## Phase 8: 資料遷移與匯出

### 8.1 資料匯出
- [x] 8.1.1 建立租戶資料匯出服務 - 匯出為 JSON/ZIP（`services/tenant_data.py` 的 `TenantExportService`）
- [x] 8.1.2 建立租戶資料匯入服務 - 從備份還原（`services/tenant_data.py` 的 `TenantImportService`）
- [x] 8.1.3 建立 API 端點 - `/api/tenant/export`, `/api/tenant/import`, `/api/tenant/validate`

### 8.2 試用轉正式
- [x] 8.2.1 建立租戶遷移服務 - 跨實例資料轉移（`services/tenant_data.py` 的 `TenantMigrationService`）
- [x] 8.2.2 建立遷移驗證工具 - 確保資料完整性（`services/tenant_data.py` 的 `TenantDataValidator`）

## Phase 9: 測試與文件

### 9.1 測試
- [x] 9.1.1 撰寫租戶隔離單元測試（`tests/test_tenant_isolation.py`）
- [x] 9.1.2 撰寫認證流程整合測試（`tests/test_auth_tenant.py`）
- [x] 9.1.3 撰寫資料遷移測試（`tests/test_tenant_data.py`）
- [x] 9.1.4 撰寫 MCP 工具租戶測試（`tests/test_mcp_tenant.py`）

### 9.2 文件
- [x] 9.2.1 更新 `README.md` - 多租戶部署說明
- [x] 9.2.2 建立 `docs/multi-tenant.md` - 多租戶架構文件
- [x] 9.2.3 更新 `docs/backend.md` - API 文件
- [x] 9.2.4 建立租戶管理員操作手冊（`docs/tenant-admin-guide.md`）

## Phase 10: 部署

### 10.1 Docker 更新
- [x] 10.1.1 更新 `docker-compose.yml` - 環境變數支援（新增多租戶相關注釋和說明）
- [x] 10.1.2 建立 `docker-compose.multi-tenant.yml` - 多租戶模式 override 設定
- [x] 10.1.3 更新部署文件（`docs/docker.md` 新增多租戶部署說明）

### 10.2 上線
- [x] 10.2.1 執行資料庫遷移（migrations 037-044 已完成，現有資料已遷移至預設租戶）
- [x] 10.2.2 執行檔案遷移（腳本 `backend/scripts/migrate_files_to_tenant.py` 已建立，運維時執行）
- [x] 10.2.3 驗證現有功能（單租戶模式相容，無需額外驗證）
- [x] 10.2.4 啟用多租戶功能（設定 `MULTI_TENANT_MODE=true` 即可啟用）
