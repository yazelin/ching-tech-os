## ADDED Requirements

### Requirement: 知識專案關聯

知識庫 SHALL 支援專案級別的知識（scope=project），讓專案成員可以共同編輯。

#### Scenario: 專案知識欄位

- **WHEN** 知識的 scope 為 project
- **THEN** 知識元資料包含 `project_id` 欄位
- **AND** `project_id` 為有效的專案 UUID

#### Scenario: 建立專案知識

- **WHEN** 系統建立知識
- **AND** scope 設為 project
- **THEN** 必須提供 project_id
- **AND** 知識關聯到該專案

#### Scenario: 搜尋專案知識

- **WHEN** 使用者搜尋知識
- **AND** 選擇 scope=project 過濾
- **THEN** 只回傳專案級別的知識
- **AND** 只回傳用戶所屬專案的知識

---

## MODIFIED Requirements

### Requirement: 知識庫權限檢查

知識庫 API SHALL 根據使用者權限控制操作，包含專案知識和全域權限覆蓋。

#### Scenario: 讀取全域知識

- Given 任何登入使用者
- When 讀取全域知識
- Then 允許讀取

#### Scenario: 讀取個人知識（擁有者）

- Given 知識擁有者
- When 讀取自己的個人知識
- Then 允許讀取

#### Scenario: 讀取他人個人知識

- Given 非擁有者使用者
- When 嘗試讀取他人的個人知識
- Then 回傳 403 權限錯誤
- And 顯示「這是私人知識，您無權查看」

#### Scenario: 讀取專案知識（專案成員）

- Given 使用者是該專案的成員
- When 讀取專案知識
- Then 允許讀取

#### Scenario: 讀取專案知識（非成員）

- Given 使用者不是該專案的成員
- When 嘗試讀取專案知識
- Then 回傳 403 權限錯誤
- And 顯示「這是專案知識，您不是專案成員」

#### Scenario: 編輯專案知識（專案成員）

- Given 使用者是該專案的成員
- When 編輯專案知識
- Then 允許編輯

#### Scenario: 編輯專案知識（非成員）

- Given 使用者不是該專案的成員
- When 嘗試編輯專案知識
- Then 回傳 403 權限錯誤
- And 顯示「您不是專案成員，無法編輯此知識」

#### Scenario: 刪除專案知識（專案成員）

- Given 使用者是該專案的成員
- When 刪除專案知識
- Then 允許刪除

#### Scenario: 編輯全域知識（有權限）

- Given 使用者擁有全域知識寫入權限
- When 編輯全域知識
- Then 允許編輯

#### Scenario: 編輯全域知識（無權限）

- Given 使用者沒有全域知識寫入權限
- When 嘗試編輯全域知識
- Then 回傳 403 權限錯誤
- And 顯示「您沒有編輯全域知識的權限」

#### Scenario: 刪除全域知識（有權限）

- Given 使用者擁有全域知識刪除權限
- When 刪除全域知識
- Then 允許刪除

#### Scenario: 刪除全域知識（無權限）

- Given 使用者沒有全域知識刪除權限
- When 嘗試刪除全域知識
- Then 回傳 403 權限錯誤
- And 顯示「您沒有刪除全域知識的權限」

#### Scenario: 編輯/刪除個人知識

- Given 知識擁有者
- When 編輯或刪除自己的個人知識
- Then 允許操作

#### Scenario: 管理員操作任何知識

- Given 管理員使用者
- When 操作任何知識（全域、個人或專案）
- Then 允許操作

#### Scenario: 全域寫入權限用戶編輯任何知識

- Given 使用者擁有全域知識寫入權限
- When 編輯任何知識（個人或專案）
- Then 允許編輯

#### Scenario: 全域刪除權限用戶刪除任何知識

- Given 使用者擁有全域知識刪除權限
- When 刪除任何知識（個人或專案）
- Then 允許刪除
