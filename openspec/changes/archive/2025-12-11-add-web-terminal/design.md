## Context

Ching-Tech OS 需要一個 Web 終端機應用程式，讓使用者能在瀏覽器中執行伺服器命令。核心挑戰是 HTTP 無狀態特性無法滿足終端機需求：

1. **Shell Session 持久化**: 工作目錄 (`cd`)、環境變數、程式狀態需跨命令保留
2. **即時雙向通訊**: 連續輸出（如 `top`）、進度條需要即時推送
3. **互動式程式**: `vim`、`htop` 需要完整 TTY 控制碼

業界常見的 Web 終端機（如 Portainer、VS Code Server、JupyterLab Terminal）皆採用 PTY + WebSocket 架構。

## Goals / Non-Goals

### Goals
- 提供持久化 shell session，保留工作目錄和環境變數
- 支援互動式程式（vim、htop 等）
- 支援多個終端機分頁
- 斷線重連機制

### Non-Goals
- 不實作 SSH 協議（使用 PTY 直接 spawn shell）
- 不實作終端機錄影/回放功能（第一版）
- 不實作終端機共享/協作功能（第一版）

## Decisions

### 1. 後端 PTY 管理
**決策**: 使用 Python `ptyprocess` 套件管理 PTY

**理由**:
- 專案後端使用 Python/FastAPI，`ptyprocess` 是成熟的跨平台 PTY 解決方案
- 比直接使用 `os.openpty()` 提供更好的 API 和錯誤處理
- 支援 resize、signal 等終端機操作

**替代方案**:
- `pexpect`: 偏向自動化腳本，不適合即時 I/O
- Node.js `node-pty`: 需要混合技術棧

### 2. 通訊協議
**決策**: 使用現有 Socket.IO 基礎設施

**理由**:
- 專案已有 Socket.IO 配置（用於 AI 聊天）
- 內建重連、房間管理、事件機制
- 無需額外配置 WebSocket

**事件設計**:
```
Client → Server:
- terminal:create    # 建立新終端機 session
- terminal:input     # 發送鍵盤輸入
- terminal:resize    # 調整視窗大小
- terminal:close     # 關閉終端機

Server → Client:
- terminal:output    # 終端機輸出
- terminal:created   # session 建立成功
- terminal:error     # 錯誤訊息
- terminal:closed    # session 已關閉
```

### 3. 前端終端機模擬器
**決策**: 使用 xterm.js（CDN 載入）

**理由**:
- 業界標準 Web 終端機前端元件（VS Code、JupyterLab 皆使用）
- 完整 VT100/xterm 支援
- 效能優秀，支援大量輸出
- 不需 npm 建置，可從 CDN 載入

**Addons**:
- `xterm-addon-fit`: 自動調整終端機尺寸
- `xterm-addon-web-links`: 自動識別 URL 並可點擊

### 4. Session 生命週期管理
**決策**: WebSocket 斷線後保留 PTY 5 分鐘

**理由**:
- 允許短暫斷線後重連（網路不穩、頁面刷新）
- 避免長時間佔用伺服器資源
- 平衡使用者體驗與資源管理

**機制**:
```
連線 → 建立/恢復 PTY session
斷線 → 啟動 5 分鐘計時器
重連 → 取消計時器，恢復 session
超時 → 清理 PTY 資源
```

### 5. 安全考量
**決策**: 以當前 Web 伺服器執行使用者身份執行 shell

**理由**:
- 第一版簡化實作，假設系統為單一管理者使用
- 避免複雜的使用者切換邏輯

**注意**:
- 終端機功能應限制於已認證使用者
- 未來可考慮整合 PAM 或 sudo 提升權限機制

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Terminal Window (xterm.js)              │    │
│  │  ┌─────────────────────────────────────────────────┐│    │
│  │  │ $ cd /home/user                                 ││    │
│  │  │ $ ls -la                                        ││    │
│  │  │ total 32                                        ││    │
│  │  │ drwxr-xr-x  5 user user 4096 Dec 10 ...        ││    │
│  │  └─────────────────────────────────────────────────┘│    │
│  └─────────────────────────────────────────────────────┘    │
│              │                    ▲                          │
│              │ Socket.IO          │                          │
│              │ terminal:input     │ terminal:output          │
│              ▼                    │                          │
└──────────────┼────────────────────┼──────────────────────────┘
               │                    │
               │    WebSocket       │
               ▼                    │
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI + Socket.IO                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  TerminalService                        │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │     sessions: Dict[session_id, TerminalSession] │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  │              │                                          │  │
│  │              ▼                                          │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │              TerminalSession                     │   │  │
│  │  │  - pty: PtyProcess (ptyprocess)                 │   │  │
│  │  │  - websocket_sid: Optional[str]                 │   │  │
│  │  │  - created_at: datetime                         │   │  │
│  │  │  - last_activity: datetime                      │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────┘  │
│                        │                                      │
│                        │ stdin/stdout                         │
│                        ▼                                      │
│                ┌───────────────┐                             │
│                │   PTY (bash)  │                             │
│                └───────────────┘                             │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow

### 建立終端機
```
1. Client: terminal:create { cols: 80, rows: 24 }
2. Server: 建立 PTY process (spawn bash)
3. Server: 產生 session_id
4. Server: terminal:created { session_id: "xxx" }
5. Server: 啟動 async 讀取 PTY output loop
```

### 輸入處理
```
1. Client: terminal:input { session_id: "xxx", data: "ls -la\r" }
2. Server: 寫入 PTY stdin
3. PTY: 執行命令
4. Server: 讀取 PTY stdout
5. Server: terminal:output { session_id: "xxx", data: "..." }
```

### 視窗調整
```
1. Client: terminal:resize { session_id: "xxx", cols: 120, rows: 40 }
2. Server: pty.setwinsize(rows, cols)
3. PTY: 發送 SIGWINCH 給 shell
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| PTY 資源洩漏（未正確清理） | 定期檢查並清理超時 session |
| 惡意命令執行 | 限制已認證使用者、未來可加入命令審計 |
| 大量輸出導致效能問題 | 前端 xterm.js 已有 buffer 管理 |
| WebSocket 斷線丟失資料 | 5 分鐘 session 保留，允許重連 |

## Migration Plan

此為新功能，無需 migration。

## File Structure

```
backend/
├── src/ching_tech_os/
│   ├── services/
│   │   └── terminal.py      # PTY 管理服務
│   ├── api/
│   │   └── terminal.py      # Socket.IO 事件處理
│   └── main.py              # 註冊 terminal 事件

frontend/
├── js/
│   └── apps/
│       └── terminal.js      # 終端機應用程式
├── css/
│   └── terminal.css         # 終端機樣式
└── index.html               # 載入 xterm.js CDN
```

## Open Questions

1. **多分頁設計**: 是否需要在單一視窗內支援多分頁？還是允許開啟多個終端機視窗？
   - 建議第一版：允許多視窗，每個視窗一個 session

2. **預設 Shell**: 是否固定使用 `/bin/bash`？還是讀取使用者偏好？
   - 建議第一版：預設 bash，後續可加入設定
