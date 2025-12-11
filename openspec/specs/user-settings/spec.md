# user-settings Specification

## Purpose
TBD - created by archiving change add-theme-settings. Update Purpose after archive.
## Requirements
### Requirement: 使用者偏好儲存
系統 SHALL 在 `users` 資料表中提供 `preferences` JSONB 欄位，用於儲存使用者個人化設定。

#### Scenario: 新使用者預設偏好
- **WHEN** 新使用者首次登入
- **THEN** `preferences` 欄位為空物件 `{}`

#### Scenario: 偏好結構擴展
- **WHEN** 系統需要新增偏好設定項目
- **THEN** 可直接在 JSONB 欄位中新增鍵值，無需資料庫 migration

---

### Requirement: 主題偏好 API
系統 SHALL 提供 REST API 讓前端取得與更新使用者的主題偏好。

#### Scenario: 取得使用者偏好
- **WHEN** 前端發送 `GET /api/user/preferences` 請求
- **THEN** 系統回傳使用者的偏好設定，包含 `theme` 欄位

#### Scenario: 更新主題偏好
- **WHEN** 前端發送 `PUT /api/user/preferences` 並帶有 `{ "theme": "light" }`
- **THEN** 系統更新資料庫中的偏好設定
- **AND** 回傳更新後的完整偏好設定

#### Scenario: 未登入存取
- **WHEN** 未認證的請求存取偏好 API
- **THEN** 系統回傳 401 Unauthorized

---

### Requirement: 主題切換機制
系統 SHALL 透過 HTML `data-theme` 屬性實現主題切換，支援即時預覽無需重新載入頁面。

#### Scenario: 切換至亮色主題
- **WHEN** 使用者選擇亮色主題
- **THEN** `document.documentElement.dataset.theme` 設為 `"light"`
- **AND** 所有 CSS 變數自動套用亮色主題數值

#### Scenario: 切換至暗色主題
- **WHEN** 使用者選擇暗色主題
- **THEN** `document.documentElement.dataset.theme` 設為 `"dark"` 或移除
- **AND** 所有 CSS 變數自動套用暗色主題數值

---

### Requirement: 亮色主題 CSS 變數
系統 SHALL 定義完整的亮色主題 CSS 變數，覆蓋 `:root` 中的暗色主題預設值。

#### Scenario: 亮色主題顏色對比
- **WHEN** 亮色主題啟用
- **THEN** 所有文字與背景的對比度符合 WCAG AA 標準（4.5:1）

#### Scenario: 亮色主題終端機
- **WHEN** 亮色主題啟用且終端機開啟
- **THEN** 終端機背景與文字顏色使用亮色主題的 `--terminal-*` 變數

---

### Requirement: 主題設定介面
系統 SHALL 提供「系統設定」應用程式，包含主題設定功能。

#### Scenario: 開啟設定應用程式
- **WHEN** 使用者點擊桌面上的「系統設定」圖示
- **THEN** 開啟設定視窗，預設顯示「外觀」分頁

#### Scenario: 主題預覽卡片
- **WHEN** 使用者進入外觀設定
- **THEN** 顯示暗色與亮色主題的預覽卡片
- **AND** 目前選擇的主題有明顯的選中標記

#### Scenario: 即時預覽
- **WHEN** 使用者點擊不同的主題卡片
- **THEN** 整個系統介面即時切換至該主題
- **AND** 預覽面板顯示各種 UI 元件的實際效果

#### Scenario: 儲存設定
- **WHEN** 使用者點擊「儲存設定」按鈕
- **THEN** 系統呼叫 API 將偏好儲存至資料庫
- **AND** 顯示儲存成功的提示訊息

---

### Requirement: 主題偏好持久化
系統 SHALL 在使用者登入後自動套用其儲存的主題偏好。

#### Scenario: 登入後套用偏好
- **WHEN** 使用者登入成功
- **THEN** 系統從 API 取得使用者偏好
- **AND** 自動套用其儲存的主題設定

#### Scenario: 本地快取
- **WHEN** 使用者偏好載入成功
- **THEN** 系統將偏好儲存至 localStorage
- **AND** 下次頁面載入時優先使用快取避免閃爍

#### Scenario: 偏好載入失敗
- **WHEN** API 無法回應或發生錯誤
- **THEN** 系統使用暗色主題作為預設值
- **AND** 不影響使用者正常使用系統

