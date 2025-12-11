# Change: 新增 Web 終端機應用程式

## Why
使用者需要透過 Web UI 執行伺服器上的命令，管理服務、執行 shell 指令等。目前終端機圖示點擊後只顯示「功能開發中」。傳統 HTTP 請求無法保持 shell session 的連貫性（工作目錄、環境變數等），需要透過 PTY (Pseudo Terminal) + WebSocket 建立持久化的終端機連線。

## What Changes
- 新增後端 PTY 管理服務，為每個使用者建立並管理偽終端機 session
- 新增 WebSocket 端點處理終端機 I/O 的雙向即時通訊
- 新增前端終端機 UI 應用程式，整合 xterm.js 終端機模擬器
- 支援多個終端機分頁/視窗
- Session 在 WebSocket 斷線後可保留一段時間供重連

## Impact
- 新增 spec: `web-terminal`
- 新增後端程式碼: `services/terminal.py`, `api/terminal.py`
- 新增前端程式碼: `js/apps/terminal.js`, `css/terminal.css`
- 修改: `desktop.js` (新增 terminal 應用程式啟動邏輯)
- 修改: `main.py` (註冊 terminal WebSocket 事件)
- 依賴套件: `ptyprocess` (Python PTY)
- 前端依賴: `xterm.js`, `xterm-addon-fit`, `xterm-addon-web-links` (CDN)

## 技術決策

### 為什麼使用 PTY + WebSocket？
一般 Web 應用的 HTTP 請求是無狀態的，每次請求都是獨立的。但終端機需要：
1. **持久化 session**: 工作目錄、環境變數、shell 歷史記錄需要跨命令保留
2. **雙向即時通訊**: 命令輸出可能是連續的（如 `top`、`tail -f`），需要即時推送
3. **互動式程式支援**: 如 `vim`、`htop` 需要完整的 TTY 控制碼支援

### 方案比較
| 方案 | 優點 | 缺點 |
|------|------|------|
| PTY + WebSocket | 完整 shell 體驗、狀態保留 | 實作複雜度較高 |
| 單次命令執行 API | 簡單直接 | 無法保留狀態、不支援互動式程式 |
| SSH over WebSocket | 標準協議 | 需要額外認證配置 |

**選擇**: PTY + WebSocket，提供最接近原生終端機的體驗。

### Session 管理策略
- 每個 WebSocket 連線對應一個 PTY session
- 斷線後 PTY session 保留 5 分鐘，允許重連
- 超時未重連則自動清理 PTY 資源
- 支援同一使用者開啟多個終端機 session
