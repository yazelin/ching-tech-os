# Tasks: AI 對話持久化與 System Prompt 管理

## 1. Alembic Migration 設定
- [x] 1.1 安裝 alembic 到 pyproject.toml
- [x] 1.2 執行 `alembic init migrations` 建立目錄結構
- [x] 1.3 修改 `alembic.ini` 設定（sqlalchemy.url 從 config 讀取）
- [x] 1.4 修改 `migrations/env.py` 整合 config.py
- [x] 1.5 建立 `001_create_users.py` migration（對應現有 users 表）
- [x] 1.6 建立 `002_create_ai_chats.py` migration（新 ai_chats 表）
- [x] 1.7 更新 `start.sh` 加入 `alembic upgrade head`

## 2. System Prompt 檔案
- [x] 2.1 建立 `data/prompts/` 目錄
- [x] 2.2 建立 `default.md` 預設助手 prompt
- [x] 2.3 建立 `code-assistant.md` 程式碼助手 prompt
- [x] 2.4 建立 `pm-assistant.md` 專案管理助手 prompt
- [x] 2.5 建立 `summarizer.md` 對話壓縮 prompt

## 3. 後端資料模型
- [x] 3.1 建立 `models/ai.py` 定義 Pydantic models
- [x] 3.2 建立 `services/ai_chat.py` 處理對話 CRUD
- [x] 3.3 實作 `get_user_chats()` 取得使用者對話列表
- [x] 3.4 實作 `create_chat()` 建立新對話
- [x] 3.5 實作 `get_chat()` 取得對話詳情
- [x] 3.6 實作 `delete_chat()` 刪除對話
- [x] 3.7 實作 `update_chat_messages()` 更新訊息

## 4. 後端 API 端點
- [x] 4.1 新增 `GET /api/ai/chats` 取得對話列表
- [x] 4.2 新增 `POST /api/ai/chats` 建立新對話
- [x] 4.3 新增 `GET /api/ai/chats/:id` 取得對話詳情
- [x] 4.4 新增 `DELETE /api/ai/chats/:id` 刪除對話
- [x] 4.5 新增 `GET /api/ai/prompts` 取得可用 prompts（掃描檔案）
- [x] 4.6 實作 API 權限驗證（使用者只能存取自己的對話）

## 5. 修改 Claude Agent（自己管理歷史）
- [x] 5.1 移除 `--session-id` / `--resume` 邏輯
- [x] 5.2 新增 `history` 參數，組合完整 prompt
- [x] 5.3 新增 `system_prompt` 參數，傳入 `--system-prompt`
- [x] 5.4 實作讀取 prompt 檔案的函數

## 6. 修改 Socket.IO 事件處理
- [x] 6.1 `ai_chat_event` 事件：從 DB 載入對話歷史
- [x] 6.2 `ai_chat_event` 事件：讀取對應的 system prompt
- [x] 6.3 呼叫 Claude 後：更新 DB 中的 messages
- [x] 6.4 首次訊息時自動更新對話標題

## 7. 前端 API 整合
- [x] 7.1 建立 `api-client.js` 封裝 REST API 呼叫
- [x] 7.2 修改 `ai-assistant.js` 載入對話列表從 API
- [x] 7.3 修改新增對話改用 API
- [x] 7.4 修改刪除對話改用 API
- [x] 7.5 移除 localStorage 相關邏輯
- [x] 7.6 移除 sessionId 相關邏輯

## 8. 前端 Prompt 選擇器
- [x] 8.1 新增 prompt 選擇下拉選單到 toolbar
- [x] 8.2 載入可用 prompts 從 API
- [x] 8.3 建立新對話時可選擇 prompt

## 9. Token 估算與警告
- [x] 9.1 實作 `estimateTokens()` 函數（字數估算）
- [x] 9.2 計算對話總 tokens 並顯示
- [x] 9.3 超過 75% 時顯示警告條
- [x] 9.4 警告條包含「壓縮對話」按鈕

## 10. 對話壓縮功能
- [x] 10.1 後端：新增 `compress_chat` Socket.IO 事件
- [x] 10.2 後端：實作壓縮邏輯（保留最近 10 則，壓縮其餘）
- [x] 10.3 後端：呼叫 Claude 產生摘要
- [x] 10.4 後端：更新 DB messages（摘要 + 保留訊息）
- [x] 10.5 前端：發送 `compress_chat` 事件
- [x] 10.6 前端：顯示「壓縮中...」狀態
- [x] 10.7 前端：收到 `compress_complete` 更新 UI

## 11. 驗證測試
- [x] 11.1 測試 `alembic upgrade head` 成功建立表
- [x] 11.2 測試 `alembic downgrade -1` 可回滾
- [x] 11.3 測試建立/載入/刪除對話
- [x] 11.4 測試訊息持久化（重新整理後仍在）
- [x] 11.5 測試不同使用者對話隔離
- [x] 11.6 測試 system prompt 切換
- [x] 11.7 測試對話歷史上下文（AI 記得之前說過什麼）
- [x] 11.8 測試 token 警告顯示
- [x] 11.9 測試對話壓縮功能
