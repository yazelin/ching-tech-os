# line-bot Spec Delta

## ADDED Requirements

### Requirement: Line Bot 對話歷史包含圖片資訊
Line Bot 的對話歷史 SHALL 包含用戶上傳的圖片資訊，讓 AI 能夠感知並自行決定是否處理。

#### Scenario: 對話歷史包含圖片訊息
- **WHEN** 系統組合對話歷史給 AI
- **AND** 歷史中包含圖片訊息
- **THEN** 圖片訊息格式化為 `[上傳圖片: /tmp/linebot-images/{line_message_id}.jpg]`
- **AND** AI 可以看到用戶上傳了圖片及其路徑

#### Scenario: 確保圖片暫存檔存在
- **WHEN** 系統準備呼叫 AI
- **AND** 對話歷史中包含圖片路徑
- **THEN** 系統檢查暫存檔是否存在
- **AND** 如不存在，從 NAS 讀取圖片並寫入暫存路徑
- **AND** AI 處理時可透過 Read 工具讀取圖片

#### Scenario: AI 自行判斷是否讀取圖片
- **WHEN** AI 收到對話歷史（包含圖片路徑）和用戶訊息
- **THEN** AI 根據用戶意圖自行判斷是否需要讀取圖片
- **AND** 如需讀取，使用 Read 工具讀取暫存路徑的圖片
- **AND** 如不需讀取，直接處理用戶的其他請求

#### Scenario: Read 工具可用
- **WHEN** Line Bot 呼叫 Claude CLI
- **THEN** 允許的工具列表包含 `Read`
- **AND** Claude 可以使用 Read 工具讀取圖片檔案

---

### Requirement: Line Bot 回覆舊圖片處理
Line Bot SHALL 支援用戶回覆舊圖片訊息時的圖片分析。

#### Scenario: 用戶回覆圖片訊息
- **WHEN** 用戶使用 Line 的回覆功能回覆一則圖片訊息
- **AND** 發送文字訊息
- **THEN** 系統從 `quotedMessageId` 取得被回覆的訊息 ID
- **AND** 如果被回覆的是圖片訊息，載入該圖片到暫存
- **AND** 在用戶訊息中標註 `[回覆圖片: {temp_path}]`
- **AND** AI 可以讀取該圖片回答問題

#### Scenario: 回覆非圖片訊息
- **WHEN** 用戶回覆的不是圖片訊息
- **THEN** 系統按原有流程處理，不載入額外圖片

---

### Requirement: Line Bot 圖片暫存清理
Line Bot SHALL 定期清理過期的圖片暫存檔。

#### Scenario: 定期清理暫存檔
- **WHEN** 排程任務執行（每小時）
- **THEN** 系統掃描 `/tmp/linebot-images/` 目錄
- **AND** 刪除修改時間超過 1 小時的檔案
- **AND** 不影響 NAS 上的原始檔案
