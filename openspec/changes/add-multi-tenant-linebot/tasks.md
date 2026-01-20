# Tasks: 多租戶 Line Bot 架構

## 1. 資料模型與資料庫

- [ ] 1.1 在 `TenantSettings` 新增 Line Bot 憑證欄位
  - `line_channel_id: str | None`
  - `line_channel_secret: str | None`（加密）
  - `line_channel_access_token: str | None`（加密）
- [ ] 1.2 建立加密/解密工具函數（AES-256）
  - 新增 `TENANT_SECRET_KEY` 環境變數
  - `encrypt_credential(value: str) -> str`
  - `decrypt_credential(encrypted: str) -> str`
- [ ] 1.3 建立 Alembic migration 更新 tenants.settings JSON schema
- [ ] 1.4 更新 `TenantInfo` API 回應（不回傳 secret，只回傳是否已設定）

## 2. Webhook 多租戶驗證

- [ ] 2.1 建立租戶 secrets 快取機制
  - 快取所有租戶的 `(channel_id, channel_secret)` 對照表
  - TTL 5 分鐘，有變更時失效
- [ ] 2.2 修改 `get_webhook_parser()` 支援多租戶
  - 新增 `verify_signature_multi_tenant(body, signature) -> tenant_id | None`
  - 遍歷租戶 secrets 驗證
- [ ] 2.3 修改 webhook endpoint
  - 驗證成功後取得 `tenant_id`
  - 將 `tenant_id` 傳遞給後續處理函數
- [ ] 2.4 實作 fallback 機制
  - 所有租戶驗證失敗時使用環境變數 Bot
  - 群組歸屬到 default 租戶

## 3. Line API Client 多租戶支援

- [ ] 3.1 修改 `get_line_api()` 支援指定 access_token
  - `get_line_api(tenant_id: UUID | None = None) -> MessagingApi`
  - 未指定或找不到時使用環境變數 token
- [ ] 3.2 修改所有回覆訊息的程式碼
  - 傳入 `tenant_id` 參數
  - 使用對應租戶的 access_token
- [ ] 3.3 更新 push_message 相關函數

## 4. 群組租戶歸屬

### 4A. 獨立 Bot 模式（自動歸屬）
- [ ] 4A.1 修改 JoinEvent 處理
  - 使用驗證時識別的 `tenant_id`
  - 建立 `line_groups` 時自動設定 `tenant_id`
- [ ] 4A.2 更新群組建立邏輯
  - tenant_id 由 webhook 簽名驗證自動取得

### 4B. 共用 Bot 模式（指令綁定）
- [ ] 4B.1 共用 Bot 加入群組時 `tenant_id = NULL`
- [ ] 4B.2 實作 `/綁定` 指令處理
  - 解析指令格式：`/綁定 {公司代碼}`
  - 驗證發送者已綁定 CTOS 帳號
  - 驗證公司代碼存在
  - 驗證發送者屬於該租戶
  - 更新 `line_groups.tenant_id`
- [ ] 4B.3 未綁定群組的訊息處理
  - 回覆提示：「請先使用 /綁定 公司代碼 綁定此群組」
  - 不觸發 AI 處理
- [ ] 4B.4 實作 `/解綁` 指令（可選）
  - 只有租戶管理員或平台管理員可操作
  - 將 `tenant_id` 設回 NULL

## 5. 租戶管理 UI

- [ ] 5.1 在 `tenant-admin.js` 新增「Line Bot 設定」區塊
  - Channel ID 輸入框
  - Channel Secret 輸入框（密碼類型）
  - Access Token 輸入框（密碼類型）
  - 儲存按鈕
- [ ] 5.2 新增「測試連線」功能
  - 驗證憑證是否正確
  - 顯示 Bot 名稱確認
- [ ] 5.3 顯示目前設定狀態
  - 已設定 / 未設定（使用預設 Bot）
  - 顯示 Channel ID（不顯示 secret）
- [ ] 5.4 在租戶設定 CSS 新增相關樣式

## 6. API 端點

- [ ] 6.1 新增 `PUT /api/tenant/linebot-settings` 端點
  - 租戶管理員可設定 Line Bot 憑證
  - 驗證憑證格式
  - 加密後儲存
- [ ] 6.2 新增 `GET /api/tenant/linebot-settings` 端點
  - 回傳是否已設定、Channel ID
  - 不回傳 secret 和 token
- [ ] 6.3 新增 `POST /api/tenant/linebot-settings/test` 端點
  - 測試憑證是否有效
  - 回傳 Bot 基本資訊

## 7. 測試

- [ ] 7.1 撰寫單元測試：加密/解密函數
- [ ] 7.2 撰寫單元測試：多租戶簽名驗證
- [ ] 7.3 撰寫整合測試：webhook 租戶識別
- [ ] 7.4 撰寫 E2E 測試：租戶設定 Line Bot 後群組自動歸屬

## 8. 文件更新

- [ ] 8.1 更新 `docs/linebot.md` 說明多租戶架構
- [ ] 8.2 更新 `docs/multi-tenant.md` 說明 Line Bot 設定
- [ ] 8.3 建立租戶 Line Bot 設定指南（給租戶管理員看）
