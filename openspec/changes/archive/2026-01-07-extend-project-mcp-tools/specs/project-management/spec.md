## MODIFIED Requirements

### Requirement: 專案成員管理
專案管理 SHALL 支援管理專案相關成員與聯絡人。

#### Scenario: 顯示成員列表
- **WHEN** 使用者切換到「成員」標籤頁
- **THEN** 顯示該專案的成員列表
- **AND** 每位成員顯示姓名、角色、公司、聯絡資訊

#### Scenario: 新增成員
- **WHEN** 使用者點擊「新增成員」按鈕
- **THEN** 顯示成員編輯表單
- **AND** 表單包含姓名、角色、公司、Email、電話、備註、內部/外部標記
- **AND** 內部成員可選擇關聯 CTOS 用戶（下拉選單）

#### Scenario: CTOS 用戶選擇器
- **WHEN** 使用者勾選「內部人員」
- **THEN** 顯示「關聯 CTOS 用戶」下拉選單
- **AND** 下拉選單列出所有 CTOS 用戶（username + display_name）
- **AND** 可選擇「不關聯」

#### Scenario: 外部人員隱藏選擇器
- **WHEN** 使用者取消勾選「內部人員」
- **THEN** 隱藏「關聯 CTOS 用戶」下拉選單
- **AND** 清除已選擇的用戶

#### Scenario: 編輯成員
- **WHEN** 使用者點擊成員項目的編輯按鈕
- **THEN** 顯示成員編輯表單
- **AND** 可修改所有成員資訊

#### Scenario: 刪除成員
- **WHEN** 使用者點擊成員項目的刪除按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 從專案移除該成員

---

## ADDED Requirements

### Requirement: 專案成員用戶關聯
專案成員 SHALL 可選擇關聯到 CTOS 用戶，用於權限控制。

#### Scenario: 資料表結構
- **WHEN** 系統儲存專案成員
- **THEN** `project_members` 包含 `user_id` 欄位
- **AND** 欄位為 INTEGER 類型，可為 NULL
- **AND** 外鍵關聯到 `users.id`，ON DELETE SET NULL

#### Scenario: 內部成員關聯用戶
- **WHEN** 新增或編輯內部成員（`is_internal=true`）
- **THEN** 可選擇關聯到 CTOS 用戶
- **AND** 關聯後該用戶可透過 Line Bot 操作此專案

#### Scenario: 外部聯絡人不關聯
- **WHEN** 新增外部聯絡人（`is_internal=false`）
- **THEN** `user_id` 保持 NULL
- **AND** 外部聯絡人僅作為聯絡資訊使用
