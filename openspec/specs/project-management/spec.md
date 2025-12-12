# project-management Specification

## Purpose
TBD - created by archiving change add-project-management. Update Purpose after archive.
## Requirements
### Requirement: 專案管理視窗佈局
專案管理應用程式 SHALL 提供雙欄式介面佈局與標籤頁切換。

#### Scenario: 顯示完整介面佈局
- **WHEN** 專案管理應用程式視窗開啟
- **THEN** 視窗內顯示上方工具列、左側專案列表、右側專案詳情面板

#### Scenario: 上方工具列
- **WHEN** 專案管理視窗開啟
- **THEN** 工具列顯示搜尋框、狀態過濾下拉選單、新增專案按鈕

#### Scenario: 左側專案列表
- **WHEN** 使用者載入專案管理
- **THEN** 左側顯示專案列表
- **AND** 每個專案顯示名稱、狀態標籤、更新時間

#### Scenario: 右側詳情面板
- **WHEN** 使用者選擇一個專案
- **THEN** 右側顯示標籤頁導航列
- **AND** 標籤頁包含：概覽、成員、會議、附件、連結

---

### Requirement: 專案 CRUD 操作
專案管理 SHALL 支援專案的新增、讀取、更新、刪除操作。

#### Scenario: 新增專案
- **WHEN** 使用者點擊「新增專案」按鈕
- **THEN** 顯示專案編輯表單
- **AND** 表單包含名稱、描述、狀態、開始日期、結束日期

#### Scenario: 編輯專案
- **WHEN** 使用者在檢視專案時點擊「編輯」按鈕
- **THEN** 切換至編輯模式
- **AND** 可修改專案所有欄位

#### Scenario: 儲存專案
- **WHEN** 使用者在編輯模式點擊「儲存」按鈕
- **THEN** 系統更新專案資料
- **AND** 顯示儲存成功通知

#### Scenario: 刪除專案
- **WHEN** 使用者點擊「刪除」按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認刪除
- **THEN** 從系統移除該專案及所有關聯資料（成員、會議、附件、連結）

---

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

### Requirement: 會議記錄管理
專案管理 SHALL 支援記錄與管理專案會議。

#### Scenario: 顯示會議列表
- **WHEN** 使用者切換到「會議」標籤頁
- **THEN** 顯示該專案的會議記錄列表
- **AND** 按日期降序排列
- **AND** 每筆會議顯示標題、日期、地點

#### Scenario: 新增會議記錄
- **WHEN** 使用者點擊「新增會議」按鈕
- **THEN** 顯示會議編輯表單
- **AND** 表單包含標題、日期時間、地點、參與人員、內容（Markdown 編輯器）

#### Scenario: 檢視會議內容
- **WHEN** 使用者點擊會議項目
- **THEN** 展開顯示會議完整內容
- **AND** Markdown 內容正確渲染

#### Scenario: 編輯會議記錄
- **WHEN** 使用者點擊會議項目的編輯按鈕
- **THEN** 顯示會議編輯表單
- **AND** 可修改所有會議資訊

#### Scenario: 刪除會議記錄
- **WHEN** 使用者點擊會議項目的刪除按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 從專案移除該會議記錄

---

### Requirement: 專案附件管理
專案管理 SHALL 支援上傳與管理專案相關檔案，包括 PDF、CAD 圖、圖片等。

#### Scenario: 顯示附件列表
- **WHEN** 使用者切換到「附件」標籤頁
- **THEN** 顯示該專案的附件列表
- **AND** 每個附件顯示檔名、類型圖示、大小、儲存位置（本機/NAS）、描述

#### Scenario: 上傳附件
- **WHEN** 使用者點擊「上傳附件」按鈕
- **THEN** 顯示上傳彈出視窗
- **AND** 支援拖放或選擇檔案
- **AND** 可輸入附件描述
- **AND** 顯示檔案大小與預估儲存位置

#### Scenario: 小型附件本機儲存
- **WHEN** 使用者上傳小於 1MB 的檔案
- **THEN** 系統將檔案存放於 `data/projects/attachments/{project_id}/`

