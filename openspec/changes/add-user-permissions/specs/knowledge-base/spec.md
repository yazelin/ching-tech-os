# knowledge-base Specification Delta

## ADDED Requirements

### Requirement: 知識分類（全域/個人）

知識庫 SHALL 區分全域知識與個人知識。

#### Scenario: 知識擁有者欄位
- Given 知識檔案使用 YAML Front Matter
- When 儲存知識
- Then Front Matter 包含 `owner` 欄位（使用者名稱或 null）
- And Front Matter 包含 `scope` 欄位（global 或 personal）

#### Scenario: 建立個人知識
- Given 使用者新增知識
- When 選擇「個人知識」scope
- Then `owner` 設為目前使用者名稱
- And `scope` 設為 personal
- And 只有擁有者可以編輯和刪除

#### Scenario: 建立全域知識
- Given 使用者新增知識
- And 使用者擁有全域知識寫入權限
- When 選擇「全域知識」scope
- Then `owner` 設為 null
- And `scope` 設為 global

#### Scenario: 無權限建立全域知識
- Given 使用者新增知識
- And 使用者沒有全域知識寫入權限
- When 嘗試選擇「全域知識」scope
- Then scope 選項顯示為禁用狀態
- And 顯示提示「您沒有建立全域知識的權限」

---

### Requirement: 知識庫權限檢查

知識庫 API SHALL 根據使用者權限控制操作。

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
- When 操作任何知識（全域或個人）
- Then 允許操作

---

### Requirement: 知識庫 UI 權限顯示

知識庫介面 SHALL 根據權限顯示適當的操作選項。

#### Scenario: 知識列表顯示 scope 標記
- Given 使用者瀏覽知識列表
- When 知識列表顯示
- Then 全域知識顯示「🌐 全域」標記
- And 個人知識顯示「👤 個人」標記

#### Scenario: 篩選 scope
- Given 使用者在知識庫
- When 使用 scope 過濾下拉選單
- Then 可選擇「全部」、「全域知識」、「個人知識」
- And 「個人知識」只顯示自己的知識

#### Scenario: 新增知識 scope 選擇
- Given 使用者新增知識
- When 顯示新增表單
- Then 顯示 scope 選擇（全域/個人）
- And 預設選擇「個人」
- And 若無全域寫入權限，全域選項顯示禁用

#### Scenario: 無權限操作禁用
- Given 使用者沒有全域知識寫入權限
- When 瀏覽全域知識
- Then 編輯按鈕顯示禁用狀態
- And hover 顯示「您沒有編輯權限」提示

#### Scenario: 無權限刪除禁用
- Given 使用者沒有全域知識刪除權限
- When 瀏覽全域知識
- Then 刪除按鈕顯示禁用狀態
- And hover 顯示「您沒有刪除權限」提示

---

## MODIFIED Requirements

### Requirement: 知識搜尋功能

知識庫搜尋 API SHALL 支援 scope 過濾參數。

#### Scenario: 依 scope 過濾搜尋
- Given 使用者執行搜尋
- When 選擇 scope 過濾條件
- Then 回傳符合該 scope 的知識
- And scope=personal 只回傳自己的個人知識
