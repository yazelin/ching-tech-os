# 即時通訊架構

## 概覽

ChingTech OS 使用 Socket.IO 實現即時雙向通訊，主要用於：
- **終端機**：PTY shell session
- **AI 助手**：串流回應

## 技術棧

| 層級 | 技術 |
|------|------|
| 前端 | Socket.IO Client |
| 後端 | python-socketio (AsyncServer) |
| 終端機 | ptyprocess (PTY 模擬) |

---

## 架構圖

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │   terminal.js   │    │  ai-assistant.js │                 │
│  │   (xterm.js)    │    │                  │                 │
│  └────────┬────────┘    └────────┬─────────┘                │
│           │                       │                          │
│           └───────────┬───────────┘                          │
│                       │                                      │
│           ┌───────────▼───────────┐                          │
│           │   socket-client.js    │                          │
│           │   (Socket.IO Client)  │                          │
│           └───────────┬───────────┘                          │
└───────────────────────┼─────────────────────────────────────┘
                        │ WebSocket
┌───────────────────────┼─────────────────────────────────────┐
│                       ▼                Backend               │
│           ┌───────────────────────┐                          │
│           │      main.py          │                          │
│           │  (Socket.IO Server)   │                          │
│           └───────────┬───────────┘                          │
│                       │                                      │
│           ┌───────────┼───────────┐                          │
│           ▼           ▼           ▼                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ api/terminal│ │   api/ai    │ │api/message  │            │
│  │    .py      │ │    .py      │ │ _events.py  │            │
│  └──────┬──────┘ └──────┬──────┘ └─────────────┘            │
│         │               │                                    │
│         ▼               ▼                                    │
│  ┌─────────────┐ ┌─────────────┐                            │
│  │  services/  │ │  services/  │                            │
│  │ terminal.py │ │claude_agent │                            │
│  │ (ptyprocess)│ │    .py      │                            │
│  └─────────────┘ └─────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 終端機 (PTY)

### 技術說明

使用 `ptyprocess` 建立真正的 pseudo-terminal，支援：
- 完整的 shell session（工作目錄、環境變數保留）
- 互動式程式（vim、htop、top）
- ANSI 轉義序列
- 視窗大小調整

### 後端實作

位置：`backend/src/ching_tech_os/services/terminal.py`

```python
# 建立 PTY session
session = await terminal_service.create_session(
    websocket_sid=sid,
    user_id=user_id,
    cols=80,
    rows=24
)

# PTY 讀取迴圈（非同步）
async def _read_loop(self) -> None:
    while self.pty.isalive():
        data = await loop.run_in_executor(
            None,
            lambda: self.pty.read(4096)
        )
        if data:
            await self._output_callback(session_id, data)
```

### Socket.IO 事件

位置：`backend/src/ching_tech_os/api/terminal.py`

| 事件 | 方向 | 說明 |
|------|------|------|
| `terminal:create` | Client → Server | 建立新 session |
| `terminal:input` | Client → Server | 傳送使用者輸入 |
| `terminal:resize` | Client → Server | 調整視窗大小 |
| `terminal:close` | Client → Server | 關閉 session |
| `terminal:output` | Server → Client | 傳送 PTY 輸出 |
| `terminal:error` | Server → Client | 錯誤通知 |
| `terminal:closed` | Server → Client | session 已關閉 |

### 前端使用

位置：`frontend/js/terminal.js`

```javascript
// 建立終端機
const response = await socket.emitWithAck('terminal:create', {
  cols: term.cols,
  rows: term.rows,
  user_id: userId
});

// 監聽輸出
socket.on('terminal:output', (data) => {
  if (data.session_id === sessionId) {
    term.write(data.data);
  }
});

// 傳送輸入
term.onData((data) => {
  socket.emit('terminal:input', {
    session_id: sessionId,
    data: data
  });
});
```

### Session 管理

