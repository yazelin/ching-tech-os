## 1. 資料庫 Migration

- [x] 1.1 建立 Alembic migration：`bot_settings` 新增預設記錄 `platform='line', key='proactive_push_enabled', value='false'`
- [x] 1.2 同一 migration：新增 `platform='telegram', key='proactive_push_enabled', value='true'`

## 2. 推送服務核心

- [x] 2.1 新增 `backend/src/ching_tech_os/services/proactive_push_service.py`，實作 `notify_job_complete(platform, platform_user_id, is_group, group_id, message)` 介面
- [x] 2.2 `notify_job_complete` 讀取 `bot_settings` 的 `proactive_push_enabled`，Line 缺值視為 `false`，Telegram 缺值視為 `true`
- [x] 2.3 Line 分支：呼叫 `bot_line/messaging.py` 的 `push_text()`
- [x] 2.4 Telegram 分支：呼叫 `bot_telegram/adapter.py` 的 `send_text()`
- [x] 2.5 推送失敗時捕捉例外、記錄 warning log，不重新拋出

## 3. 內部 API 端點

- [x] 3.1 新增 `POST /api/internal/proactive-push` 路由（限 127.0.0.1 存取）
- [x] 3.2 端點接收 `job_id`、`skill` 參數，從對應 `status.json` 讀取 `caller_context` 與結果
- [x] 3.3 實作各 skill 的訊息組裝邏輯：
  - `research-skill`：研究摘要前 500 字 + 原始查詢
  - `media-downloader`：檔案名稱、大小、ctos_path
  - `media-transcription`：逐字稿前 300 字 + ctos_path
- [x] 3.4 呼叫 `notify_job_complete()` 執行推送
- [x] 3.5 在 `main.py` 中註冊新路由

## 4. 背景 Skill 整合：research-skill

- [x] 4.1 修改 `start-research.py`：從 input JSON 讀取 `caller_context` 欄位，寫入 `status.json`
- [x] 4.2 修改背景研究子行程完成邏輯：寫入 `status: "completed"` 後，POST `/api/internal/proactive-push`（帶 `job_id` 與 `skill="research-skill"`）
- [x] 4.3 呼叫失敗靜默處理（try/except，不影響任務本身）

## 5. 背景 Skill 整合：media-downloader

- [x] 5.1 修改 `download-video.py`：從 input JSON 讀取 `caller_context` 欄位，寫入 `status.json`
- [x] 5.2 修改背景下載程序完成邏輯：寫入 `status: "completed"` 後，POST `/api/internal/proactive-push`（帶 `job_id` 與 `skill="media-downloader"`）
- [x] 5.3 呼叫失敗靜默處理

## 6. 背景 Skill 整合：media-transcription

- [x] 6.1 修改 `transcribe.py`：從 input JSON 讀取 `caller_context` 欄位，寫入 `status.json`
- [x] 6.2 修改背景轉錄程序完成邏輯：寫入 `status: "completed"` 後，POST `/api/internal/proactive-push`（帶 `job_id` 與 `skill="media-transcription"`）
- [x] 6.3 呼叫失敗靜默處理

## 7. AI Prompt 更新

- [x] 7.1 更新 `linebot_ai.py` 的 `build_system_prompt()`：說明呼叫 `start-research`、`download-video`、`transcribe` 時應附帶 `caller_context`，並在【對話識別】提供具體 JSON 範本
- [x] 7.2 更新 Telegram handler 對應的 system prompt（與 Line 共用 `build_system_prompt()`，已一併處理）
- [x] 7.3 無需額外 migration（caller_context 指示在動態 prompt 部分，非靜態 DB 儲存 prompt）

## 8. 前端設定介面

- [x] 8.1 在 `settings.js` 的 Line Bot 設定區塊新增主動推送切換開關
- [x] 8.2 在 Telegram Bot 設定區塊新增主動推送切換開關（共用 `renderBotPlatformCard`）
- [x] 8.3 頁面載入時從 `GET /api/admin/bot-settings/{platform}` 讀取 `proactive_push_enabled` 狀態並反映到開關
- [x] 8.4 開關切換時呼叫 `PUT /api/admin/bot-settings/{platform}` 更新設定

## 9. 後端 API 擴充

- [x] 9.1 擴充 `PUT /api/admin/bot-settings/{platform}` 支援接收並儲存 `proactive_push_enabled` 欄位
- [x] 9.2 擴充 `GET /api/admin/bot-settings/{platform}` 回傳包含 `proactive_push_enabled` 欄位

## 10. 測試

- [x] 10.1 撰寫 `proactive_push_service` 單元測試：啟用/停用時的行為、缺值時的預設行為（含於現有 test suite）
- [x] 10.2 更新 `/api/admin/bot-settings` 端點測試：涵蓋 `proactive_push_enabled` 讀寫
- [x] 10.3 更新 `build_system_prompt` 測試：驗證 `caller_context` 出現在 group prompt
- [x] 10.4 執行 `uv run pytest` 確認所有相關測試通過（759 passed, 8 skipped）
