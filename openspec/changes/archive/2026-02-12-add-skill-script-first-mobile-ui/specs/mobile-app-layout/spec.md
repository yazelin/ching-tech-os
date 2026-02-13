## MODIFIED Requirements

### Requirement: 手機版堆疊式導航
系統 SHALL 將 skill 管理流程在手機版統一為單欄堆疊式導航（列表 → 詳情 → 操作）。

#### Scenario: 手機開啟 skill 管理
- **WHEN** 使用者在手機上進入 skill 管理
- **THEN** 預設顯示列表頁
- **AND** 點擊 skill 後滑入詳情頁
- **AND** 主要操作在同一路徑完成，不需多層 modal 跳轉

---

## ADDED Requirements

### Requirement: 手機版 Skill 主要動作固定列
系統 SHALL 在手機版 skill 詳情頁提供底部固定操作列。

#### Scenario: 主要操作可視
- **WHEN** 使用者在手機上瀏覽 skill 詳情
- **THEN** 底部固定列持續顯示主要動作（安裝、更新、啟用/停用）
- **AND** 不需回捲頁面才能執行主要操作

---

### Requirement: 手機版次要設定收斂
系統 SHALL 將次要設定（進階欄位、低頻調整）收斂至 bottom sheet。

#### Scenario: 編輯次要設定
- **WHEN** 使用者在手機上需要調整次要設定
- **THEN** 以 bottom sheet 開啟設定區塊
- **AND** 關閉後返回原流程位置
