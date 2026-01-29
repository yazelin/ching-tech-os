## Phase 3 任務清單

### 3.1 訊息儲存基礎設施
- [x] 3.1.1 在 handler.py 加入 `_ensure_bot_user()` — 查找或建立 Telegram bot_user 記錄
  - 查詢 `bot_users WHERE platform_type='telegram' AND platform_user_id=$1`
  - 不存在則 INSERT（display_name 從 `user.full_name` 取得）
  - 驗證：查詢 DB 確認 bot_user 記錄存在
- [x] 3.1.2 在 handler.py 加入 `_save_message()` — 儲存訊息到 bot_messages
  - 用戶訊息和 Bot 回覆都要儲存
  - 包含 message_type（text/image/file）、content、is_from_bot 欄位
  - 驗證：發送訊息後查詢 bot_messages 確認寫入

### 3.2 AI Log 記錄
- [x] 3.2.1 在 `_handle_text_with_ai()` 加入 AI Log 記錄
  - 呼叫 `log_linebot_ai_call`（或抽取的通用版本）
  - context_type 使用 `"telegram-personal"` / `"telegram-group"`
  - 記錄 duration_ms、input/output tokens
  - 驗證：查詢 ai_logs 確認 Telegram 對話有記錄

### 3.3 對話歷史
- [x] 3.3.1 在 AI 處理前查詢對話歷史
  - 呼叫 `get_conversation_context(group_id, user_id, limit=20)`
  - 將歷史傳給 `call_claude(history=history)`
  - 驗證：連續發送多則訊息，AI 能記住前幾則的內容
- [x] 3.3.2 實作 `/reset` 和 `/新對話` 指令的完整版
  - 更新 `bot_users.conversation_reset_at`（而非只發送文字）
  - 驗證：重置後 AI 不記得之前的對話

### 3.4 用戶綁定與存取控制
- [x] 3.4.1 實作驗證碼綁定流程
  - 偵測 6 位數字訊息
  - 查詢 `bot_binding_codes` 驗證
  - 建立/更新 `bot_users` 的 `user_id` 關聯
  - 驗證：發送有效驗證碼後 bot_user 關聯到 CTOS 帳號
- [x] 3.4.2 實作存取控制
  - 未綁定 + 私訊非驗證碼 → 回覆提示綁定訊息
  - 已綁定 → 正常 AI 處理
  - 取得綁定用戶的 app_permissions 用於工具過濾
  - 驗證：未綁定用戶無法使用 AI
- [x] 3.4.3 取得用戶權限用於 system_prompt 和工具過濾
  - 透過 `bot_user.user_id` 查詢 CTOS 帳號的 role 和權限
  - 傳入 `build_system_prompt()` 和工具列表過濾
  - 驗證：不同權限用戶看到不同的工具

### 3.5 群組支援
- [x] 3.5.1 實作群組訊息判斷（是否應該觸發 AI）
  - 檢查 `message.entities` 是否有 mention Bot
  - 檢查 `message.reply_to_message` 是否回覆 Bot
  - 私訊 chat type 為 `private`，群組為 `group`/`supergroup`
  - 驗證：群組中只有 @Bot 或回覆 Bot 才觸發
- [x] 3.5.2 實作 `_ensure_bot_group()` — 查找或建立群組記錄
  - 查詢 `bot_groups WHERE platform_type='telegram' AND platform_group_id=$1`
  - 不存在則 INSERT（group_name 從 chat.title 取得）
  - 驗證：群組記錄正確寫入
- [x] 3.5.3 群組 AI 開關檢查
  - 查詢 `bot_groups.allow_ai_response`
  - false 時靜默忽略
  - 驗證：關閉開關後 Bot 不回應
- [x] 3.5.4 群組中未綁定用戶靜默忽略
  - 不回覆任何提示訊息
  - 驗證：未綁定用戶 @Bot 無反應
- [x] 3.5.5 實作 Bot 加入/離開群組事件處理
  - 監聽 `my_chat_member` Update
  - 加入 → 建立群組記錄
  - 離開 → 標記 inactive
  - 驗證：Bot 加入群組後 bot_groups 有記錄

### 3.6 圖片/檔案接收
- [x] 3.6.1 新增 `media.py` — 圖片下載與儲存
  - `download_telegram_photo(bot, message)` → 下載最高解析度圖片
  - 儲存到 NAS（路徑格式與 Line Bot 一致）
  - 記錄到 `bot_files`
  - 驗證：發送圖片後 NAS 有檔案、bot_files 有記錄
- [x] 3.6.2 新增檔案下載與儲存
  - `download_telegram_document(bot, message)` → 下載 document
  - 儲存到 NAS、記錄到 `bot_files`
  - 驗證：發送檔案後 NAS 有檔案
- [x] 3.6.3 handler.py 整合圖片/檔案處理
  - 收到圖片 → 下載儲存 → 觸發 AI（附帶圖片路徑）
  - 收到檔案 → 下載儲存 → 觸發 AI（附帶檔案路徑，限可讀類型）
  - 驗證：發送圖片後 AI 能描述圖片內容

### 3.7 Telegram 指令
- [x] 3.7.1 實作 `/start` 和 `/help` 指令
  - `/start`：歡迎訊息 + 綁定說明
  - `/help`：功能列表和使用方式
  - 驗證：發送指令後收到正確回覆
- [x] 3.7.2 實作回覆訊息上下文
  - 用戶回覆舊訊息時，查詢被回覆訊息的內容
  - 圖片/檔案：載入暫存路徑供 AI 讀取
  - 文字：加入 `[回覆訊息: ...]` 標註
  - 驗證：回覆一則圖片訊息後 AI 能描述該圖片

### 3.8 測試
- [x] 3.8.1 手動測試：私訊綁定流程
- [x] 3.8.2 手動測試：多輪對話 + 對話重置
- [x] 3.8.3 手動測試：群組 @Bot 觸發
- [x] 3.8.4 手動測試：圖片和檔案接收
- [x] 3.8.5 回歸測試：Line Bot 功能不受影響

### 依賴關係
- 3.1（訊息儲存）是所有後續任務的基礎
- 3.2（AI Log）和 3.3（對話歷史）依賴 3.1
- 3.4（綁定）可與 3.2/3.3 平行，但需要 3.1
- 3.5（群組）依賴 3.4（存取控制）
- 3.6（媒體）依賴 3.1
- 3.7（指令）可與其他任務平行
- 3.8（測試）在全部完成後

### 建議實作順序
1. **3.1** → 訊息儲存基礎
2. **3.2 + 3.3** → AI Log + 對話歷史（平行）
3. **3.4** → 綁定與存取控制
4. **3.7.1** → /start /help 指令（快速完成）
5. **3.5** → 群組支援
6. **3.6** → 圖片/檔案
7. **3.7.2** → 回覆上下文
8. **3.8** → 測試
