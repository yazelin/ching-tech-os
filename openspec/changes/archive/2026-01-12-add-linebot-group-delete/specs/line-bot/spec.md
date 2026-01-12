# line-bot Spec Delta

## MODIFIED Requirements

### Requirement: Line 群組管理 API
Line Bot SHALL 提供群組管理 RESTful API，包含刪除功能。

#### Scenario: 刪除群組
- **WHEN** 使用者請求 `DELETE /api/linebot/groups/{id}`
- **THEN** 系統刪除群組記錄
- **AND** 級聯刪除該群組的所有訊息記錄
- **AND** 級聯刪除該群組的所有檔案記錄
- **AND** 返回刪除結果（含已刪除的訊息數量）
- **AND** NAS 實體檔案不自動刪除

---

### Requirement: Line Bot 前端管理介面
Line Bot SHALL 提供桌面應用程式管理介面，包含群組刪除功能。

#### Scenario: 刪除群組操作
- **WHEN** 使用者在群組詳情頁面點擊「刪除群組」按鈕
- **THEN** 系統顯示確認對話框
- **AND** 對話框顯示群組名稱與將刪除的訊息數量
- **WHEN** 使用者確認刪除
- **THEN** 系統呼叫 DELETE API 刪除群組
- **AND** 刪除成功後重新載入群組列表
- **AND** 顯示刪除成功通知