#### Scenario: 大型附件 NAS 儲存
- **WHEN** 使用者上傳大於或等於 1MB 的檔案
- **THEN** 系統將檔案存放於 NAS `//192.168.11.50/擎添開發/ching-tech-os/projects/attachments/{project_id}/`
- **AND** 使用 `nas://projects/attachments/{project_id}/{filename}` 協定引用

#### Scenario: 預覽附件
- **WHEN** 使用者點擊附件的預覽按鈕
- **THEN** 依檔案類型開啟相應預覽器
- **AND** 圖片使用圖片檢視器
- **AND** PDF 使用 PDF 預覽器
- **AND** 其他檔案下載後以原生應用開啟

#### Scenario: 下載附件
- **WHEN** 使用者點擊附件的下載按鈕
- **THEN** 瀏覽器下載該檔案

#### Scenario: 刪除附件
- **WHEN** 使用者點擊附件的刪除按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 從系統移除該附件（包括實體檔案）

---

### Requirement: PDF 預覽功能
專案管理 SHALL 提供 PDF 檔案預覽功能。

#### Scenario: 載入 PDF.js
- **WHEN** 使用者首次預覽 PDF 檔案
- **THEN** 系統載入 pdf.js 函式庫

#### Scenario: 顯示 PDF 內容
- **WHEN** 使用者預覽 PDF 附件
- **THEN** 在彈出視窗中渲染 PDF 頁面
- **AND** 顯示頁碼導航控制項

#### Scenario: PDF 頁面導航
- **WHEN** 使用者點擊上一頁/下一頁按鈕
- **THEN** 切換顯示對應頁面

#### Scenario: PDF 縮放
- **WHEN** 使用者調整縮放比例
- **THEN** PDF 內容依比例縮放顯示

---

### Requirement: 專案連結管理
專案管理 SHALL 支援管理專案相關連結（NAS 路徑、外部網址），並自動判斷連結類型。

#### Scenario: 顯示連結列表
- **WHEN** 使用者切換到「連結」標籤頁
- **THEN** 顯示該專案的連結列表
- **AND** 每個連結顯示標題、自動判斷的類型圖示（NAS 資料夾/外部地球）、描述

#### Scenario: 新增連結
- **WHEN** 使用者點擊「新增連結」按鈕
- **THEN** 顯示連結編輯表單
- **AND** 表單包含標題、URL/路徑、描述
- **AND** 系統自動判斷連結類型（無需用戶選擇）

#### Scenario: 自動判斷連結類型
- **WHEN** 連結 URL 以 `/` 或 `nas://` 開頭
- **THEN** 系統判斷為 NAS 連結
- **WHEN** 連結 URL 以 `http://` 或 `https://` 開頭
- **THEN** 系統判斷為外部連結

#### Scenario: 開啟 NAS 連結
- **WHEN** 使用者點擊 NAS 連結項目
- **THEN** 系統開啟檔案管理器應用程式
- **AND** 檔案管理器導航至該 NAS 路徑
- **AND** 使用者可瀏覽、預覽該目錄下的檔案

#### Scenario: 開啟外部連結
- **WHEN** 使用者點擊外部連結項目
- **THEN** 系統在新視窗開啟該網址

#### Scenario: 編輯連結
- **WHEN** 使用者點擊連結項目的編輯按鈕
- **THEN** 顯示連結編輯表單

#### Scenario: 刪除連結
- **WHEN** 使用者點擊連結項目的刪除按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 從專案移除該連結

---

### Requirement: 專案管理 API
後端 SHALL 提供 RESTful API 供前端操作專案管理。

#### Scenario: 專案列表 API
- **WHEN** 前端請求 `GET /api/projects?status={status}&q={keyword}`
- **THEN** 後端返回符合條件的專案列表
- **AND** 每個專案包含 id、名稱、狀態、開始/結束日期、更新時間

#### Scenario: 專案詳情 API
- **WHEN** 前端請求 `GET /api/projects/{id}`
- **THEN** 後端返回專案完整資料

#### Scenario: 新增專案 API
- **WHEN** 前端請求 `POST /api/projects`
- **THEN** 後端建立新專案記錄
- **AND** 返回新專案的完整資料

#### Scenario: 更新專案 API
- **WHEN** 前端請求 `PUT /api/projects/{id}`
- **THEN** 後端更新專案記錄
- **AND** 更新 `updated_at` 時間戳

