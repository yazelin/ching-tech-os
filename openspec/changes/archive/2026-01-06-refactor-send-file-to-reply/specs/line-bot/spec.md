# line-bot Spec Delta

## ADDED Requirements

### Requirement: Line Bot 多訊息回覆
Line Bot SHALL 支援一次回覆多則訊息（文字 + 圖片混合）。

#### Scenario: 回覆文字和圖片
- **WHEN** AI 回應包含檔案訊息標記
- **AND** reply_token 有效
- **THEN** 系統解析 AI 回應提取檔案資訊
- **AND** 組合 TextMessage 和 ImageMessage
- **AND** 使用 `reply_message` 一次發送（最多 5 則）

#### Scenario: 訊息數量超過限制
- **WHEN** AI 回應包含超過 4 張圖片
- **THEN** 系統只發送前 4 張圖片
- **AND** 其餘圖片以連結形式附加在文字中

#### Scenario: reply_token 過期 fallback
- **WHEN** reply_token 已過期
- **AND** 有檔案訊息需要發送
- **THEN** 系統改用 push_message 發送
- **AND** 記錄警告日誌

---

### Requirement: AI 回應解析
Line Bot SHALL 解析 AI 回應中的檔案訊息標記。

#### Scenario: 解析 FILE_MESSAGE 標記
- **WHEN** AI 回應包含 `[FILE_MESSAGE:{...}]` 格式標記
- **THEN** 系統提取 JSON 內容
- **AND** 移除標記保留純文字回覆
- **AND** 根據 type 欄位決定訊息類型（image/file）

#### Scenario: 無效的 JSON 格式
- **WHEN** FILE_MESSAGE 標記中的 JSON 格式無效
- **THEN** 系統忽略該標記
- **AND** 將標記原文保留在回覆中
- **AND** 記錄警告日誌

#### Scenario: 回應不含標記
- **WHEN** AI 回應不包含任何 FILE_MESSAGE 標記
- **THEN** 系統按原有邏輯回覆純文字
