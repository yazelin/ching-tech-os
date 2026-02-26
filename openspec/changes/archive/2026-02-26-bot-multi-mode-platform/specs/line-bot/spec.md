## MODIFIED Requirements

### Requirement: Line Bot 存取控制
Line Bot SHALL 根據系統配置的未綁定用戶策略決定未綁定用戶的處理方式，而非硬編碼拒絕。

#### Scenario: 未綁定用戶的個人對話（reject 策略）
- **WHEN** 未綁定 CTOS 帳號的 Line 用戶在個人對話中發送訊息
- **AND** 訊息不是驗證碼格式
- **AND** `BOT_UNBOUND_USER_POLICY` 為 `reject`
- **THEN** 系統回覆「請先在 CTOS 綁定您的 Line 帳號才能使用此功能」
- **AND** 訊息不觸發 AI 處理

#### Scenario: 未綁定用戶的個人對話（restricted 策略）
- **WHEN** 未綁定 CTOS 帳號的 Line 用戶在個人對話中發送訊息
- **AND** 訊息不是驗證碼格式
- **AND** `BOT_UNBOUND_USER_POLICY` 為 `restricted`
- **THEN** 系統 SHALL 將訊息委派給身份分流路由器
- **AND** 路由器將訊息導向受限模式 AI 流程

#### Scenario: 未綁定用戶的群組訊息
- **WHEN** 未綁定 CTOS 帳號的 Line 用戶在群組中 @ 提及 Bot
- **THEN** 系統靜默不回應
- **AND** 訊息仍記錄到資料庫
- **AND** 不受 `BOT_UNBOUND_USER_POLICY` 影響

#### Scenario: 已綁定用戶的正常使用
- **WHEN** 已綁定 CTOS 帳號的 Line 用戶發送訊息
- **AND** 符合 AI 觸發條件
- **THEN** 系統正常處理訊息並回應
- **AND** 不受 `BOT_UNBOUND_USER_POLICY` 影響
