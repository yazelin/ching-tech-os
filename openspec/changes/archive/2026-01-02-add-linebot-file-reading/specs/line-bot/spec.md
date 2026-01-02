# Spec Delta: line-bot

## ADDED Requirements

### Requirement: Line Bot 對話歷史包含檔案資訊
Line Bot 的對話歷史 SHALL 包含用戶上傳的可讀取檔案資訊，讓 AI 能夠感知並自行決定是否處理。

#### Scenario: 對話歷史包含檔案訊息
- **WHEN** 系統組合對話歷史給 AI
- **AND** 歷史中包含檔案訊息
- **AND** 檔案副檔名為可讀取類型（txt, md, json, csv, log, xml, yaml, yml, pdf）
- **THEN** 檔案訊息格式化為 `[上傳檔案: /tmp/linebot-files/{line_message_id}_{filename}]`
- **AND** AI 可以看到用戶上傳了檔案及其路徑

#### Scenario: 確保檔案暫存檔存在
- **WHEN** 系統準備呼叫 AI
- **AND** 對話歷史中包含檔案路徑
- **THEN** 系統檢查暫存檔是否存在
- **AND** 如不存在，從 NAS 讀取檔案並寫入 `/tmp/linebot-files/`
- **AND** AI 處理時可透過 Read 工具讀取檔案內容

#### Scenario: AI 自行判斷是否讀取檔案
- **WHEN** AI 收到對話歷史（包含檔案路徑）和用戶訊息
- **THEN** AI 根據用戶意圖自行判斷是否需要讀取檔案
- **AND** 如需讀取，使用 Read 工具讀取暫存路徑的檔案
- **AND** 如不需讀取，直接處理用戶的其他請求

#### Scenario: 不支援的檔案類型
- **WHEN** 用戶上傳不支援的檔案（如 docx, pptx, xlsx）
- **THEN** 系統不將檔案複製到暫存
- **AND** 對話歷史顯示 `[上傳檔案: {filename}（無法讀取此類型）]`
- **AND** AI 可告知用戶此檔案類型暫不支援

#### Scenario: 大檔案限制
- **WHEN** 用戶上傳超過 5MB 的檔案
- **THEN** 系統不將檔案複製到暫存
- **AND** 對話歷史顯示 `[上傳檔案: {filename}（檔案過大）]`

---

### Requirement: Line Bot 回覆舊檔案處理
Line Bot SHALL 支援用戶回覆舊檔案訊息時的檔案讀取。

#### Scenario: 用戶回覆檔案訊息
- **WHEN** 用戶使用 Line 的回覆功能回覆一則檔案訊息
- **AND** 發送文字訊息
- **AND** 被回覆的檔案為可讀取類型
- **THEN** 系統從 `quotedMessageId` 取得被回覆的訊息 ID
- **AND** 載入該檔案到暫存
- **AND** 在用戶訊息中標註 `[回覆檔案: {temp_path}]`
- **AND** AI 可以讀取該檔案回答問題

#### Scenario: 回覆不可讀取的檔案
- **WHEN** 用戶回覆的檔案為不支援的類型
- **THEN** 系統在用戶訊息中標註 `[回覆檔案: {filename}（無法讀取此類型）]`
- **AND** AI 可告知用戶此檔案類型暫不支援

---

## MODIFIED Requirements

### Requirement: Line Bot 圖片暫存清理
Line Bot SHALL 定期清理過期的圖片與檔案暫存檔。

#### Scenario: 定期清理暫存檔
- **WHEN** 排程任務執行（每小時）
- **THEN** 系統掃描 `/tmp/linebot-images/` 目錄
- **AND** 系統掃描 `/tmp/linebot-files/` 目錄
- **AND** 刪除修改時間超過 1 小時的檔案
- **AND** 不影響 NAS 上的原始檔案
