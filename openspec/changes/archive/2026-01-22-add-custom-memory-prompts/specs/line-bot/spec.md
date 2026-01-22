## ADDED Requirements

### Requirement: Line Bot 自訂記憶資料儲存
Line Bot SHALL 支援儲存群組和個人的自訂記憶 prompt。

#### Scenario: line_group_memories 資料表
- **WHEN** 系統儲存群組記憶
- **THEN** 記憶資料存於 `line_group_memories` 資料表
- **AND** 包含欄位：id、line_group_id、title、content、is_active、created_by、created_at、updated_at
- **AND** line_group_id 關聯到 line_groups 表，ON DELETE CASCADE
- **AND** created_by 關聯到 line_users 表，ON DELETE SET NULL

#### Scenario: line_user_memories 資料表
- **WHEN** 系統儲存個人記憶
- **THEN** 記憶資料存於 `line_user_memories` 資料表
- **AND** 包含欄位：id、line_user_id、title、content、is_active、created_at、updated_at
- **AND** line_user_id 關聯到 line_users 表，ON DELETE CASCADE

---

### Requirement: Line Bot 記憶管理 API
Line Bot SHALL 提供記憶管理的 RESTful API。

#### Scenario: 取得群組記憶列表
- **WHEN** 使用者請求 `GET /api/linebot/groups/{id}/memories`
- **THEN** 系統回傳該群組的所有記憶列表
- **AND** 每筆記憶包含 id、title、content、is_active、created_at

#### Scenario: 新增群組記憶
- **WHEN** 使用者請求 `POST /api/linebot/groups/{id}/memories`
- **AND** 提供 title、content 參數
- **THEN** 系統建立新的群組記憶
- **AND** 回傳建立的記憶資料

#### Scenario: 取得個人記憶列表
- **WHEN** 使用者請求 `GET /api/linebot/users/{id}/memories`
- **THEN** 系統回傳該用戶的所有個人記憶列表

#### Scenario: 新增個人記憶
- **WHEN** 使用者請求 `POST /api/linebot/users/{id}/memories`
- **AND** 提供 title、content 參數
- **THEN** 系統建立新的個人記憶

#### Scenario: 更新記憶
- **WHEN** 使用者請求 `PUT /api/linebot/memories/{id}`
- **AND** 提供更新欄位（title、content、is_active）
- **THEN** 系統更新該記憶
- **AND** 更新 updated_at 時間戳

#### Scenario: 刪除記憶
- **WHEN** 使用者請求 `DELETE /api/linebot/memories/{id}`
- **THEN** 系統刪除該記憶

---

### Requirement: Line Bot 自訂記憶整合到 Prompt
Line Bot 在處理對話時 SHALL 自動載入並整合自訂記憶到系統 prompt。

#### Scenario: 群組對話載入群組記憶
- **WHEN** AI 處理群組對話
- **THEN** 系統查詢該群組的所有啟用記憶（is_active = true）
- **AND** 將記憶內容以編號列表格式附加到 system prompt 末尾
- **AND** 記憶區塊以「【自訂記憶】」標題開頭

#### Scenario: 個人對話載入個人記憶
- **WHEN** AI 處理個人對話
- **THEN** 系統查詢該用戶的所有啟用記憶
- **AND** 將記憶內容以編號列表格式附加到 system prompt 末尾

#### Scenario: 無記憶時不影響 prompt
- **WHEN** 群組或用戶沒有任何啟用的記憶
- **THEN** system prompt 不包含記憶區塊
- **AND** 對話正常進行

#### Scenario: 記憶格式化
- **WHEN** 系統整合記憶到 prompt
- **THEN** 格式為：
  ```
  【自訂記憶】
  以下是此對話的自訂記憶，請在回應時遵循這些規則：
  1. {記憶內容1}
  2. {記憶內容2}

  請自然地遵循上述規則，不需要特別提及或確認。
  ```

---

### Requirement: Line Bot 記憶管理前端應用
系統 SHALL 提供桌面應用程式管理 Line Bot 記憶。

#### Scenario: 開啟記憶管理應用
- **WHEN** 使用者點擊 Taskbar 的「記憶管理」圖示
- **THEN** 開啟記憶管理視窗

#### Scenario: 切換群組和個人記憶
- **WHEN** 記憶管理視窗開啟
- **THEN** 顯示「群組」和「個人」兩個分頁
- **AND** 預設顯示群組分頁

#### Scenario: 選擇群組
- **WHEN** 使用者在群組分頁
- **THEN** 顯示群組下拉選單
- **WHEN** 使用者選擇群組
- **THEN** 載入該群組的記憶列表

#### Scenario: 顯示記憶列表
- **WHEN** 載入記憶列表
- **THEN** 每筆記憶顯示勾選框、標題、內容預覽
- **AND** 勾選框反映 is_active 狀態
- **AND** 每筆記憶有編輯和刪除按鈕

#### Scenario: 切換記憶啟用狀態
- **WHEN** 使用者點擊記憶的勾選框
- **THEN** 系統更新該記憶的 is_active 狀態
- **AND** 顯示操作成功提示

#### Scenario: 新增記憶
- **WHEN** 使用者點擊「新增」按鈕
- **THEN** 顯示新增記憶彈出視窗
- **AND** 包含標題和內容輸入欄位
- **WHEN** 使用者填寫並確認
- **THEN** 系統建立記憶並重新載入列表

#### Scenario: 編輯記憶
- **WHEN** 使用者點擊記憶的「編輯」按鈕
- **THEN** 顯示編輯彈出視窗
- **AND** 預填現有標題和內容
- **WHEN** 使用者修改並確認
- **THEN** 系統更新記憶

#### Scenario: 刪除記憶
- **WHEN** 使用者點擊記憶的「刪除」按鈕
- **THEN** 顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 系統刪除記憶並重新載入列表
