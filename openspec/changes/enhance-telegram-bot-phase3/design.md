# Design: Telegram Bot Phase 3

## 架構決策

### 決策 1：共用邏輯的抽取策略

**選項 A**：將 `linebot_ai.py` 中的共用函式移到 `bot/processor.py`（原始計畫 Phase 2.1）
- 優點：乾淨的架構，平台無關
- 缺點：大量重構，影響 Line Bot 穩定性

**選項 B**：Telegram handler 直接呼叫 `linebot_ai.py` 中的現有函式
- 優點：最小改動，快速交付
- 缺點：函式名稱帶 `linebot` 前綴但被 Telegram 使用，語義不精確

**選擇 B**：Phase 2 已經採用此策略（handler.py 直接 import `linebot_ai` 的函式），Phase 3 延續此模式。完整的共用核心抽取留給未來獨立重構。

### 決策 2：對話歷史實作方式

Line Bot 的對話歷史依賴 `bot_messages` 表和 `bot_users` 表。Telegram 要使用相同的對話歷史機制，需要：

1. **訊息儲存**：每則 Telegram 訊息（含 bot 回覆）寫入 `bot_messages`
2. **用戶記錄**：Telegram 用戶需要 `bot_users` 記錄（綁定時建立，或首次訊息時建立未綁定記錄）
3. **歷史查詢**：`get_conversation_context` 透過 `platform_user_id` 查詢，天然支援 Telegram

**關鍵**：目前 handler.py 的 `_handle_text_with_ai` 沒有儲存訊息到 `bot_messages`，也沒有查詢歷史。需要加入完整的訊息生命週期。

### 決策 3：未綁定用戶的處理

**方案**：
- 私訊：未綁定用戶發送非驗證碼訊息 → 提示需要綁定
- 群組：未綁定用戶 @Bot → 靜默忽略
- 綁定流程：用戶從 CTOS Web 取得 6 位驗證碼 → 私訊 Bot → 系統驗證並建立 `bot_users` 記錄

### 決策 4：群組訊息觸發機制

Telegram 群組中 Bot 不會收到所有訊息（除非設為 Privacy Mode off）。觸發方式：
1. `@bot_username` mention — Telegram 原生支援
2. 回覆 Bot 的訊息 — `reply_to_message` 欄位
3. `/` 指令 — Telegram 原生支援

**實作**：檢查 `message.entities` 中是否有 `mention` 指向 Bot，或 `reply_to_message` 的 from 是 Bot。

### 決策 5：圖片/檔案下載

Telegram 的圖片和檔案需要：
1. 呼叫 `bot.get_file(file_id)` 取得 `File` 物件
2. 呼叫 `file.download_to_memory()` 下載到記憶體
3. 儲存到 NAS（與 Line Bot 相同的路徑結構）
4. 記錄到 `bot_files` 表

Telegram 圖片有多個解析度（`photo[-1]` 為最高解析度），使用最高解析度版本。

## 資料流

### 私訊文字訊息流程（完整版）
```
Telegram Update
  → handler.handle_update()
  → 查找/建立 bot_user（by platform_user_id + platform_type='telegram'）
  → 檢查綁定狀態
    → 未綁定 + 是驗證碼 → 執行綁定
    → 未綁定 + 非驗證碼 → 提示綁定
    → 已綁定 → 繼續
  → 儲存用戶訊息到 bot_messages
  → 取得對話歷史（get_conversation_context）
  → 建構 system_prompt（build_system_prompt）
  → 呼叫 AI（call_claude）
  → 記錄 AI Log（log_ai_call）
  → 儲存 bot 回覆到 bot_messages
  → 解析回應 + 發送回覆
```

### 群組訊息流程
```
Telegram Update（群組）
  → handler.handle_update()
  → 判斷是否為 @Bot 或回覆 Bot
    → 否 → 忽略（或僅記錄）
  → 查找/建立 bot_group
  → 檢查 allow_ai_response
    → false → 忽略
  → 查找 bot_user + 檢查綁定
    → 未綁定 → 靜默忽略
  → 儲存訊息 + 對話歷史 + AI 處理 + Log + 回覆
```
