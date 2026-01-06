# Proposal: reply-to-bot-trigger

## Summary
在 Line 群組中，當用戶「回覆」機器人之前的訊息時，不需要 @ 機器人也能自動觸發 AI 回應。

## Problem Statement
目前群組中觸發 AI 的唯一方式是在訊息中 @ 機器人名稱（如 `@擎添AI`）。但這在實際使用情境中有不便之處：

1. 用戶已經在回覆機器人的訊息，語意上已經很清楚是要跟機器人對話
2. 需要額外輸入 @ 和機器人名稱很繁瑣
3. Line 的「回覆」功能本身就是一種明確的對話指向

## Proposed Solution
修改 `should_trigger_ai` 函數，加入「回覆機器人訊息」的觸發條件：

1. 在處理訊息時，檢查 `quoted_message_id`（被回覆的訊息 ID）
2. 查詢該訊息是否為機器人發送的（source_type = 'bot'）
3. 如果是回覆機器人訊息，即使沒有 @ 也觸發 AI 回應

## Scope
- 修改：`linebot.py` 中的 `should_trigger_ai` 函數
- 修改：`linebot_ai.py` 中的 `process_message_with_ai` 調用邏輯
- 新增：查詢訊息發送者的輔助函數

## Out of Scope
- 不改變現有的 @ 觸發機制（兩種方式並存）
- 不改變個人對話的觸發邏輯（仍然是全部觸發）
