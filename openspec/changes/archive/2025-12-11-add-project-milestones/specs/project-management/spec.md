## ADDED Requirements

### Requirement: 專案里程碑管理
專案管理 SHALL 支援管理專案關鍵里程碑，追蹤預計與實際完成日期。

#### Scenario: 顯示里程碑列表
- **WHEN** 使用者在「概覽」標籤頁檢視專案
- **THEN** 顯示該專案的里程碑時間軸
- **AND** 每個里程碑顯示名稱、類型圖示、預計日期、實際日期、狀態

#### Scenario: 里程碑狀態顯示
- **WHEN** 里程碑有實際完成日期
- **THEN** 狀態顯示為「已完成」（綠色）
- **WHEN** 里程碑預計日期已過且無實際日期
- **THEN** 狀態顯示為「延遲」（紅色）
- **WHEN** 里程碑預計日期在 7 天內且無實際日期
- **THEN** 狀態顯示為「進行中」（藍色）
- **WHEN** 里程碑預計日期在 7 天後且無實際日期
- **THEN** 狀態顯示為「待處理」（灰色）

#### Scenario: 新增里程碑
- **WHEN** 使用者點擊「新增里程碑」按鈕
- **THEN** 顯示里程碑編輯表單
- **AND** 表單包含名稱、類型（下拉選單）、預計日期、實際日期、備註

#### Scenario: 里程碑類型選項
- **WHEN** 使用者選擇里程碑類型
- **THEN** 提供預設選項：設計完成、製造完成、交機、場測、驗收、自訂
- **AND** 選擇「自訂」時可輸入自訂名稱

#### Scenario: 編輯里程碑
- **WHEN** 使用者點擊里程碑的編輯按鈕
- **THEN** 顯示里程碑編輯表單
- **AND** 可修改所有里程碑資訊

#### Scenario: 標記里程碑完成
- **WHEN** 使用者在編輯時填入實際完成日期
- **THEN** 系統自動將狀態更新為「已完成」

#### Scenario: 刪除里程碑
- **WHEN** 使用者點擊里程碑的刪除按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 從專案移除該里程碑

#### Scenario: 里程碑排序
- **WHEN** 顯示里程碑列表
- **THEN** 按預計日期升序排列
- **AND** 無預計日期的里程碑排在最後

---

### Requirement: 里程碑 API
後端 SHALL 提供 RESTful API 供前端操作專案里程碑。

#### Scenario: 里程碑列表 API
- **WHEN** 前端請求 `GET /api/projects/{id}/milestones`
- **THEN** 後端返回該專案的里程碑列表
- **AND** 每個里程碑包含 id、名稱、類型、預計日期、實際日期、狀態、備註

#### Scenario: 新增里程碑 API
- **WHEN** 前端請求 `POST /api/projects/{id}/milestones`
- **THEN** 後端建立新里程碑記錄
- **AND** 返回新里程碑的完整資料

#### Scenario: 更新里程碑 API
- **WHEN** 前端請求 `PUT /api/projects/{id}/milestones/{mid}`
- **THEN** 後端更新里程碑記錄
- **AND** 重新計算狀態

#### Scenario: 刪除里程碑 API
- **WHEN** 前端請求 `DELETE /api/projects/{id}/milestones/{mid}`
- **THEN** 後端刪除里程碑記錄
- **AND** 返回成功狀態

---

### Requirement: 里程碑資料庫儲存
專案管理 SHALL 使用 PostgreSQL 資料庫儲存里程碑資料。

#### Scenario: 里程碑資料表
- **WHEN** 系統儲存里程碑
- **THEN** 里程碑資料存於 `project_milestones` 資料表
- **AND** 包含欄位：id、project_id、name、milestone_type、planned_date、actual_date、status、notes、sort_order、created_at、updated_at

#### Scenario: 級聯刪除
- **WHEN** 刪除專案
- **THEN** 同時刪除所有關聯的里程碑記錄
