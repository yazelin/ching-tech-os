## 1. 準備工作

- [x] 1.1 備份資料庫：`pg_dump ching_tech_os > backup_before_migration.sql`
- [x] 1.2 備份 NAS 檔案：`rsync -av /mnt/nas/ctos/ /backup/ctos/` (跳過，可稍後手動執行)
- [x] 1.3 記錄 chingtech 租戶的 UUID: `fe530f72-f9f5-434c-ba0b-8bc2d6485ca3`
- [x] 1.4 確認現有資料筆數：users=11, ai_agents=7, ai_prompts=8, bot_groups=8, bot_users=20, bot_messages=3785, bot_files=499
- [x] 1.5 記錄現有 Line Bot 憑證：所有租戶皆無資料庫憑證，使用環境變數

## 2. 資料庫遷移

- [x] 2.1 建立 Alembic migration：刪除非 chingtech 租戶資料（所有有 tenant_id 的表）
- [x] 2.2 建立 Alembic migration：從 tenants.settings 遷移 Line/Telegram 憑證到新 bot_settings 表（無現有憑證，跳過）
- [x] 2.3 建立 Alembic migration：移除以下表的 `tenant_id` 欄位
  - users（同時移除 NOT NULL 約束後的資料清理）
  - ai_agents、ai_chats、ai_prompts
  - bot_groups、bot_users、bot_messages、bot_files、bot_binding_codes
- [x] 2.4 建立 Alembic migration：修改分區表結構（ai_logs, messages, login_records）
  - 分區表保留 tenant_id 欄位但移除索引（重建分區表過於複雜）
- [x] 2.5 建立 Alembic migration：刪除 `tenants` 表
- [x] 2.6 建立 Alembic migration：刪除 `tenant_admins` 表
- [x] 2.7 建立 Alembic migration：更新 `users.role` 欄位
  - platform_admin → admin
  - tenant_admin → admin
  - user → user
- [x] 2.8 建立 Alembic migration：新增 `bot_settings` 表
  - id SERIAL PRIMARY KEY
  - platform VARCHAR(20) NOT NULL
  - key VARCHAR(100) NOT NULL
  - value TEXT (加密)
  - updated_at TIMESTAMP
  - UNIQUE(platform, key)
- [x] 2.9 執行 migration 並驗證資料筆數
  - users=11, ai_agents=7, ai_prompts=8, bot_groups=8, bot_users=20 ✓
  - bot_settings 表已建立 ✓
  - users.role 只有 admin/user ✓
  - tenants/tenant_admins 表已刪除 ✓

## 3. 後端 - 移除租戶模組

- [x] 3.1 刪除 `services/tenant.py`（~500 行）✓
- [x] 3.2 刪除 `api/tenant.py`（~1300 行）✓
- [x] 3.3 刪除 `api/admin/tenants.py`（~600 行）✓
- [x] 3.4 刪除 `models/tenant.py` ✓
- [x] 3.5 更新 `main.py`：移除租戶相關路由註冊 ✓
  - 移除 tenant_router
  - 移除 admin_tenants_router

## 4. 後端 - 簡化認證模組

- [x] 4.1 更新 `models/auth.py`：
  - 移除 SessionData 中的 tenant_id 欄位
  - 簡化 role 類型（只有 admin/user）
- [x] 4.2 更新 `api/auth.py`：
  - 移除 `resolve_tenant_id()` 呼叫 ✓
  - 移除登入時的 tenant_code 參數處理 ✓
  - 移除 `require_can_manage_target()` 的跨租戶檢查 ✓
  - 簡化 `get_user_role()` - 只判斷 admin/user ✓
- [x] 4.3 更新 `/api/auth/login` 回應格式：移除 tenant 物件 ✓
- [ ] 4.4 更新 `/api/user/me` 回應格式：移除 tenant 相關欄位
- [ ] 4.5 更新 `services/permissions.py`：
  - 移除 platform_admin 角色
  - 移除 tenant_admin 角色
  - 更新權限檢查邏輯

## 5. 後端 - 新增 Bot 設定 API（從 tenant.py 遷移）

