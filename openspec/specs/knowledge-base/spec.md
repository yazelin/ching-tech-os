# knowledge-base Specification

## Purpose
TBD - created by archiving change add-knowledge-base. Update Purpose after archive.
## Requirements
### Requirement: 知識庫視窗佈局
知識庫應用程式 SHALL 提供三欄式介面佈局。

#### Scenario: 顯示完整介面佈局
- **WHEN** 知識庫應用程式視窗開啟
- **THEN** 視窗內顯示上方工具列、左側列表區、右側內容區

#### Scenario: 上方工具列
- **WHEN** 知識庫視窗開啟
- **THEN** 工具列顯示搜尋框、標籤過濾下拉選單、新增知識按鈕

#### Scenario: 左側列表區
- **WHEN** 使用者執行搜尋或載入知識庫
- **THEN** 左側顯示知識條目列表
- **AND** 每個條目顯示標題、標籤摘要、更新時間

#### Scenario: 右側內容區
- **WHEN** 使用者選擇一個知識條目
- **THEN** 右側顯示知識完整內容（Markdown 渲染）
- **AND** 顯示知識元資料（作者、標籤、來源等）

---

### Requirement: 知識搜尋功能

知識庫搜尋 API SHALL 支援 scope 過濾參數。

#### Scenario: 依 scope 過濾搜尋
- Given 使用者執行搜尋
- When 選擇 scope 過濾條件
- Then 回傳符合該 scope 的知識
- And scope=personal 只回傳自己的個人知識

### Requirement: 知識 CRUD 操作
知識庫 SHALL 支援知識的新增、讀取、更新、刪除操作。

#### Scenario: 新增知識
- **WHEN** 使用者點擊「新增知識」按鈕
- **THEN** 顯示知識編輯表單
- **AND** 表單包含標題、內容（Markdown 編輯器）、標籤選擇

#### Scenario: 編輯知識
- **WHEN** 使用者在檢視知識時點擊「編輯」按鈕
- **THEN** 切換至編輯模式
- **AND** 可修改標題、內容、標籤

#### Scenario: 儲存知識
- **WHEN** 使用者在編輯模式點擊「儲存」按鈕
- **THEN** 系統更新知識檔案與索引
- **AND** 顯示儲存成功通知

#### Scenario: 刪除知識
- **WHEN** 使用者點擊「刪除」按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認刪除
- **THEN** 從系統移除該知識檔案與索引記錄

---

### Requirement: 知識元資料管理
知識庫 SHALL 使用 YAML Front Matter 儲存知識元資料。

#### Scenario: 顯示元資料
- **WHEN** 使用者檢視知識內容
- **THEN** 元資料區顯示作者、建立時間、更新時間
- **AND** 顯示標籤（專案、類型、角色、主題）
- **AND** 顯示來源資訊（若有）
- **AND** 顯示關聯知識（若有）

#### Scenario: 編輯標籤
- **WHEN** 使用者編輯知識
- **THEN** 可從預定義標籤選擇或新增自訂標籤
- **AND** 標籤類型包含：專案、類型、角色、層級、主題

#### Scenario: 設定關聯知識
- **WHEN** 使用者編輯知識的關聯欄位
- **THEN** 可搜尋並選擇其他知識作為關聯
- **AND** 關聯知識在檢視時可直接點擊導航

---

### Requirement: 知識檔案儲存
知識庫 SHALL 以檔案方式儲存知識，支援 Git 版本控制。

#### Scenario: 檔案結構
- **WHEN** 系統儲存知識
- **THEN** 知識存放於 `data/knowledge/entries/` 目錄
- **AND** 檔名格式為 `kb-{id}-{slug}.md`
- **AND** 附件存放於 `data/knowledge/assets/`

#### Scenario: 索引維護
- **WHEN** 知識新增、修改或刪除
- **THEN** 系統自動更新 `data/knowledge/index.json`
- **AND** 索引包含所有知識的元資料摘要

#### Scenario: 重建索引
- **WHEN** 管理者執行「重建索引」操作
- **THEN** 系統重新掃描所有知識檔案
- **AND** 重新建立 `index.json`

---

### Requirement: Markdown 渲染
知識庫 SHALL 支援 Markdown 格式渲染與圖片顯示。

#### Scenario: 渲染 Markdown 內容
- **WHEN** 使用者檢視知識
- **THEN** Markdown 內容正確渲染（標題、列表、程式碼區塊等）

#### Scenario: 顯示內嵌圖片
- **WHEN** 知識內容包含相對路徑圖片
- **THEN** 圖片正確載入並顯示

#### Scenario: 程式碼高亮
- **WHEN** 知識內容包含程式碼區塊
- **THEN** 程式碼依據語言標記高亮顯示

---

### Requirement: 知識庫 API
後端 SHALL 提供 RESTful API 供前端操作知識庫。

#### Scenario: 搜尋知識 API
- **WHEN** 前端請求 `GET /api/knowledge?q={keyword}&tags={tags}`
- **THEN** 後端返回符合條件的知識列表
- **AND** 每個知識包含 id、標題、標籤摘要、更新時間

#### Scenario: 取得知識詳情 API
- **WHEN** 前端請求 `GET /api/knowledge/{id}`
- **THEN** 後端返回完整知識內容與元資料

#### Scenario: 新增知識 API
- **WHEN** 前端請求 `POST /api/knowledge`
- **THEN** 後端建立新知識檔案與索引記錄
- **AND** 返回新知識的完整資料

