## MODIFIED Requirements

### Requirement: Telegram Bot Message Reception
Telegram Bot MUST 使用 polling（`getUpdates`）模式主動向 Telegram API 拉取訊息更新，取代原有的 webhook 被動接收模式。

#### Scenario: 正常 polling 接收訊息
- **WHEN** polling 服務啟動且 Telegram 有新訊息
- **THEN** 系統透過 `getUpdates` 取得更新並交由 `handle_update()` 處理

#### Scenario: 服務啟動時自動開始 polling
- **WHEN** FastAPI 應用程式啟動
- **THEN** 系統自動刪除現有 webhook 並啟動 polling 背景任務

#### Scenario: 服務關閉時優雅停止
- **WHEN** FastAPI 應用程式關閉
- **THEN** polling 任務被取消，當前處理中的訊息完成後才結束

#### Scenario: 網路錯誤自動重試
- **WHEN** polling 過程中發生網路錯誤
- **THEN** 系統以指數退避方式自動重試，不丟失訊息（透過 offset 機制）

## REMOVED Requirements

### Requirement: Telegram Webhook Endpoint
**Reason**: 改用 polling 模式，不再需要接收 Telegram 推送的 webhook endpoint
**Migration**: 移除 `POST /api/bot/telegram/webhook` endpoint 及相關的 secret token 驗證

### Requirement: Telegram Webhook Health Check
**Reason**: Polling 模式不需要 webhook 健康檢查，polling 本身有內建的重試機制
**Migration**: 移除 `check_telegram_webhook_health()` 排程任務
