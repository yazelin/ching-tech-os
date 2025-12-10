# AI Agent Backend Specification

## MODIFIED Requirements

### Requirement: Claude CLI Integration
系統 SHALL 透過非同步 subprocess 呼叫 Claude CLI 提供 AI 對話功能，使用 `--session-id` 維持對話上下文，完整回應後透過 Socket.IO 傳給前端。

#### Scenario: 發送訊息並接收回應
- **GIVEN** 後端服務運行中且 Socket.IO 連線建立
- **WHEN** 前端發送 `ai_chat` 事件包含 chatId、sessionId、message、model
- **THEN** 後端發送 `ai_typing` 事件通知前端
- **AND** 後端非同步呼叫 Claude CLI（含 `--session-id`）等待完整回應
- **AND** 後端發送 `ai_response` 事件回傳結果

#### Scenario: 維持對話上下文
- **GIVEN** 使用者在同一個對話框發送多則訊息
- **WHEN** 後端呼叫 Claude CLI
- **THEN** 使用相同的 sessionId
- **AND** Claude CLI 維持對話上下文

#### Scenario: 錯誤處理
- **GIVEN** Claude CLI 不可用或發生錯誤
- **WHEN** 使用者發送訊息
- **THEN** 後端發送 `ai_error` 事件包含錯誤訊息
- **AND** 前端顯示錯誤提示

---

### Requirement: 全域 Socket.IO 連線
系統 SHALL 在頁面載入時建立全域 Socket.IO 連線，不隨 AI 助手視窗關閉斷線。

#### Scenario: 頁面載入時連線
- **GIVEN** 使用者進入桌面頁面
- **WHEN** 頁面載入完成
- **THEN** 自動建立 Socket.IO 連線

#### Scenario: AI 助手關閉時仍可接收回應
- **GIVEN** 使用者發送訊息後關閉 AI 助手視窗
- **WHEN** 後端回傳 AI 回應
- **THEN** 前端接收回應並更新 localStorage
- **AND** 下次開啟 AI 助手視窗時顯示該回應

---

### Requirement: 通知系統
系統 SHALL 在 AI 助手視窗關閉時，收到 AI 回應後顯示通知。

#### Scenario: AI 助手開啟時不通知
- **GIVEN** AI 助手視窗開啟中
- **WHEN** 收到 AI 回應
- **THEN** 直接更新訊息列表
- **AND** 不顯示通知

#### Scenario: AI 助手關閉時顯示通知
- **GIVEN** AI 助手視窗關閉
- **WHEN** 收到 AI 回應
- **THEN** 顯示 Toast 通知「AI 助手已回覆」
- **AND** 點擊通知開啟 AI 助手視窗