- [ ] 5.1 新增 `services/bot_settings.py`：
  - `get_bot_credentials(platform)` - 優先資料庫，fallback 環境變數
  - `update_bot_credentials(platform, credentials)` - 加密儲存
  - `delete_bot_credentials(platform)`
  - 使用 BOT_SECRET_KEY 環境變數的 Fernet 加密
- [ ] 5.2 新增 `api/admin/bot_settings.py`：
  - `GET /api/admin/bot-settings/line` - 取得設定狀態
  - `PUT /api/admin/bot-settings/line` - 更新憑證
  - `POST /api/admin/bot-settings/line/test` - 測試連線
  - `DELETE /api/admin/bot-settings/line` - 清除憑證
  - 同樣為 telegram 建立端點
- [ ] 5.3 更新 `main.py`：註冊 bot_settings 路由

## 6. 後端 - 更新服務層（移除 tenant_id 參數）

- [~] 6.1 更新 `services/user.py`：（部分完成：upsert_user, get_user_by_username）
  - 移除所有函數的 tenant_id 參數
  - 移除 WHERE tenant_id = ? 條件
- [~] 6.2 更新 `services/ai_manager.py`：（部分完成：get_agent_by_name）
- [ ] 6.3 更新 `services/ai_chat.py`：移除 tenant_id 參數
- [ ] 6.4 更新 `services/ai_log.py`：移除 tenant_id 參數
- [ ] 6.5 更新 `services/bot_platform.py`：
  - 移除 tenant_id 參數
  - 移除 BotContext 中的 tenant_id
- [ ] 6.6 更新 `services/linebot.py`：
  - 移除多租戶憑證邏輯（get_all_tenant_line_secrets 等）
  - 改用 bot_settings.py 的 get_bot_credentials()
  - 移除 invalidate_tenant_secrets_cache()
- [ ] 6.7 更新 `services/telegram.py`：同樣改用 bot_settings.py
- [ ] 6.8 更新 `services/knowledge.py`：移除 tenant_id 參數

## 7. 後端 - 簡化資料匯出/匯入（tenant_data.py）

- [ ] 7.1 更新 `services/tenant_data.py`：
  - 重命名為 `services/data_export.py`
  - 移除租戶相關邏輯
  - 保留為系統備份/還原功能
- [ ] 7.2 更新 `api/admin/` 新增備份 API（可選）

## 8. 後端 - 更新 MCP Server

- [ ] 8.1 更新 `services/mcp_server.py`：
  - 移除所有工具的 `ctos_tenant_id` 參數
  - 移除 `_get_tenant_id()` 輔助函數
  - 更新 search_knowledge、get_knowledge_item 等
  - 更新 search_nas_files、send_nas_file 等
  - 更新 add_note、add_note_with_attachments 等
  - 更新 generate_presentation、generate_md2ppt 等

## 9. 後端 - 更新 API 路由

- [ ] 9.1 更新 `api/admin/users.py`：移除租戶過濾邏輯
- [ ] 9.2 更新 `api/bot.py`：移除 tenant_id 參數
- [ ] 9.3 更新 `api/knowledge.py`：移除 tenant_id 參數
- [ ] 9.4 更新 `api/ai.py`：移除 tenant_id 參數

## 10. 後端 - 路徑管理

- [x] 10.1 更新 `services/path_manager.py`：
  - 移除租戶路徑方法（get_tenant_base_path 等）
  - 新增單一租戶路徑屬性：knowledge_base_path, linebot_base_path 等
- [ ] 10.2 更新所有使用 PathManager 的程式碼

## 11. 後端 - 環境變數

- [ ] 11.1 更新 `config.py`：
  - 移除 MULTI_TENANT_MODE
  - 移除 DEFAULT_TENANT_ID
  - 移除 TENANT_SECRET_KEY
  - 新增 LINE_CHANNEL_ACCESS_TOKEN（fallback 用）
  - 新增 LINE_CHANNEL_SECRET（fallback 用）
  - 新增 BOT_SECRET_KEY（加密 bot_settings 用）
- [ ] 11.2 更新 `.env.example`
- [ ] 11.3 更新實際 `.env` 檔案

## 12. 前端 - 登入頁面