#### Scenario: 刪除專案 API
- **WHEN** 前端請求 `DELETE /api/projects/{id}`
- **THEN** 後端刪除專案記錄及所有關聯資料
- **AND** 返回成功狀態

#### Scenario: 成員 CRUD API
- **WHEN** 前端請求成員相關 API（GET/POST/PUT/DELETE /api/projects/{id}/members）
- **THEN** 後端執行對應的成員操作

#### Scenario: 會議 CRUD API
- **WHEN** 前端請求會議相關 API（GET/POST/PUT/DELETE /api/projects/{id}/meetings）
- **THEN** 後端執行對應的會議操作

#### Scenario: 附件上傳/下載 API
- **WHEN** 前端請求附件相關 API
- **THEN** 後端處理附件上傳/下載/刪除
- **AND** 自動判斷儲存位置（本機/NAS）

#### Scenario: 連結 CRUD API
- **WHEN** 前端請求連結相關 API（GET/POST/PUT/DELETE /api/projects/{id}/links）
- **THEN** 後端執行對應的連結操作

---

### Requirement: 資料庫儲存
專案管理 SHALL 使用 PostgreSQL 資料庫儲存專案結構化資料。

#### Scenario: 專案資料表
- **WHEN** 系統儲存專案
- **THEN** 專案資料存於 `projects` 資料表
- **AND** 包含欄位：id、name、description、status、start_date、end_date、created_at、updated_at、created_by

#### Scenario: 成員資料表
- **WHEN** 系統儲存專案成員
- **THEN** 成員資料存於 `project_members` 資料表
- **AND** 透過 `project_id` 外鍵關聯至專案

#### Scenario: 會議資料表
- **WHEN** 系統儲存會議記錄
- **THEN** 會議資料存於 `project_meetings` 資料表
- **AND** 透過 `project_id` 外鍵關聯至專案

#### Scenario: 附件資料表
- **WHEN** 系統儲存附件資訊
- **THEN** 附件元資料存於 `project_attachments` 資料表
- **AND** 實體檔案存於本機或 NAS

#### Scenario: 連結資料表
- **WHEN** 系統儲存連結
- **THEN** 連結資料存於 `project_links` 資料表
- **AND** 透過 `project_id` 外鍵關聯至專案

#### Scenario: 級聯刪除
- **WHEN** 刪除專案
- **THEN** 同時刪除所有關聯的成員、會議、附件、連結記錄
- **AND** 刪除附件實體檔案

---

### Requirement: CSS 設計系統
專案管理 SHALL 使用全域 CSS 變數確保設計一致性。

#### Scenario: 使用全域色彩變數
- **WHEN** 定義專案管理 UI 樣式
- **THEN** 使用 `main.css` 定義的全域色彩變數
- **AND** 保持與其他應用（如知識庫）視覺風格一致

#### Scenario: 標籤頁樣式
- **WHEN** 顯示標籤頁導航
- **THEN** 使用強調色變數標示當前選中的標籤
- **AND** 切換時有平滑過渡效果

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

### Requirement: 會議內容 Markdown 渲染
專案管理模組 SHALL 在會議詳情中正確渲染 Markdown 格式的會議內容。

#### Scenario: 會議內容 Markdown 渲染
- **WHEN** 使用者查看會議詳情
- **THEN** 會議內容使用 marked.js 渲染 Markdown
- **AND** 套用完整的 Markdown 樣式

#### Scenario: 會議內容樣式元素
- **GIVEN** 會議內容包含 Markdown 格式
- **THEN** 以下元素正確顯示：
  - 標題（h1-h6）
  - 列表（有序、無序）
  - 代碼塊（行內代碼、多行代碼）
  - 引用
  - 表格
  - 連結
  - 水平線

#### Scenario: 會議內容主題適配
- **WHEN** 使用者切換暗色/亮色主題
- **THEN** 會議內容的 Markdown 渲染樣式自動更新
- **AND** 代碼塊、引用、表格等元素的背景與文字顏色正確切換

#### Scenario: 無會議內容
- **GIVEN** 會議沒有內容
- **WHEN** 使用者查看會議詳情
- **THEN** 顯示「無會議內容」提示文字

