## ADDED Requirements

### Requirement: Claude API Integration
系統後端 SHALL 整合 Claude API 以提供 AI 對話功能。

#### Scenario: 發送訊息取得回應
- **WHEN** 前端發送使用者訊息至後端
- **THEN** 後端將訊息轉發至 Claude API
- **AND** 後端將 Claude 回應返回給前端

#### Scenario: 串流回應
- **WHEN** Claude API 以串流方式回傳回應
- **THEN** 後端即時將回應片段推送給前端
- **AND** 前端逐步顯示回應內容

---

### Requirement: Multi-Model Support
系統 SHALL 支援使用者選擇不同的 Claude 模型進行對話。

#### Scenario: 取得可用模型列表
- **WHEN** 前端請求可用模型列表
- **THEN** 後端返回支援的 Claude 模型清單

#### Scenario: 切換對話模型
- **WHEN** 使用者在對話中切換模型
- **THEN** 後續訊息使用新選擇的模型處理
- **AND** 對話上下文保持連續

---

### Requirement: Session Management
系統 SHALL 管理對話 session 以維持對話上下文。

#### Scenario: 建立新對話 session
- **WHEN** 使用者建立新對話
- **THEN** 後端建立新的 Claude session
- **AND** Session ID 儲存於資料庫

#### Scenario: 恢復對話 session
- **WHEN** 使用者切換至既有對話
- **THEN** 後端載入對應的 session
- **AND** 對話上下文正確恢復

---

### Requirement: Conversation Persistence
系統 SHALL 將對話資料持久化儲存。

#### Scenario: 儲存對話訊息
- **WHEN** 對話產生新訊息
- **THEN** 訊息儲存至 PostgreSQL 資料庫

#### Scenario: 載入歷史對話
- **WHEN** 使用者登入系統
- **THEN** 系統載入該使用者的所有對話列表
