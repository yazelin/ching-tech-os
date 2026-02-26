## ADDED Requirements

### Requirement: 知識庫公開存取旗標
系統 SHALL 支援標記知識庫項目為「公開」，允許未綁定用戶在受限模式下查詢。

#### Scenario: 知識項目公開旗標
- **WHEN** 系統儲存知識庫項目
- **THEN** Front Matter 中 SHALL 支援 `is_public` 布林欄位（預設 `false`）
- **AND** `index.json` 的 entry 中 SHALL 包含 `is_public` 欄位

#### Scenario: 設定項目為公開
- **WHEN** 有全域編輯權限的用戶更新知識項目
- **AND** 設定 `is_public: true`
- **THEN** 系統 SHALL 更新 Front Matter 和 index.json 中的 `is_public` 欄位
- **AND** 該項目可被受限模式的 `search_knowledge` 查詢到

#### Scenario: 預設為非公開
- **WHEN** 建立新的知識項目
- **AND** 未指定 `is_public`
- **THEN** 系統 SHALL 預設 `is_public` 為 `false`

### Requirement: 受限模式知識查詢過濾
`search_knowledge` 工具 SHALL 根據呼叫者身份過濾查詢結果。

#### Scenario: 已綁定用戶查詢（現有行為不變）
- **WHEN** 已綁定用戶（或 `ctos_user_id` 不為 NULL）呼叫 `search_knowledge`
- **THEN** 系統 SHALL 回傳所有符合條件的全域知識 + 個人知識
- **AND** 不受 `is_public` 旗標影響

#### Scenario: 未綁定用戶查詢（受限模式）
- **WHEN** 未綁定用戶（`ctos_user_id` 為 NULL）呼叫 `search_knowledge`
- **THEN** 系統 SHALL 僅回傳 `scope=global` 且 `is_public=true` 的知識項目
- **AND** 不回傳 `is_public=false` 的全域知識
- **AND** 不回傳任何個人知識

#### Scenario: 無公開知識時的回覆
- **WHEN** 未綁定用戶查詢知識庫
- **AND** 沒有符合條件的公開知識
- **THEN** 系統 SHALL 回傳空結果
- **AND** 不回傳錯誤訊息

### Requirement: 圖書館公開資料夾
圖書館（library）資料夾 SHALL 支援標記為「公開」，允許受限模式用戶查閱。

#### Scenario: 資料夾公開配置
- **WHEN** 管理員配置圖書館資料夾
- **THEN** 系統 SHALL 支援標記特定資料夾為公開
- **AND** 公開標記儲存方式與知識庫 `is_public` 一致

#### Scenario: 受限模式瀏覽圖書館
- **WHEN** 未綁定用戶在受限模式中使用 `list_library_folders`
- **THEN** 系統 SHALL 僅顯示標記為公開的資料夾
- **AND** 不顯示未標記為公開的資料夾

#### Scenario: 已綁定用戶瀏覽圖書館
- **WHEN** 已綁定用戶使用 `list_library_folders`
- **THEN** 系統 SHALL 顯示所有資料夾（現有行為不變）
