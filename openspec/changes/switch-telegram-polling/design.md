## Context
Telegram Bot API 提供兩種接收更新的方式：
1. **Webhook**：Telegram 主動 POST 到指定 URL（目前使用）
2. **Polling**：伺服器主動呼叫 `getUpdates` 拉取更新

目前因為伺服器 IP 會變動（DDNS 環境），webhook 經常失效，健康檢查每 5 分鐘才能修復，中間訊息會延遲。

## Goals / Non-Goals
- **Goals**：
  - 不受 IP / DNS 變動影響，訊息接收穩定
  - 簡化架構，移除 webhook 相關的 public URL、secret 驗證、健康檢查
  - 保持現有訊息處理邏輯不變
- **Non-Goals**：
  - 不需要支援 webhook/polling 雙模式切換
  - 不改變 AI 回應、檔案處理、帳號綁定等功能

## Decisions

### Polling 實作方式：使用 `Bot.get_updates()` 手動管理 long polling 迴圈
- **理由**：專案已使用 `python-telegram-bot` 套件，直接呼叫 `Bot.get_updates()` 配合自行管理的 offset 和指數退避重試，可精確控制行為且與現有 `handle_update()` 無縫銜接
- **替代方案**：使用 `Application.run_polling()` — 內建完整 polling 機制，但需重構 handler 註冊方式，與現有架構不相容

### 架構選擇：獨立 asyncio task 在 FastAPI lifespan 中運行
- **理由**：polling 是一個持續運行的迴圈，適合作為背景任務。放在 lifespan 中可以確保 FastAPI 關閉時一併停止
- **做法**：
  ```python
  # 在 lifespan 中
  polling_task = asyncio.create_task(run_telegram_polling())
  yield
  polling_task.cancel()
  ```

### 訊息處理銜接
- `getUpdates` 回傳的 `Update` 物件格式與 webhook 收到的完全相同
- 現有 `handle_update(update, adapter)` 可直接複用，不需修改

## Risks / Trade-offs
- **延遲略增**：Polling 透過 long polling（timeout 30s），最差情況延遲約 1-2 秒，相比 webhook 即時推送稍慢，但對聊天場景可接受
- **Telegram API 限制**：`getUpdates` 不能與 webhook 同時使用，切換前必須先 `deleteWebhook`
- **持續連線**：Polling 會佔用一個持續的 HTTP 連線，但資源消耗很低

## Migration Plan
1. 先 `deleteWebhook` 清除現有 webhook 設定
2. 部署新版程式碼，啟動 polling
3. 驗證訊息收發正常
4. 移除 `TELEGRAM_WEBHOOK_SECRET` 環境變數（`PUBLIC_URL` 若其他服務還需要則保留）

## Open Questions
- `PUBLIC_URL` 是否僅 Telegram webhook 使用？若 Line Bot 或其他功能也需要，則保留該設定
