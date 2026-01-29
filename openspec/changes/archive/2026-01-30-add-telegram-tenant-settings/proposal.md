# add-telegram-tenant-settings

## Summary

新增 Telegram Bot 的租戶級設定管理，對齊現有 Line Bot 的多租戶架構。目前 Telegram Bot 只能透過全域環境變數設定，租戶管理和平台管理 UI 中完全缺少 Telegram 的設定介面。

## Problem

Line Bot 已有完整的多租戶設定架構：
- `TenantSettings` model 有 `line_channel_id`、`line_channel_secret`、`line_channel_access_token`
- 後端有 `GET/PUT/POST/DELETE /api/tenant/bot` 和 `/api/admin/tenants/{id}/bot` API
- 前端平台管理有 "Line Bot" tab，租戶管理有 Line Bot 設定表單
- 憑證加密儲存、測試連線功能完備

Telegram Bot 完全沒有對應的設定：
- `TenantSettings` 無 Telegram 欄位
- 沒有 API endpoints
- 平台管理和租戶管理 UI 沒有 Telegram 設定
- 只能透過全域環境變數 `TELEGRAM_BOT_TOKEN` 設定

## Scope

### 後端
- `models/tenant.py` — 新增 `TenantSettings` Telegram 欄位與 request/response models
- `services/tenant.py` — 新增 Telegram 憑證的加密/解密/取得/更新函式
- `api/tenant.py` — 新增 `/api/tenant/telegram-bot` CRUD + 測試 API
- `api/admin/tenants.py` — 新增 `/api/admin/tenants/{id}/telegram-bot` CRUD + 測試 API

### 前端
- `platform-admin.js` — 新增 "Telegram Bot" tab 及設定表單
- `tenant-admin.js` — 新增 Telegram Bot 設定區塊

### 不在範圍內
- Telegram 多租戶 webhook 路由（各租戶獨立 Bot token 的 webhook 分流）— 這需要另一個 proposal 處理
- 目前先支援「設定 + 儲存 + 測試連線」，實際的多租戶 adapter 切換後續處理

## Design

### 資料模型

在 `TenantSettings` 新增：
```python
# Telegram Bot 設定（多租戶支援）
telegram_bot_token: str | None = None      # 加密儲存
telegram_admin_chat_id: str | None = None  # 管理員 Chat ID
```

### API 設計

完全對照 Line Bot 的 API 模式：

| Method | 平台管理路由 | 租戶管理路由 | 說明 |
|--------|-------------|-------------|------|
| GET | `/api/admin/tenants/{id}/telegram-bot` | `/api/tenant/telegram-bot` | 取得設定（不含敏感資訊） |
| PUT | `/api/admin/tenants/{id}/telegram-bot` | `/api/tenant/telegram-bot` | 更新設定 |
| POST | `/api/admin/tenants/{id}/telegram-bot/test` | `/api/tenant/telegram-bot/test` | 測試連線（呼叫 Telegram getMe API） |
| DELETE | `/api/admin/tenants/{id}/telegram-bot` | `/api/tenant/telegram-bot` | 清除設定 |

### 前端 UI

- 平台管理：在租戶詳情彈窗新增 "Telegram Bot" tab，表單包含 Bot Token、Admin Chat ID
- 租戶管理：在設定頁面新增 Telegram Bot 設定區塊，與 Line Bot 區塊並列

### 憑證安全

- `telegram_bot_token` 使用現有的 `encrypt_credential()` / `decrypt_credential()` 加密儲存
- API 回應中不返回 token 明文，只返回 `configured: bool`
- 更新時空字串表示不更新該欄位

## Risks

- 低風險：完全平行於現有 Line Bot 設定架構，不影響既有功能
- 測試連線使用 Telegram Bot API 的 `getMe` 方法驗證 token 有效性
