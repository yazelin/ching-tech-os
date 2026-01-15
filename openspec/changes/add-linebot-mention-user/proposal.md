# Change: Line Bot 群組回應時 Mention 用戶

## Why

在群組對話中人數較多時，Bot 的回應可能讓人不清楚是回覆給誰的。透過 mention（@用戶）功能，可以讓被回覆的用戶：
1. 明確知道這個回應是給自己的
2. 收到 Line 的提及通知

## What Changes

- 群組對話中，Bot 回覆時會在訊息開頭 mention 發問的用戶
- 使用 Line Messaging API 的 `TextMessageV2` + `MentionSubstitutionObject` 實現
- 個人對話不受影響（不需要 mention）

## Impact

- Affected specs: `line-bot`
- Affected code:
  - `backend/src/ching_tech_os/services/linebot.py` - 新增 mention 訊息發送函數
  - `backend/src/ching_tech_os/services/linebot_ai.py` - 修改 `send_ai_response()` 支援 mention

## Technical Validation

已驗證 Line SDK v3 支援此功能：

```python
from linebot.v3.messaging import (
    TextMessageV2,
    MentionSubstitutionObject,
    UserMentionTarget,
)

msg = TextMessageV2(
    text='{user} 你好！',
    substitution={
        'user': MentionSubstitutionObject(
            mentionee=UserMentionTarget(userId='U1234567890abcdef')
        )
    }
)
```

詳細研究文件：`docs/linebot-mention-research.md`
