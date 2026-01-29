# Tasks

## 1. 擴充 TenantSettings model 新增 Telegram 欄位
- 檔案：`backend/src/ching_tech_os/models/tenant.py`
- 在 `TenantSettings` 新增 `telegram_bot_token`、`telegram_admin_chat_id`
- 新增 `TelegramBotSettingsUpdate`、`TelegramBotSettingsResponse`、`TelegramBotTestResponse` models

## 2. 新增 Telegram 憑證加密/解密/管理函式
- 檔案：`backend/src/ching_tech_os/services/tenant.py`
- 擴充 `_encrypt_settings_credentials()` 和 `_decrypt_settings_credentials()` 處理 Telegram 欄位
- 新增 `get_tenant_telegram_credentials()`、`update_tenant_telegram_settings()` 函式

## 3. 新增租戶管理 Telegram Bot API
- 檔案：`backend/src/ching_tech_os/api/tenant.py`
- 新增 `GET/PUT/POST/DELETE /api/tenant/telegram-bot` endpoints
- 測試連線使用 Telegram `getMe` API

## 4. 新增平台管理 Telegram Bot API
- 檔案：`backend/src/ching_tech_os/api/admin/tenants.py`
- 新增 `GET/PUT/POST/DELETE /api/admin/tenants/{id}/telegram-bot` endpoints

## 5. 平台管理前端新增 Telegram Bot tab
- 檔案：`frontend/js/platform-admin.js`
- 在租戶詳情彈窗新增 "Telegram Bot" tab
- 實作設定表單（Bot Token、Admin Chat ID）
- 實作測試連線、儲存、清除功能

## 6. 租戶管理前端新增 Telegram Bot 設定區塊
- 檔案：`frontend/js/tenant-admin.js`
- 在 Line Bot 設定區塊旁新增 Telegram Bot 設定區塊
- 對齊 Line Bot 的 UI 風格與操作流程

## 7. 部署測試
- 部署到 trial 機驗證：
  - 平台管理可設定/測試/清除租戶的 Telegram Bot
  - 租戶管理可設定/測試/清除自己的 Telegram Bot
  - Line Bot 設定不受影響
