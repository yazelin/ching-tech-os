# Line Bot 用戶 Mention（標記）功能研究

## 研究目的

在群組對話中，當 Bot 回應訊息時 tag（mention）發問的用戶，讓用戶清楚知道這個回應是給誰的。

## 技術發現

### Line Messaging API 支援

Line SDK v3 支援透過 `TextMessageV2` 發送帶有 mention 的訊息：

```python
from linebot.v3.messaging import (
    TextMessageV2,
    MentionSubstitutionObject,
    UserMentionTarget,
)

# 建立帶有 mention 的訊息
msg = TextMessageV2(
    text='{user} 你好！',  # 使用佔位符
    substitution={
        'user': MentionSubstitutionObject(
            mentionee=UserMentionTarget(userId='U1234567890abcdef')
        )
    }
)
```

### 產生的 JSON 格式

```json
{
    "type": "textV2",
    "text": "{user} 你好！",
    "substitution": {
        "user": {
            "type": "mention",
            "mentionee": {
                "type": "user",
                "userId": "U1234567890abcdef"
            }
        }
    }
}
```

### 重要限制

1. **需要 Line 用戶 ID**：必須知道要 mention 的用戶的 Line User ID（格式如 `U1234567890abcdef`）
2. **佔位符格式**：文字中使用 `{key}` 作為佔位符，在 `substitution` 中定義對應的 mention 對象
3. **僅適用 TextMessageV2**：原本的 `TextMessage` 不支援 substitution

### 可用的 Mention 類型

1. **UserMentionTarget**：mention 特定用戶
   - 需要 `userId` 參數

2. **AllMentionTarget**：mention 全部（@All）
   - 不需要參數

## 實作方案

### 修改位置

1. `backend/src/ching_tech_os/services/linebot.py`
   - 新增 import：`TextMessageV2`, `MentionSubstitutionObject`, `UserMentionTarget`
   - 新增函數：`reply_text_with_mention()`
   - 修改 `reply_messages()` 以支援 TextMessageV2

2. `backend/src/ching_tech_os/services/linebot_ai.py`
   - 修改 `send_ai_response()` 在群組對話時使用 mention
   - 傳遞 Line 用戶 ID 到回應函數

3. `backend/src/ching_tech_os/api/linebot_router.py`
   - 確保 Line 用戶 ID 被正確傳遞

### 實作步驟

1. **在 linebot.py 新增 mention 支援函數**
   ```python
   async def reply_text_with_mention(
       reply_token: str,
       text: str,
       mention_user_id: str | None = None,
   ) -> str | None:
       """回覆文字訊息，可選擇 mention 特定用戶"""
       if mention_user_id:
           # 使用 TextMessageV2 + mention
           message = TextMessageV2(
               text='{user} ' + text,
               substitution={
                   'user': MentionSubstitutionObject(
                       mentionee=UserMentionTarget(userId=mention_user_id)
                   )
               }
           )
       else:
           # 原本的 TextMessage
           message = TextMessage(text=text)

       # 發送訊息
       ...
   ```

2. **修改 linebot_ai.py 的 send_ai_response()**
   - 新增 `mention_user_id` 參數
   - 群組對話時，在回應開頭加入 mention

3. **修改 process_message_with_ai()**
   - 傳遞 Line 用戶 ID 給 send_ai_response()

### 用戶體驗

**修改前（群組）：**
```
Bot: 好的，這是你需要的資料...
```

**修改後（群組）：**
```
Bot: @小明 好的，這是你需要的資料...
     ^^^^^ 可點擊的 mention，小明會收到通知
```

### 注意事項

1. **僅群組對話需要**：個人對話不需要 mention（因為就是一對一）
2. **Line 用戶 ID 來源**：從 webhook 事件中取得，已經儲存在 `line_users` 表
3. **向後相容**：若未提供 mention_user_id，退回使用原本的 TextMessage

## 測試計劃

1. 在測試群組中，讓某用戶發送訊息 @Bot
2. 確認 Bot 回覆時會 mention 該用戶
3. 確認被 mention 的用戶會收到 Line 通知
4. 確認個人對話不受影響

## 參考資料

- [LINE Messaging API - Text message (v2)](https://developers.line.biz/en/reference/messaging-api/#text-message-v2)
- [line-bot-sdk-python GitHub](https://github.com/line/line-bot-sdk-python)
