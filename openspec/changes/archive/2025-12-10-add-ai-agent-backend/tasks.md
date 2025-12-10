# Tasks: AI Agent 後端整合

## 1. 後端 Socket.IO 整合
- [x] 1.1 新增 `python-socketio` 依賴到 `pyproject.toml`
- [x] 1.2 修改 `main.py` 建立 Socket.IO 伺服器
- [x] 1.3 設定 CORS 允許前端連線

## 2. Claude CLI 服務封裝
- [x] 2.1 建立 `services/claude_agent.py`
- [x] 2.2 實作 `async def call_claude(prompt, session_id, model)` 非同步呼叫
- [x] 2.3 實作回應解析和錯誤處理
- [x] 2.4 實作超時處理（120 秒）

## 3. AI 對話端點
- [x] 3.1 建立 `api/ai.py` Socket.IO 事件處理
- [x] 3.2 實作 `ai_chat` 事件接收訊息（含 chatId, sessionId, message, model）
- [x] 3.3 實作 `ai_typing` 事件通知處理中
- [x] 3.4 實作 `ai_response` 事件回傳結果
- [x] 3.5 實作 `ai_error` 事件回傳錯誤

## 4. 前端全域 Socket.IO 連線
- [x] 4.1 新增 Socket.IO client 腳本引用（CDN 或本地）
- [x] 4.2 建立 `socket-client.js` 全域連線模組
- [x] 4.3 實作頁面載入時自動連線
- [x] 4.4 實作 `ai_response` 事件處理（更新 localStorage）
- [x] 4.5 實作 `ai_typing` 事件處理

## 5. 修改 AI 助手（ai-assistant.js）
- [x] 5.1 Chat 結構新增 `sessionId` 欄位（UUID）
- [x] 5.2 建立新對話時生成 sessionId
- [x] 5.3 修改 `sendMessage()` 透過 SocketClient 發送
- [x] 5.4 移除模擬回應邏輯（simulateResponse）
- [x] 5.5 實作接收回應後更新訊息列表
- [x] 5.6 暴露 `isWindowOpen()` 方法供通知系統判斷

## 6. 通知系統
- [x] 6.1 建立 `notification.js` 通知模組
- [x] 6.2 實作 Toast 通知樣式
- [x] 6.3 AI 助手關閉時收到回應 → 顯示通知
- [x] 6.4 點擊通知 → 開啟 AI 助手視窗

## 7. 驗證
- [x] 7.1 測試 Socket.IO 連線建立
- [x] 7.2 測試發送訊息並接收回應
- [x] 7.3 測試 sessionId 對話上下文維持
- [x] 7.4 測試 AI 助手開啟時不顯示通知
- [x] 7.5 測試 AI 助手關閉時顯示通知
- [x] 7.6 測試錯誤處理（CLI 不存在、超時等）
