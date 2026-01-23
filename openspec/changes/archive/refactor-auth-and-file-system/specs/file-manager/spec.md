## MODIFIED Requirements

### Requirement: 檔案管理視窗

系統 SHALL 提供檔案管理視窗，讓使用者瀏覽和管理 NAS 上的檔案。使用者 MUST 先連接 NAS 後才能瀏覽檔案。

#### Scenario: 開啟檔案管理（未連接 NAS）
- Given 使用者已登入並在桌面
- When 雙擊「檔案管理」圖示或從 Taskbar 開啟
- Then 開啟檔案管理視窗
- And 顯示「NAS 連線」對話框
- And 對話框包含 NAS IP、帳號、密碼輸入欄位

#### Scenario: 開啟檔案管理（已有連線記錄）
- Given 使用者之前已儲存 NAS 連線設定
- When 開啟檔案管理視窗
- Then 顯示「NAS 連線」對話框
- And 自動填入上次使用的 NAS IP 和帳號
- And 密碼欄位視設定決定是否自動填入

#### Scenario: 進入資料夾
- Given 檔案管理視窗已開啟且已連接 NAS
- When 雙擊資料夾
- Then 進入該資料夾並顯示內容
- And 導航列更新目前路徑

#### Scenario: 返回上層資料夾
- Given 使用者位於某資料夾內
- When 點擊「上一層」按鈕
- Then 返回父資料夾
- And 更新檔案列表和導航列

#### Scenario: 顯示檔案資訊
- Given 檔案管理視窗顯示檔案列表
- Then 每個項目顯示圖示、名稱、大小（檔案）、修改日期
- And 資料夾顯示資料夾圖示
- And 檔案根據類型顯示對應圖示

#### Scenario: 多選檔案
- Given 檔案管理視窗已開啟
- When 使用者按住 Ctrl 並點擊多個檔案
- Then 多個檔案被選取
- And 狀態列顯示選取數量

#### Scenario: 範圍選取
- Given 檔案管理視窗已開啟且已選取一個檔案
- When 使用者按住 Shift 並點擊另一個檔案
- Then 兩個檔案之間的所有項目被選取

---

## ADDED Requirements

### Requirement: NAS 連線對話框

系統 SHALL 提供 NAS 連線對話框，讓使用者輸入 NAS 伺服器資訊和憑證。

#### Scenario: 顯示連線對話框
- Given 使用者開啟檔案管理視窗
- When 尚未建立 NAS 連線
- Then 顯示連線對話框
- And 對話框包含以下欄位：
  - NAS IP/主機名稱（必填）
  - 帳號（必填）
  - 密碼（必填）
  - 記住此連線（勾選框）
  - 記住密碼（勾選框，需先勾選「記住此連線」）

#### Scenario: 成功連線 NAS
- Given 使用者在連線對話框
- When 輸入有效的 NAS 位址和憑證並按「連線」
- Then 系統驗證憑證
- And 取得 NAS 連線 token
- And 隱藏連線對話框
- And 顯示 NAS 共享資料夾列表

#### Scenario: 連線失敗 - 認證錯誤
- Given 使用者在連線對話框
- When 輸入錯誤的帳號或密碼
- Then 顯示錯誤訊息「帳號或密碼錯誤」
- And 對話框保持開啟

#### Scenario: 連線失敗 - 無法連線
- Given 使用者在連線對話框
- When NAS 位址無法連線
- Then 顯示錯誤訊息「無法連線至 NAS 伺服器」
- And 對話框保持開啟

#### Scenario: 取消連線
- Given 使用者在連線對話框
- When 點擊「取消」或關閉對話框
- Then 關閉連線對話框
- And 關閉檔案管理視窗

---

### Requirement: NAS 連線記憶

系統 SHALL 支援記住 NAS 連線設定（可選功能）。

#### Scenario: 儲存連線設定（不含密碼）
- Given 使用者勾選「記住此連線」但未勾選「記住密碼」
- When 成功連線
- Then 系統儲存 NAS IP 和帳號到 localStorage
- And 不儲存密碼
- And 下次開啟時自動填入 IP 和帳號

#### Scenario: 儲存連線設定（含密碼）
- Given 使用者同時勾選「記住此連線」和「記住密碼」
- When 成功連線
- Then 系統加密儲存 NAS IP、帳號、密碼到 localStorage
- And 下次開啟時自動填入所有欄位

#### Scenario: 管理已儲存的連線
- Given 使用者在連線對話框
- When 點擊「已儲存的連線」按鈕
- Then 顯示已儲存的 NAS 連線列表
- And 可選擇連線、編輯或刪除

#### Scenario: 刪除儲存的連線
- Given 使用者在已儲存連線列表
- When 點擊刪除按鈕
- Then 從 localStorage 移除該連線設定
- And 更新列表顯示

---

### Requirement: NAS 連線生命週期

系統 SHALL 管理 NAS 連線的生命週期，確保安全和資源管理。

#### Scenario: 連線自動延長
- Given 使用者已連接 NAS
- When 進行檔案操作（瀏覽、下載、上傳等）
- Then 系統自動延長連線有效期
- And 連線 token 預設有效期為 30 分鐘

#### Scenario: 連線逾時
- Given 使用者已連接 NAS
- When 超過 30 分鐘無任何檔案操作
- Then 連線自動斷開
- And 顯示「連線已逾時，請重新連線」訊息
- And 顯示連線對話框

#### Scenario: 主動斷開連線
- Given 使用者已連接 NAS
- When 點擊「斷開連線」按鈕或關閉檔案管理視窗
- Then 系統呼叫 API 斷開 NAS 連線
- And 清除本地連線 token

#### Scenario: 顯示連線狀態
- Given 檔案管理視窗已開啟
- Then 狀態列顯示目前連線的 NAS 資訊
- And 格式為「已連線：{IP} ({帳號})」
- And 提供「斷開連線」按鈕

---

### Requirement: NAS 連線切換

系統 SHALL 支援在檔案管理視窗內切換不同的 NAS 連線。

#### Scenario: 切換 NAS 連線
- Given 使用者已連接 NAS A
- When 點擊「連線其他 NAS」按鈕
- Then 顯示連線對話框
- And 成功連線後斷開 NAS A
- And 切換到新 NAS 的共享資料夾列表

#### Scenario: 保持多個連線（進階）
- Given 使用者需要同時存取多個 NAS
- When 開啟多個檔案管理視窗
- Then 每個視窗可連接不同的 NAS
- And 各視窗的連線相互獨立
