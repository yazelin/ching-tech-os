## 1. 資料庫 Migration

- [ ] 1.1 建立 Alembic migration：`bot_settings` 新增預設記錄 `platform='line', key='proactive_push_enabled', value='false'`
- [ ] 1.2 同一 migration：新增 `platform='telegram', key='proactive_push_enabled', value='true'`

## 2. 推送服務核心

- [ ] 2.1 新增 `backend/src/ching_tech_os/services/proactive_push_service.py`，實作 `notify_job_complete(platform, platform_user_id, is_group, group_id, message)` 介面
- [ ] 2.2 `notify_job_complete` 讀取 `bot_settings` 的 `proactive_push_enabled`，Line 缺值視為 `false`，Telegram 缺值視為 `true`
- [ ] 2.3 Line 分支：呼叫 `bot_line/messaging.py` 的 `push_text()`
- [ ] 2.4 Telegram 分支：呼叫 `bot_telegram/adapter.py` 的 `send_text()`
- [ ] 2.5 推送失敗時捕捉例外、記錄 warning log，不重新拋出

## 3. 內部 API 端點

- [ ] 3.1 新增 `POST /api/internal/proactive-push` 路由（限 127.0.0.1 存取）
- [ ] 3.2 端點接收 `job_id`、`skill` 參數，從對應 `status.json` 讀取 `caller_context` 與結果
- [ ] 3.3 實作各 skill 的訊息組裝邏輯：
  - `research-skill`：研究摘要前 500 字 + 原始查詢
  - `media-downloader`：檔案名稱、大小、ctos_path
  - `media-transcription`：逐字稿前 300 字 + ctos_path
- [ ] 3.4 呼叫 `notify_job_complete()` 執行推送
- [ ] 3.5 在 `main.py` 中註冊新路由

## 4. 背景 Skill 整合：research-skill

- [ ] 4.1 修改 `start-research.py`：從 input JSON 讀取 `caller_context` 欄位，寫入 `status.json`
- [ ] 4.2 修改背景研究子行程完成邏輯：寫入 `status: "completed"` 後，POST `/api/internal/proactive-push`（帶 `job_id` 與 `skill="research-skill"`）
- [ ] 4.3 呼叫失敗靜默處理（try/except，不影響任務本身）

## 5. 背景 Skill 整合：media-downloader

- [ ] 5.1 修改 `download-video.py`：從 input JSON 讀取 `caller_context` 欄位，寫入 `status.json`
- [ ] 5.2 修改背景下載程序完成邏輯：寫入 `status: "completed"` 後，POST `/api/internal/proactive-push`（帶 `job_id` 與 `skill="media-downloader"`）
- [ ] 5.3 呼叫失敗靜默處理

## 6. 背景 Skill 整合：media-transcription

- [ ] 6.1 修改 `transcribe.py`：從 input JSON 讀取 `caller_context` 欄位，寫入 `status.json`
- [ ] 6.2 修改背景轉錄程序完成邏輯：寫入 `status: "completed"` 後，POST `/api/internal/proactive-push`（帶 `job_id` 與 `skill="media-transcription"`）
- [ ] 6.3 呼叫失敗靜默處理

## 7. AI Prompt 更新

- [ ] 7.1 更新 `linebot_agents.py` 的 system prompt：說明呼叫 `start-research`、`download-video`、`transcribe` 時應附帶 `caller_context`（包含 `platform`、`platform_user_id`、`is_group`、`group_id`）
- [ ] 7.2 更新 Telegram handler 對應的 system prompt（或共用 prompt 範本）
- [ ] 7.3 建立新的 migration 更新資料庫中的 agent prompt

## 8. 前端設定介面

- [ ] 8.1 在 `system-settings.js`（或 Bot 設定相關 JS）的 Line Bot 設定區塊新增主動推送切換開關
- [ ] 8.2 在 Telegram Bot 設定區塊新增主動推送切換開關
- [ ] 8.3 頁面載入時從 `GET /api/admin/bot-settings/{platform}` 讀取 `proactive_push_enabled` 狀態並反映到開關
- [ ] 8.4 開關切換時呼叫 `PUT /api/admin/bot-settings/{platform}` 更新設定

## 9. 後端 API 擴充

- [ ] 9.1 擴充 `PUT /api/admin/bot-settings/{platform}` 支援接收並儲存 `proactive_push_enabled` 欄位
- [ ] 9.2 擴充 `GET /api/admin/bot-settings/{platform}` 回傳包含 `proactive_push_enabled` 欄位

## 10. 測試

- [ ] 10.1 撰寫 `proactive_push_service` 單元測試：啟用/停用時的行為、缺值時的預設行為
- [ ] 10.2 撰寫 `/api/internal/proactive-push` 端點測試：各 skill 的訊息組裝
- [ ] 10.3 撰寫 start script 的 caller_context 讀寫測試（research、media-downloader、media-transcription）
- [ ] 10.4 執行 `uv run pytest` 確認所有測試通過
