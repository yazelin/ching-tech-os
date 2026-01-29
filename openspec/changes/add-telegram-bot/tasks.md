## Phase 0: 資料庫欄位重命名（前置作業）

- [ ] 0.1 建立 migration `007_rename_line_columns_to_platform.py`
  - `bot_users.line_user_id` → `platform_user_id`
  - `bot_groups.line_group_id` → `platform_group_id`
  - `bot_messages.line_user_id` → `bot_user_id`
  - `bot_messages.line_group_id` → `bot_group_id`
  - `bot_binding_codes.used_by_line_user_id` → `used_by_bot_user_id`
  - `bot_user_memories.line_user_id` → `bot_user_id`
  - `bot_files` 中的 `line_*` 欄位 → `bot_*`
  - 修正唯一索引加入 `platform_type`
  - 新增 `platform_type` 複合索引
- [ ] 0.2 更新所有引用舊欄位名的後端程式碼（SQL query、model）
- [ ] 0.3 更新前端引用的 API 回應欄位名（如有）
- [ ] 0.4 **測試**：Line Bot 回歸測試（確保重命名後功能正常）

## Phase 1: Telegram 基礎架構

- [ ] 1.1 新增 `python-telegram-bot` 依賴到 `pyproject.toml`
- [ ] 1.2 新增 Telegram 設定到 `config.py`
  - `telegram_bot_token`：Bot Token（從 @BotFather 取得）
  - `telegram_webhook_url`：Webhook 公開 URL
  - `telegram_webhook_secret`：Webhook 驗證 secret
- [ ] 1.3 建立 `services/bot_telegram/` 模組
  - `__init__.py`
  - `adapter.py`：實作 BotAdapter + EditableMessageAdapter + ProgressNotifier
  - `webhook.py`：Webhook secret 驗證、Update 解析
  - `handler.py`：事件分發（文字、圖片、檔案、指令、加入群組）
- [ ] 1.4 建立 `api/telegram_router.py`
  - POST `/api/bot/telegram/webhook`
  - 啟動時呼叫 `set_webhook` 註冊 URL
- [ ] 1.5 在 `main.py` 註冊 telegram_router 和初始化
- [ ] 1.6 實作基本文字訊息收發（不含 AI，echo 測試）
- [ ] 1.7 **測試**：TelegramBotAdapter 單元測試
- [ ] 1.8 **測試**：Webhook 路由整合測試

## Phase 2: AI 處理整合

- [ ] 2.1 從 `linebot_ai.py` 抽取共享邏輯到 `bot/processor.py`
  - 存取控制檢查（綁定 + 群組開關）
  - system prompt 組合（Agent + 權限 + 記憶）
  - 對話歷史組合（含圖片/檔案路徑）
  - Claude CLI 呼叫
  - 回應解析（FILE_MESSAGE、nanobanana 圖片、fallback）
- [ ] 2.2 重構 `linebot_ai.py` 改用 `bot/processor.py`
- [ ] 2.3 Telegram handler 整合 `bot/processor.py`
- [ ] 2.4 實作 ProgressNotifier 整合（AI tool 執行狀態即時更新）
- [ ] 2.5 **測試**：AI 處理流程測試
- [ ] 2.6 **測試**：Line Bot 回歸測試（確保重構未破壞）

## Phase 3: 完整功能

- [ ] 3.1 實作 Telegram 帳號綁定（私訊 Bot 發送驗證碼 → 建立 platform_type='telegram' 的 bot_user）
- [ ] 3.2 實作存取控制（未綁定拒絕、群組 allow_ai_response 開關）
- [ ] 3.3 實作圖片訊息接收（下載圖片、儲存到 NAS、記錄到 bot_files）
- [ ] 3.4 實作檔案訊息接收（下載檔案、儲存到 NAS、記錄到 bot_files）
- [ ] 3.5 實作回覆訊息上下文（回覆圖片/檔案時載入到暫存供 AI 讀取）
- [ ] 3.6 實作群組 @Bot 觸發（Telegram 天然支援 @username）
- [ ] 3.7 實作 Telegram 指令：`/start`、`/help`、`/reset`（對話重置）
- [ ] 3.8 **測試**：綁定、存取控制、媒體處理測試

## Phase 4: 前端管理

- [ ] 4.1 Bot 管理 App 新增平台篩選器（全部 / Line / Telegram）
- [ ] 4.2 群組列表、用戶列表顯示平台圖示
- [ ] 4.3 綁定頁面支援多平台狀態（Line 和 Telegram 各自的綁定狀態）
- [ ] 4.4 記憶管理支援 Telegram 群組/用戶

## Phase 5: 文件與部署

- [ ] 5.1 新增 `docs/telegram-bot.md`
- [ ] 5.2 更新 `docs/backend.md` API 參考
- [ ] 5.3 更新 `README.md` 功能總覽
- [ ] 5.4 `.env.example` 新增 Telegram 設定項
- [ ] 5.5 Nginx 設定：proxy `/ctos/api/bot/telegram/webhook`

### 依賴關係
- Phase 0 必須最先完成（後續都依賴正確的欄位名）
- Phase 1 依賴 Phase 0
- Phase 2 依賴 Phase 1
- Phase 3 依賴 Phase 2
- Phase 4 可與 Phase 3 平行開發
- Phase 5 在 Phase 3 之後
