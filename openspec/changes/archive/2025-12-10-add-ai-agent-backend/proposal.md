# Change: 新增 AI Agent 後端整合

## Why
AI 助手前端 UI 完成後，需要整合 Claude CLI 後端以提供實際的 AI 對話功能。參考 jaba 專案的做法，使用非同步 subprocess 呼叫 Claude CLI，完整回應後透過 Socket.IO 傳給前端。

## What Changes
- 新增 FastAPI 後端的 AI Agent 模組
- 透過 `asyncio.subprocess` 非同步呼叫 Claude CLI
- 整合 Socket.IO 進行即時通訊（全域連線）
- 前端連接 Socket.IO 接收 AI 回應
- 新增通知系統（AI 助手關閉時顯示通知）

## Impact
- Affected specs: 修改 `ai-agent-backend`
- Affected code:
  - `backend/src/ching_tech_os/services/claude_agent.py` - Claude CLI 封裝
  - `backend/src/ching_tech_os/api/ai.py` - AI 對話端點
  - `backend/src/ching_tech_os/main.py` - 整合 Socket.IO
  - `frontend/js/ai-assistant.js` - 連接 Socket.IO、新增 sessionId
  - `frontend/js/socket-client.js` - 全域 Socket.IO 連線管理
  - `frontend/js/notification.js` - 通知系統

## Technical Notes

### 架構（參考 jaba）
```
Frontend (Global Socket.IO Client)
    ↓ Socket.IO（全域連線，不隨視窗關閉斷線）
Backend (FastAPI + Socket.IO)
    ↓ asyncio.subprocess
Claude CLI（使用 --session-id 維持對話上下文）
```

### Chat 結構（新增 sessionId）
```javascript
{
  id: 'chat-1702345678-abc123def',
  sessionId: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',  // UUID for Claude CLI
  title: '新對話',
  model: 'claude-sonnet',
  messages: [...],
  createdAt: Date.now(),
  updatedAt: Date.now()
}
```

### Claude CLI 呼叫方式
```python
import asyncio
import uuid

async def call_claude(prompt: str, session_id: str, model: str = "sonnet") -> str:
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--session-id", session_id,  # 維持對話上下文
        "--model", model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(),
        timeout=120
    )
    return stdout.decode('utf-8')
```

### Socket.IO 事件
| 事件 | 方向 | 說明 |
|------|------|------|
| `ai_chat` | 前端→後端 | 發送訊息（含 chatId, sessionId, message, model） |
| `ai_typing` | 後端→前端 | 通知正在處理中 |
| `ai_response` | 後端→前端 | 回傳 AI 回應（含 chatId, message） |
| `ai_error` | 後端→前端 | 回傳錯誤訊息 |

### 全域 Socket.IO 連線
```javascript
// socket-client.js - 頁面載入時建立連線，不隨 AI 助手視窗關閉斷線
const SocketClient = (function() {
  let socket = null;

  function connect() {
    socket = io('http://localhost:8000');
    socket.on('ai_response', handleAIResponse);
    socket.on('ai_typing', handleAITyping);
  }

  function handleAIResponse(data) {
    // 1. 更新 chats 到 localStorage
    // 2. 如果 AI 助手開啟中 → 更新訊息列表
    // 3. 如果 AI 助手關閉 → 顯示通知
  }

  return { connect, emit: (e, d) => socket.emit(e, d) };
})();
```

### 通知邏輯
```
收到 ai_response 時：
├── AI 助手視窗開啟中
│   └── 直接更新訊息列表（不通知）
└── AI 助手視窗關閉
    └── 顯示系統通知：「AI 助手已回覆」
        └── 點擊通知 → 開啟 AI 助手視窗
```

### 流程
1. 頁面載入時建立全域 Socket.IO 連線
2. 前端透過 Socket.IO 發送 `ai_chat` 事件（含 sessionId）
3. 後端發送 `ai_typing` 通知前端顯示「正在輸入...」
4. 後端非同步呼叫 Claude CLI（`--session-id <sessionId>`），等待完整回應
5. 後端透過 Socket.IO 發送 `ai_response` 回傳結果
6. 前端收到回應：
   - 更新 localStorage
   - 如果 AI 助手開啟 → 更新 UI
   - 如果 AI 助手關閉 → 顯示通知

## Dependencies
- Claude CLI 已安裝並可執行
- python-socketio 套件
- 已完成 `add-ai-assistant-ui`

## Out of Scope
- 串流回應（逐字顯示）
- 對話歷史持久化到資料庫（目前用 localStorage + Claude CLI session）
