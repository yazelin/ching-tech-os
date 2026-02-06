## Why

目前系統採用 Shared Database + Row-Level 的多租戶架構，所有資料表都有 `tenant_id` 欄位。然而隨著 ERPNext 整合及未來更多外部系統（知識庫、其他 ERP）的整合需求，這種架構帶來以下問題：

1. **客製整合互相影響**：每個租戶可能需要整合不同的外部系統（擎添用 ERPNext、客戶 B 可能用 SAP），這些整合不應該影響其他租戶的程式碼
2. **程式複雜度高**：所有查詢都要記得帶 `tenant_id`，遺漏會造成資料洩漏
3. **部署缺乏彈性**：無法為特定客戶獨立部署、獨立客製
4. **平台化不是目標**：我們不打算做 SaaS 平台，目前只有 2 個租戶

改為**單一租戶 + 獨立實例部署**模式，每個客戶部署獨立的 CTOS 實例，外部整合以擴充套件方式處理。

## What Changes

### 資料庫變更
- **BREAKING** 移除所有 23 張表的 `tenant_id` 欄位
- **BREAKING** 刪除 `tenants` 表
- **BREAKING** 刪除 `tenant_admins` 表
- 分區表（ai_logs, messages, login_records）改為只按時間分區
- 移除所有 `(tenant_id, ...)` 複合索引

### 角色系統簡化
- **BREAKING** 移除 `platform_admin` 角色
- **BREAKING** 移除 `tenant_admin` 角色
- 只保留 `admin` 和 `user` 兩種角色
- 移除跨租戶權限檢查邏輯

### 後端程式碼移除
- 刪除 `services/tenant.py`（~500 行）
- 刪除 `api/tenant.py`（~400 行）
- 刪除 `api/admin/tenants.py`（~600 行）
- 刪除 `models/tenant.py`（~100 行）
- 簡化 `api/auth.py` 的租戶解析邏輯
- 移除所有服務層的 `tenant_id` 參數
- 移除 MCP 工具的 `ctos_tenant_id` 參數

### Bot 憑證管理變更
- 移除多租戶憑證加密儲存機制（從 `tenants` 表的 `line_credentials`、`telegram_credentials` 欄位）
- 改為獨立的 `bot_settings` 表 + 環境變數 fallback
- **保留並遷移** 現有 UI 設定介面
  - 從 `/api/tenant/bot` 遷移到 `/api/admin/bot-settings/line`
  - 從 `/api/tenant/telegram-bot` 遷移到 `/api/admin/bot-settings/telegram`

### 前端程式碼變更
- 移除登入頁面的租戶代碼輸入
- **重構** `tenant-admin.js`：抽取 Bot 設定 UI 到獨立模組 `bot-settings.js`
- 刪除 `platform-admin.js`
- 移除桌面上的租戶/平台管理 App
- 保留 Bot 設定功能在系統設定中（admin 專用）

### 檔案系統路徑簡化
- 移除 `/tenants/{tenant_id}/` 層級
- 改為 `/mnt/nas/ctos/knowledge/`、`/mnt/nas/ctos/linebot/` 等

### 配置與環境變數
- 移除 `MULTI_TENANT_MODE` 環境變數
- 移除 `DEFAULT_TENANT_ID` 環境變數
- 移除 `TENANT_SECRET_KEY` 環境變數
- 新增 `LINE_CHANNEL_ACCESS_TOKEN`、`LINE_CHANNEL_SECRET` 環境變數

### 資料遷移
- 保留 `chingtech` 租戶的所有資料
- 移除其他測試租戶資料
- 移除 `tenant_id` 欄位但保留其他資料

## Capabilities

### New Capabilities
（無新增，Bot 設定 UI 已存在，只是遷移端點）

### Modified Capabilities
- `backend-auth`: 移除多租戶登入流程、簡化角色系統為 admin/user
- `bot-platform`: 移除 tenant_id 相關欄位和邏輯
- `line-bot`: 遷移憑證管理（從 tenants 表到 bot_settings 表），API 端點從 `/api/tenant/bot` 遷移到 `/api/admin/bot-settings/line`

## Impact

### 後端檔案
- `backend/src/ching_tech_os/services/tenant.py` - 刪除
- `backend/src/ching_tech_os/api/tenant.py` - 刪除
- `backend/src/ching_tech_os/api/admin/tenants.py` - 刪除
- `backend/src/ching_tech_os/models/tenant.py` - 刪除
- `backend/src/ching_tech_os/models/auth.py` - 移除 tenant_id
- `backend/src/ching_tech_os/api/auth.py` - 大幅簡化
- `backend/src/ching_tech_os/services/user.py` - 移除 tenant_id 參數
- `backend/src/ching_tech_os/services/ai_*.py` - 移除 tenant_id 參數
- `backend/src/ching_tech_os/services/linebot.py` - 移除多租戶邏輯
- `backend/src/ching_tech_os/services/bot_platform.py` - 移除 tenant_id
- `backend/src/ching_tech_os/services/mcp_server.py` - 移除 ctos_tenant_id
- `backend/src/ching_tech_os/config.py` - 簡化 PathManager

### 前端檔案
- `frontend/login.html` - 移除租戶代碼輸入
- `frontend/js/login.js` - 移除租戶相關邏輯
- `frontend/js/tenant-admin.js` - 刪除
- `frontend/js/platform-admin.js` - 刪除
- `frontend/js/desktop.js` - 移除租戶管理 App

### 資料庫
- 需要建立新的 migration 移除 tenant_id 欄位
- 需要遷移 chingtech 租戶資料

### API 端點
- 移除 `/api/tenant/*` 所有端點
- 移除 `/api/admin/tenants/*` 所有端點
- 簡化 `/api/auth/login` 請求格式
- 簡化 `/api/user/me` 回應格式

### 文件
- `docs/multi-tenant.md` - 刪除或改為部署指南
- `docs/tenant-admin-guide.md` - 刪除
- `CLAUDE.md` - 移除多租戶相關規則
- `README.md` - 更新架構說明
