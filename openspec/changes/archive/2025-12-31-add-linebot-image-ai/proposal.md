# Proposal: add-linebot-image-ai

## Summary

讓 Line Bot AI 能夠「看到」用戶傳送的圖片。透過在對話歷史中記錄圖片暫存路徑，Claude 可以自行判斷是否需要讀取圖片來回答用戶問題。

## Problem

目前 Line Bot 的 AI 功能只能處理純文字訊息：
- 圖片訊息會儲存到 NAS，但 AI 不知道有圖片
- 用戶傳圖片後問「這是什麼」，AI 完全看不到圖片
- 只能回覆「無法查看圖片」

## Solution

### 核心概念

在對話歷史中包含圖片資訊，讓 Claude 自行判斷是否需要處理：

1. **對話歷史中**：圖片訊息顯示為 `[上傳圖片: /tmp/linebot-images/{message_id}.jpg]`
2. **AI 處理前**：確保暫存檔存在（從 NAS 讀取）
3. **Read 工具**：始終可用，Claude 根據用戶意圖自行決定是否讀取

### 回覆舊圖片

Line SDK 的 `quotedMessageId` 可以知道用戶在回覆哪則訊息：
- 如果用戶回覆的是圖片訊息，即使超過對話歷史範圍
- 系統會額外載入該圖片供 AI 分析

### 暫存檔清理

使用排程自動清理過期的暫存檔：
- 暫存目錄：`/tmp/linebot-images/`
- 清理頻率：每小時
- 保留時間：1 小時內的檔案

### 範例對話

```
# 情境 1：最近上傳圖片後詢問
user: [上傳圖片: /tmp/linebot-images/abc123.jpg]
user: 這是什麼？
→ Claude 判斷用戶在問圖片，使用 Read 工具讀取並回答

# 情境 2：上傳圖片後問其他問題
user: [上傳圖片: /tmp/linebot-images/def456.jpg]
user: 幫我查一下專案 A 的進度
→ Claude 判斷用戶在問專案，不讀取圖片

# 情境 3：回覆很久以前的圖片
user: (回覆 3 天前的圖片) 這個設計圖是哪個專案的？
→ 系統從 quotedMessageId 找到圖片，載入暫存後讓 Claude 分析
```

## Affected Specs

- `line-bot`: 修改對話歷史格式，新增圖片暫存機制，支援回覆舊圖片

## Scope

- 後端：`linebot_ai.py`、`linebot.py`、`linebot_router.py`
- 排程：新增暫存清理任務
- 無前端變更
- 無資料庫變更（使用現有的 line_files 表）
