## 1. 後端 PTY 服務

- [x] 1.1 安裝 `ptyprocess` 套件到專案依賴
- [x] 1.2 建立 `services/terminal.py` - TerminalSession 類別
  - PTY process 建立與管理
  - stdin/stdout 讀寫封裝
  - resize 功能
- [x] 1.3 建立 `services/terminal.py` - TerminalService 類別
  - Session 字典管理 (session_id → TerminalSession)
  - 建立/取得/關閉 session 方法
  - 超時清理機制 (5 分鐘)
- [x] 1.4 新增 session 清理背景任務到 lifespan

## 2. 後端 Socket.IO 事件

- [x] 2.1 建立 `api/terminal.py` - 定義 terminal 事件處理器
  - `terminal:create` - 建立新 session
  - `terminal:input` - 接收並寫入 PTY
  - `terminal:resize` - 調整 PTY 尺寸
  - `terminal:close` - 關閉 session
- [x] 2.2 實作 PTY 輸出讀取 async loop
  - 從 PTY stdout 讀取
  - 透過 `terminal:output` 發送到客戶端
- [x] 2.3 在 `main.py` 註冊 terminal 事件
- [x] 2.4 處理 WebSocket 斷線時的 session 保留邏輯

## 3. 前端終端機模擬器

- [x] 3.1 在 `index.html` 引入 xterm.js CDN
  - xterm.js 核心
  - xterm-addon-fit
  - xterm-addon-web-links
- [x] 3.2 新增 `css/terminal.css` - 終端機樣式
  - 視窗內容區樣式
  - xterm.js 容器樣式
- [x] 3.3 新增 `js/terminal.js` - TerminalApp 模組
  - 初始化 xterm.js Terminal
  - 配置 addons (fit, webLinks)
  - Socket.IO 連線管理

## 4. 前端事件串接

- [x] 4.1 實作 terminal:create 發送
  - 開啟視窗時建立 session
  - 傳送初始 cols/rows
- [x] 4.2 實作 terminal:input 發送
  - xterm.js onData 事件綁定
  - 發送鍵盤輸入到伺服器
- [x] 4.3 實作 terminal:output 接收
  - 監聽伺服器輸出
  - 寫入 xterm.js terminal
- [x] 4.4 實作 terminal:resize 發送
  - 視窗 resize 事件綁定
  - 呼叫 fitAddon.fit()
  - 發送新尺寸到伺服器

## 5. 視窗整合

- [x] 5.1 修改 `desktop.js` - 新增 terminal case
  - openApp('terminal') 呼叫 TerminalApp.open()
- [x] 5.2 實作 TerminalApp.open() 方法
  - 透過 WindowModule.createWindow() 建立視窗
  - 在視窗內容區初始化 xterm.js
- [x] 5.3 處理視窗關閉事件
  - 發送 terminal:close
  - 清理 xterm.js 實例
- [x] 5.4 處理視窗 resize 事件
  - 使用 ResizeObserver 監聽容器大小變化
  - 觸發 terminal resize

## 6. 斷線重連機制

- [x] 6.1 前端 - 儲存 session_id 到 sessionStorage
- [x] 6.2 前端 - 重新開啟時檢查是否有可恢復的 session
- [x] 6.3 後端 - 新增 `terminal:reconnect` 事件
- [x] 6.4 前端 - 顯示「恢復 session」或「建立新 session」選項

## 7. 測試與驗證

- [x] 7.1 手動測試基本命令執行 (ls, cd, pwd)
- [x] 7.2 測試互動式程式 (vim, htop)
- [x] 7.3 測試視窗縮放功能
- [x] 7.4 測試多視窗獨立 session
- [x] 7.5 測試斷線重連功能
