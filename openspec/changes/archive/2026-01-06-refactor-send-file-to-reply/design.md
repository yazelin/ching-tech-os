# Design: refactor-send-file-to-reply

## Architecture Overview

### 訊息流程圖

```
┌─────────────────────────────────────────────────────────────────┐
│                        用戶發送訊息                              │
│                   「找亦達 layout 圖給我」                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    linebot_ai.py                                 │
│              process_message_with_ai()                           │
│                                                                  │
│  1. 組合 prompt + history                                        │
│  2. 呼叫 Claude CLI（含 MCP 工具）                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Claude AI 處理                                │
│                                                                  │
│  1. 使用 search_nas_files 找到檔案                               │
│  2. 使用 prepare_file_message 準備發送                           │
│     → 回傳: 好的，這是亦達的 layout 圖                           │
│             [FILE_MESSAGE:{"type":"image","url":"..."}]          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                linebot_ai.py 解析回應                            │
│                                                                  │
│  parse_ai_response():                                            │
│    - 提取 [FILE_MESSAGE:...] 標記                                │
│    - 移除標記後的純文字作為回覆                                   │
│    - 解析 JSON 取得圖片 URL                                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   reply_messages()                               │
│                                                                  │
│  messages = [                                                    │
│    TextMessage("好的，這是亦達的 layout 圖"),                     │
│    ImageMessage(url="..."),                                      │
│  ]                                                               │
│                                                                  │
│  api.reply_message(reply_token, messages)  ← 免費！              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      用戶收到回覆                                 │
│                                                                  │
│  ┌──────────────────────┐                                        │
│  │ 好的，這是亦達的      │                                        │
│  │ layout 圖            │                                        │
│  ├──────────────────────┤                                        │
│  │  ┌────────────────┐  │                                        │
│  │  │   [圖片預覽]    │  │                                        │
│  │  └────────────────┘  │                                        │
│  └──────────────────────┘                                        │
└─────────────────────────────────────────────────────────────────┘
```

## MCP 工具設計

### prepare_file_message 工具

```python
@mcp.tool()
async def prepare_file_message(
    file_path: str,
) -> str:
    """
    準備檔案訊息供 Line Bot 回覆。不會直接發送，而是由回覆系統處理。

    Args:
        file_path: NAS 檔案的完整路徑（從 search_nas_files 取得）

    Returns:
        包含 [FILE_MESSAGE:...] 標記的字串，供回覆系統解析
    """
    # 1. 驗證檔案路徑
    # 2. 產生 24h 分享連結
    # 3. 回傳結構化標記
```

### 回傳格式

```json
{
  "type": "image",       // 或 "file"
  "url": "https://...",  // 分享連結 URL
  "name": "layout.png",  // 檔案名稱
  "size": "1.2MB"        // 檔案大小（選填）
}
```

標記格式：`[FILE_MESSAGE:{"type":"image","url":"...","name":"..."}]`

## 回覆邏輯設計

### parse_ai_response() 函數

```python
def parse_ai_response(response: str) -> tuple[str, list[dict]]:
    """
    解析 AI 回應，提取文字和檔案訊息

    Returns:
        (text, files): 純文字回覆和檔案訊息列表
    """
    import re
    import json

    pattern = r'\[FILE_MESSAGE:(\{.*?\})\]'
    files = []

    for match in re.finditer(pattern, response):
        try:
            file_info = json.loads(match.group(1))
            files.append(file_info)
        except json.JSONDecodeError:
            pass

    # 移除標記，保留純文字
    text = re.sub(pattern, '', response).strip()

    return text, files
```

### reply_messages() 函數

```python
async def reply_messages(
    reply_token: str,
    messages: list[TextMessage | ImageMessage],
) -> list[str]:
    """
    使用 reply_message 發送多則訊息

    Args:
        reply_token: Line 回覆 token
        messages: 訊息列表（最多 5 則）

    Returns:
        發送成功的訊息 ID 列表
    """
    api = await get_messaging_api()
    response = await api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages[:5],  # Line 限制最多 5 則
        )
    )
    return [m.id for m in response.sent_messages]
```

## Prompt 更新

### 工具說明更新

```
【NAS 專案檔案】
- search_nas_files: 搜尋 NAS 共享檔案
- get_nas_file_info: 取得 NAS 檔案詳細資訊
- prepare_file_message: 準備檔案訊息（圖片會直接顯示，其他發連結）
  · file_path: 檔案完整路徑（從 search_nas_files 取得）
  · 使用後圖片會顯示在回覆中，不需額外操作
- create_share_link: 只產生連結（不發送）

使用流程：
1. 用 search_nas_files 搜尋檔案
2. 用 prepare_file_message 準備發送（圖片會自動顯示）
3. 若只想給連結不顯示，才用 create_share_link
```

## 錯誤處理

### reply_token 過期

```python
# 在 linebot_ai.py 中
try:
    await reply_messages(reply_token, messages)
except InvalidReplyTokenError:
    # Token 過期，fallback 到 push_message
    logger.warning("Reply token 過期，改用 push_message")
    for msg in messages:
        if isinstance(msg, ImageMessage):
            await push_image(target_id, msg.original_content_url)
        else:
            await push_text(target_id, msg.text)
```

### 訊息數量超過限制

```python
# 如果 AI 回傳超過 4 張圖片（預留 1 則給文字）
if len(files) > 4:
    # 只發送前 4 張，其餘提供連結
    extra_files = files[4:]
    files = files[:4]
    text += "\n\n其他檔案連結：\n" + "\n".join(f.url for f in extra_files)
```

## 相容性考量

### send_nas_file 處理

- 程式碼保留 `send_nas_file`（不刪除）
- Prompt 中**不提及** `send_nas_file`，只說明 `prepare_file_message`
- AI 不會使用到舊的 push 方式
- 未來視統計數據決定是否恢復 push 方式
