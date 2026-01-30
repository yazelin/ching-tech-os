## 1. 實作 Polling 服務
- [x] 1.1 新增 `services/bot_telegram/polling.py`，實作 polling 迴圈
  - 使用 `python-telegram-bot` 的 `Bot.get_updates()` 配合 long polling
  - 管理 offset 確保不重複處理
  - 錯誤處理與自動重試（含指數退避）
  - 啟動時先 `delete_webhook()` 確保 polling 可用
- [x] 1.2 在 `main.py` lifespan 中啟動 polling task 取代 `setup_telegram_webhook()`，關閉時優雅停止

## 2. 停用 Webhook 相關排程
- [x] 2.1 在 `scheduler.py` 中停用 `check_telegram_webhook_health()` 排程（保留程式碼，僅不註冊）

## 3. 文件更新
- [x] 3.1 更新文件 `docs/telegram-bot.md` 反映新的 polling 架構

## 4. 驗證
- [x] 4.1 測試私人訊息收發
- [x] 4.2 測試群組 @mention 回應
- [x] 4.3 測試圖片/檔案下載與儲存
- [x] 4.4 測試服務重啟後 polling 自動恢復

## 備註
- 舊的 webhook 程式碼（endpoint、setup 函式、config 設定）全部保留不動
- 若需要切回 webhook，只要在 lifespan 改回呼叫 `setup_telegram_webhook()` 並重新啟用排程即可