#### Scenario: 更新知識 API
- **WHEN** 前端請求 `PUT /api/knowledge/{id}`
- **THEN** 後端更新知識檔案與索引記錄
- **AND** 更新 `updated_at` 時間戳

#### Scenario: 刪除知識 API
- **WHEN** 前端請求 `DELETE /api/knowledge/{id}`
- **THEN** 後端刪除知識檔案與索引記錄
- **AND** 返回成功狀態

#### Scenario: 取得標籤列表 API
- **WHEN** 前端請求 `GET /api/knowledge/tags`
- **THEN** 後端返回所有可用標籤（按類型分組）

---

### Requirement: 版本歷史功能
知識庫 SHALL 支援查看知識的 Git 版本歷史。

#### Scenario: 顯示版本歷史按鈕
- **WHEN** 使用者檢視知識內容
- **THEN** 右側內容區顯示「版本歷史」按鈕

#### Scenario: 查看版本歷史列表
- **WHEN** 使用者點擊「版本歷史」按鈕
- **THEN** 系統顯示該知識的 Git commit 歷史列表
- **AND** 每筆記錄顯示時間、作者、commit message

#### Scenario: 查看特定版本內容
- **WHEN** 使用者點擊版本歷史中的某筆記錄
- **THEN** 系統顯示該版本的知識內容

#### Scenario: 版本歷史 API
- **WHEN** 前端請求 `GET /api/knowledge/{id}/history`
- **THEN** 後端使用 `git log --follow` 取得檔案歷史
- **AND** 返回 commit 列表（hash、時間、作者、訊息）

#### Scenario: 取得特定版本 API
- **WHEN** 前端請求 `GET /api/knowledge/{id}/version/{commit}`
- **THEN** 後端使用 `git show {commit}:{path}` 取得該版本內容
- **AND** 返回該版本的知識內容

---

### Requirement: 大型附件 NAS 儲存
知識庫 SHALL 將大型附件儲存於 NAS，避免 Git 膨脹。

#### Scenario: 小型附件本機儲存
- **WHEN** 使用者上傳小於 1MB 的圖片
- **THEN** 系統將圖片存放於 `data/knowledge/assets/images/`
- **AND** 圖片隨 Git 追蹤

#### Scenario: 大型附件 NAS 儲存
- **WHEN** 使用者上傳大於或等於 1MB 的附件
- **THEN** 系統將附件存放於 NAS `//192.168.11.50/擎添開發/ching-tech-os/knowledge/attachments/{kb-id}/`
- **AND** 附件不進入 Git

#### Scenario: NAS 附件引用
- **WHEN** 知識包含 NAS 附件
- **THEN** 元資料 attachments 欄位記錄附件資訊
- **AND** 使用 `nas://knowledge/attachments/{kb-id}/{filename}` 協定引用

#### Scenario: 顯示 NAS 附件
- **WHEN** 使用者檢視包含 NAS 附件的知識
- **THEN** 前端透過後端 API 代理載入附件
- **AND** 附件正確顯示（圖片、影片等）

#### Scenario: 附件區固定底部顯示
- **WHEN** 使用者檢視知識內容
- **THEN** 附件區固定顯示於內容區底部
- **AND** 無需捲動即可查看附件列表
- **AND** 內容過長時僅內容區捲動，附件區維持可見

#### Scenario: 上傳附件彈出視窗
- **WHEN** 使用者在編輯模式點擊「新增附件」按鈕
- **THEN** 顯示上傳附件彈出視窗
- **AND** 視窗包含檔案選擇器、描述輸入欄位
- **AND** 顯示檔案大小預估與儲存位置提示（本機/NAS）

#### Scenario: 編輯附件元資料
- **WHEN** 使用者點擊附件的編輯按鈕
- **THEN** 顯示附件編輯表單
- **AND** 可修改附件描述文字
- **WHEN** 使用者儲存修改
- **THEN** 系統更新附件元資料（不移動檔案）

#### Scenario: 刪除知識連帶刪除附件
- **WHEN** 使用者確認刪除知識
- **THEN** 系統刪除該知識的所有附件（本機與 NAS）
- **AND** 刪除知識檔案與索引記錄
- **AND** 若 NAS 附件目錄為空則一併刪除

---

### Requirement: CSS 設計系統
知識庫 SHALL 使用全域 CSS 變數確保設計一致性。

#### Scenario: 使用全域色彩變數
- **WHEN** 定義知識庫 UI 樣式
- **THEN** 使用 `main.css` 定義的全域色彩變數
- **AND** 包含：`--bg-surface`、`--border-light`、`--accent-bg-subtle` 等

#### Scenario: 表面與邊框變數
- **WHEN** 需要背景或邊框樣式
- **THEN** 使用以下變數：
  - `--bg-surface`：基礎表面背景
  - `--bg-surface-dark`：較深表面背景
  - `--bg-overlay`：疊層背景
  - `--border-subtle`：淡色邊框
  - `--border-light`：淺色邊框
  - `--border-strong`：明顯邊框

#### Scenario: 強調色變數
- **WHEN** 需要強調色相關樣式
- **THEN** 使用以下變數：
  - `--accent-bg-subtle`：淡強調色背景
  - `--accent-bg-light`：淺強調色背景
  - `--accent-border`：強調色邊框

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