- [ ] 12.1 更新 `login.html`：移除租戶代碼輸入欄位（id="tenant-code"）
- [ ] 12.2 更新 `js/login.js`：
  - 移除 tenantCode 相關邏輯
  - 簡化登入請求（只傳 username/password）

## 13. 前端 - 租戶上下文

- [ ] 13.1 刪除 `js/tenant-context.js`
- [ ] 13.2 更新 `index.html`：移除 tenant-context.js 引入
- [ ] 13.3 搜尋並移除所有 `getTenantId()`、`TenantContext` 的使用

## 14. 前端 - 移除租戶管理 App

- [ ] 14.1 刪除 `js/tenant-admin.js`（Bot 設定 UI 需先遷移到新模組）
- [ ] 14.2 刪除 `js/platform-admin.js`
- [ ] 14.3 更新 `js/desktop.js`：
  - 移除租戶管理 App 註冊
  - 移除平台管理 App 註冊
- [ ] 14.4 更新 `index.html`：移除租戶管理相關 JS 引入

## 15. 前端 - Bot 設定 UI（從 tenant-admin.js 遷移）

- [ ] 15.1 新增 `js/bot-settings.js`：
  - 從 tenant-admin.js 抽取 Bot 設定相關程式碼
  - 更新 API 端點（/api/tenant/bot → /api/admin/bot-settings/line）
  - 包含 Line Bot 和 Telegram Bot 設定
- [ ] 15.2 新增 `css/bot-settings.css`（如需要）
- [ ] 15.3 整合到系統設定 App 或建立獨立 App
- [ ] 15.4 更新 `index.html`：引入新的 JS/CSS

## 16. 前端 - 清理

- [ ] 16.1 搜尋並移除所有前端的 tenant 相關程式碼
- [ ] 16.2 更新 `js/user-admin.js`：移除租戶相關邏輯
- [ ] 16.3 更新角色顯示（platform_admin/tenant_admin → admin）
- [ ] 16.4 檢查 localStorage 是否有 tenant 相關資料需清理

## 17. 檔案系統遷移

- [ ] 17.1 確認 chingtech 租戶的 UUID
- [ ] 17.2 移動租戶檔案到根層級：
  ```bash
  mv /mnt/nas/ctos/tenants/{uuid}/knowledge/* /mnt/nas/ctos/knowledge/
  mv /mnt/nas/ctos/tenants/{uuid}/linebot/* /mnt/nas/ctos/linebot/
  mv /mnt/nas/ctos/tenants/{uuid}/ai-generated/* /mnt/nas/ctos/ai-generated/
  mv /mnt/nas/ctos/tenants/{uuid}/attachments/* /mnt/nas/ctos/attachments/
  ```
- [ ] 17.3 刪除 tenants 目錄：`rm -rf /mnt/nas/ctos/tenants/`
- [ ] 17.4 驗證檔案存取正常

## 18. 文件更新

- [ ] 18.1 刪除 `docs/multi-tenant.md`
- [ ] 18.2 刪除 `docs/tenant-admin-guide.md`
- [ ] 18.3 更新 `CLAUDE.md`：移除多租戶相關規則
- [ ] 18.4 更新 `README.md`：更新架構說明
- [ ] 18.5 更新相關 openspec specs

## 19. 測試與驗證

- [ ] 19.1 測試登入功能（無租戶代碼）
- [ ] 19.2 測試使用者管理功能（admin/user 角色）
- [ ] 19.3 測試 Line Bot webhook 驗證（新憑證來源）
- [ ] 19.4 測試 Bot 設定 UI（新端點）
- [ ] 19.5 測試知識庫功能（新路徑）
- [ ] 19.6 測試 AI 對話功能
- [ ] 19.7 測試 MCP 工具（無 ctos_tenant_id）
- [ ] 19.8 測試檔案存取（新路徑結構）
- [ ] 19.9 測試資料備份/還原功能

## 20. 部署

- [ ] 20.1 設定 BOT_SECRET_KEY 環境變數
- [ ] 20.2 設定 Line Bot 憑證（透過 UI 或環境變數）
- [ ] 20.3 執行資料庫 migration
- [ ] 20.4 執行檔案系統遷移
- [ ] 20.5 重啟後端服務
- [ ] 20.6 清除前端快取
- [ ] 20.7 最終驗證所有功能
