## ADDED Requirements

### Requirement: 使用者資訊視窗
系統 SHALL 提供使用者資訊視窗，讓使用者檢視和編輯個人資料。

#### Scenario: 開啟使用者資訊視窗
- Given 使用者已登入並在桌面
- When 點擊右上角的使用者名稱
- Then 開啟使用者資訊視窗
- And 顯示目前的使用者資訊

#### Scenario: 顯示使用者資訊
- Given 使用者資訊視窗已開啟
- Then 視窗顯示 username（唯讀）
- And 顯示 display_name（可編輯）
- And 顯示首次登入時間 created_at
- And 顯示最後登入時間 last_login_at

#### Scenario: 編輯顯示名稱
- Given 使用者資訊視窗已開啟
- When 修改 display_name 欄位並點擊儲存
- Then 系統呼叫 API 更新資料
- And 顯示儲存成功提示
- And 右上角的使用者名稱顯示更新

#### Scenario: 關閉使用者資訊視窗
- Given 使用者資訊視窗已開啟
- When 點擊關閉按鈕或視窗外區域
- Then 視窗關閉
