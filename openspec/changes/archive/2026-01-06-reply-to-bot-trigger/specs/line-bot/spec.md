## MODIFIED Requirements

### Requirement: 群組 AI 回應觸發條件
Line Bot SHALL 支援多種群組 AI 回應觸發方式。

#### Scenario: @ 機器人觸發（現有行為）
- **WHEN** Line 用戶在群組中發送訊息
- **AND** 訊息包含 `@{bot_name}`（設定的觸發名稱）
- **AND** 群組 `allow_ai_response = true`
- **AND** 用戶已綁定 CTOS 帳號
- **THEN** 系統觸發 AI 處理該訊息

#### Scenario: 回覆機器人訊息觸發（新增）
- **WHEN** Line 用戶在群組中使用「回覆」功能
- **AND** 回覆的對象是機器人之前發送的訊息
- **AND** 群組 `allow_ai_response = true`
- **AND** 用戶已綁定 CTOS 帳號
- **THEN** 系統觸發 AI 處理該訊息
- **AND** 不需要訊息內容包含 @ 機器人

#### Scenario: 回覆其他用戶訊息不觸發
- **WHEN** Line 用戶在群組中使用「回覆」功能
- **AND** 回覆的對象是其他用戶的訊息
- **AND** 訊息內容不包含 @ 機器人
- **THEN** 系統不觸發 AI 處理

#### Scenario: 個人對話不受影響
- **WHEN** Line 用戶在個人對話中發送訊息
- **THEN** 所有訊息都觸發 AI 處理（維持現有行為）

---
