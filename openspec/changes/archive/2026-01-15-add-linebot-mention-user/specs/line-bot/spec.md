## ADDED Requirements

### Requirement: 群組對話回應時 Mention 用戶
Line Bot 在群組對話中回應時 SHALL mention（@）發問的用戶，讓用戶清楚知道回應對象。

#### Scenario: 群組對話回應包含 mention
- **WHEN** Bot 在群組中回覆用戶的訊息
- **THEN** 回覆訊息使用 `TextMessageV2` 格式
- **AND** 訊息開頭 mention 發問的用戶
- **AND** 用戶會收到 Line 的提及通知

#### Scenario: 個人對話不使用 mention
- **WHEN** Bot 在個人對話中回覆用戶
- **THEN** 回覆訊息使用一般的 `TextMessage` 格式
- **AND** 不包含 mention（因為一對一不需要）

#### Scenario: 混合訊息回覆（文字+圖片）
- **WHEN** Bot 在群組中回覆包含圖片的訊息
- **THEN** 第一則文字訊息使用 `TextMessageV2` 並 mention 用戶
- **AND** 後續的圖片訊息使用 `ImageMessage`
- **AND** 整體回覆順序維持：文字在前、圖片在後

#### Scenario: 無法取得用戶 ID 時的 fallback
- **WHEN** Bot 需要回覆但無法取得發問用戶的 Line User ID
- **THEN** 使用一般的 `TextMessage` 回覆
- **AND** 不阻擋回覆流程
