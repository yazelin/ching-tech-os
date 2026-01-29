# Design: add-telegram-progress-notify

## 現有架構

```
handler.py                    claude_agent.py
    │                              │
    ├─ call_claude(prompt)  ──►    ├─ 啟動子程序
    │   （等待完成）                │   ├─ 收集全部 stdout
    │                              │   ├─ 程序結束
    │                              │   └─ 一次性解析 stream-json
    ◄─ ClaudeResponse ────────     └─ 回傳結果
```

**問題**：`call_claude()` 是「等全部完成才回傳」，無法在執行期間通知進度。

## 目標架構

```
handler.py                    claude_agent.py
    │                              │
    ├─ call_claude(                ├─ 啟動子程序
    │    prompt,                   │   ├─ 即時讀取 stdout 行
    │    on_tool_start=cb1,        │   │   ├─ 偵測 tool_use → await on_tool_start(name, input)
    │    on_tool_end=cb2,          │   │   └─ 偵測 tool_result → await on_tool_end(name, result)
    │  )                           │   ├─ 程序結束
    │                              │   └─ 回傳完整結果
    ◄─ ClaudeResponse ────────     └─
    │
    ├─ (cb1): adapter.send_progress() / adapter.update_progress()
    └─ (cb2): adapter.update_progress() (✅ 完成標記)
```

## 關鍵設計決策

### 1. Callback 型態

使用 async callable：

```python
ToolNotifyCallback = Callable[[str, dict], Awaitable[None]]
# on_tool_start(tool_name: str, tool_input: dict) -> None
# on_tool_end(tool_name: str, result: dict) -> None
```

`result` dict 包含 `{"duration_ms": int, "output": str | None}`。

### 2. 串流解析修改方式

目前 `read_stdout()` 已經逐行讀取並記錄時間戳，只需在讀取每行後**即時解析**並觸發 callback：

```python
async def read_stdout():
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        ts = time.time()
        decoded = line.decode("utf-8")
        stdout_lines_with_time.append((ts, decoded))
        # 即時解析並觸發 callback
        await _process_stream_event(decoded, ts, on_tool_start, on_tool_end)
```

重用現有的 `_parse_stream_json_with_timing` 邏輯，但拆出單行事件處理。

### 3. 進度訊息格式

參考 `~/SDD/telegram-bot` 的格式：

```
🤖 AI 處理中

🔧 search_knowledge
   └ query='水切爐'
   ⏳ 執行中...

🔧 get_knowledge_item
   └ id='kb-015'
   ✅ 完成 (1.2s)
```

### 4. 進度訊息生命週期

1. 第一個 tool 開始 → `send_progress()` 送出初始訊息，記住 `message_id`
2. 後續 tool 開始/結束 → `update_progress()` 編輯同一則訊息
3. AI 回應完成 → `finish_progress()` 刪除進度訊息
4. 如果沒有任何 tool 被呼叫 → 不送進度訊息

### 5. 錯誤處理

- Callback 內部的錯誤不應影響 AI 處理流程（catch + log）
- `edit_message` 可能因 Telegram API 限流失敗（靜默忽略）
- `delete_message` 可能因訊息已過期失敗（靜默忽略，adapter 已處理）

### 6. 不修改 `call_claude()` 回傳值

Callback 參數是可選的（`None` 表示不使用），不改變既有呼叫者的行為。