- **超時時間**：5 分鐘無活動自動清理
- **多終端機**：每個終端機視窗獨立 session
- **斷線重連**：短暫斷線可恢復（在超時前）

---

## AI 串流

### 技術說明

AI 對話使用 Socket.IO 實現串流回應，讓使用者可以即時看到 AI 的回覆。

### Socket.IO 事件

| 事件 | 方向 | 說明 |
|------|------|------|
| `ai:message` | Client → Server | 發送訊息 |
| `ai:stream:start` | Server → Client | 開始串流 |
| `ai:stream:chunk` | Server → Client | 串流片段 |
| `ai:stream:end` | Server → Client | 串流結束 |
| `ai:error` | Server → Client | 錯誤通知 |

### 資料結構

```javascript
// ai:message
{
  conversation_id: "uuid",
  content: "使用者訊息"
}

// ai:stream:chunk
{
  conversation_id: "uuid",
  chunk: "AI 回應片段"
}
```

---

## 訊息事件

### Socket.IO 事件

位置：`backend/src/ching_tech_os/api/message_events.py`

| 事件 | 方向 | 說明 |
|------|------|------|
| `message:new` | Server → Client | 新訊息通知 |
| `message:read` | Client → Server | 標記已讀 |

---

## 前端 Socket 客戶端

位置：`frontend/js/socket-client.js`

### 初始化

```javascript
const SocketClient = (function() {
  let socket = null;

  function init() {
    socket = io('http://localhost:8089', {
      transports: ['websocket'],
      autoConnect: true
    });

    socket.on('connect', () => {
      console.log('Socket connected:', socket.id);
    });

    socket.on('disconnect', (reason) => {
      console.log('Socket disconnected:', reason);
    });
  }

  function getSocket() {
    return socket;
  }

  return { init, getSocket };
})();
```

### 使用方式

```javascript
// 取得 socket 實例
const socket = SocketClient.getSocket();

// 發送事件
socket.emit('event:name', data);

// 發送事件並等待回應
const response = await socket.emitWithAck('event:name', data);

// 監聽事件
socket.on('event:name', (data) => {
  // 處理資料
});

// 移除監聽
socket.off('event:name');
```

---

## 後端 Socket.IO 設定

位置：`backend/src/ching_tech_os/main.py`

```python
import socketio
from fastapi import FastAPI

# 建立 Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*'
)

# 建立 FastAPI app
app = FastAPI()

# 註冊事件處理
from .api import terminal, ai
terminal.register_events(sio)
ai.register_events(sio)

# 建立 ASGI app
socket_app = socketio.ASGIApp(sio, app)
```

---

## 注意事項

### CORS 設定

開發環境允許所有來源：

```python
sio = socketio.AsyncServer(cors_allowed_origins='*')
```

生產環境應限制：

```python
sio = socketio.AsyncServer(
    cors_allowed_origins=['https://your-domain.com']
)
```

### 連線狀態處理

前端應處理斷線重連：

```javascript
socket.on('disconnect', (reason) => {
  if (reason === 'io server disconnect') {
    // 伺服器主動斷線，需要手動重連
    socket.connect();
  }
  // 其他原因會自動重連
});
```

### 錯誤處理

```javascript
socket.on('connect_error', (error) => {
  console.error('Connection error:', error);
  // 顯示錯誤通知
});
```

---

## 相關檔案

| 位置 | 說明 |
|------|------|
| `backend/src/ching_tech_os/main.py` | Socket.IO server 設定 |
| `backend/src/ching_tech_os/api/terminal.py` | 終端機事件處理 |
| `backend/src/ching_tech_os/services/terminal.py` | PTY session 管理 |
| `backend/src/ching_tech_os/api/ai.py` | AI 串流事件處理 |
| `frontend/js/socket-client.js` | Socket.IO 客戶端 |
| `frontend/js/terminal.js` | 終端機前端（xterm.js） |
