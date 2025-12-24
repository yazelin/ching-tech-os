# web-desktop Specification

## Purpose
TBD - created by archiving change add-web-desktop-ui. Update Purpose after archive.
## Requirements
### Requirement: Login Page
使用者 SHALL 能透過登入頁面進入系統桌面。

#### Scenario: 顯示登入表單
- **WHEN** 使用者訪問登入頁面
- **THEN** 系統顯示包含使用者名稱輸入框、密碼輸入框、登入按鈕的表單

#### Scenario: 模擬登入成功
- **WHEN** 使用者輸入任意使用者名稱和密碼並點擊登入按鈕
- **THEN** 系統導向至桌面主畫面
- **AND** 系統儲存使用者名稱於 session 中

#### Scenario: 未登入存取桌面
- **WHEN** 使用者未經登入直接訪問桌面頁面
- **THEN** 系統重新導向至登入頁面

---

### Requirement: Desktop Layout
桌面主畫面 SHALL 提供類似作業系統的三層佈局結構。

#### Scenario: 顯示完整桌面佈局
- **WHEN** 使用者成功登入後進入桌面
- **THEN** 系統顯示包含 Header Bar（頂部）、Desktop Area（中間）、Taskbar（底部）的完整佈局

#### Scenario: 全螢幕佈局
- **WHEN** 桌面載入完成
- **THEN** 佈局佔滿整個瀏覽器視窗
- **AND** 各區域不會出現溢出捲軸

---

### Requirement: Header Bar
Header Bar SHALL 位於畫面最上方，提供系統狀態資訊與基本操作。

#### Scenario: 顯示系統時間
- **WHEN** 桌面載入完成
- **THEN** Header Bar 右側區域顯示當前系統時間
- **AND** 時間每秒自動更新

#### Scenario: 顯示使用者資訊
- **WHEN** 桌面載入完成
- **THEN** Header Bar 右側區域顯示當前登入的使用者名稱

#### Scenario: 登出操作
- **WHEN** 使用者點擊登出按鈕
- **THEN** 系統清除 session 資料
- **AND** 系統重新導向至登入頁面

---

### Requirement: Desktop Area
Desktop Area SHALL 作為主要工作區域，顯示應用程式圖示。

#### Scenario: 顯示應用程式圖示
- **WHEN** 桌面載入完成
- **THEN** Desktop Area 顯示預設的應用程式圖示
- **AND** 每個圖示包含圖片和名稱標籤

#### Scenario: 圖示互動（第一階段為佔位）
- **WHEN** 使用者點擊任一應用程式圖示
- **THEN** 系統暫時無反應或顯示「功能開發中」提示

---

### Requirement: Taskbar
Taskbar SHALL 固定於畫面底部，提供類似 macOS Dock 的應用程式快速啟動列。

#### Scenario: 顯示 Dock 風格工作列
- **WHEN** 桌面載入完成
- **THEN** 畫面底部顯示固定的 Taskbar
- **AND** Taskbar 包含應用程式圖示

#### Scenario: 圖示 Hover 效果
- **WHEN** 使用者將滑鼠移至 Taskbar 上的圖示
- **THEN** 該圖示顯示放大或高亮效果

#### Scenario: Taskbar 置中顯示
- **WHEN** Taskbar 載入完成
- **THEN** Taskbar 內容水平置中於畫面底部

#### Scenario: 點擊開啟應用程式
- **WHEN** 使用者點擊 Taskbar 上尚未開啟的應用程式圖示
- **THEN** 系統開啟該應用程式視窗

#### Scenario: 點擊聚焦單一視窗應用程式
- **WHEN** 使用者點擊 Taskbar 上只有一個視窗的應用程式圖示
- **AND** 該視窗不在最上層
- **THEN** 系統將該視窗帶到最上層並聚焦

#### Scenario: 點擊顯示多視窗選單
- **WHEN** 使用者點擊 Taskbar 上有多個視窗的應用程式圖示
- **THEN** 系統顯示視窗選單，列出該應用程式的所有視窗
- **AND** 選單顯示每個視窗的標題

#### Scenario: 從視窗選單選擇視窗
- **WHEN** 使用者從視窗選單中點擊某個視窗
- **THEN** 系統將該視窗帶到最上層並聚焦
- **AND** 視窗選單關閉

#### Scenario: 點擊恢復最小化的應用程式
- **WHEN** 使用者點擊 Taskbar 上已最小化的應用程式圖示
- **THEN** 系統恢復該視窗並聚焦

#### Scenario: 顯示單一視窗運行指示器
- **WHEN** 應用程式只有一個視窗開啟中
- **THEN** 該應用程式在 Taskbar 上的圖示下方顯示一個運行指示器（小點）

#### Scenario: 顯示多視窗運行指示器
- **WHEN** 應用程式有多個視窗開啟中
- **THEN** 該應用程式在 Taskbar 上的圖示下方顯示多個運行指示器（小點）
- **AND** 小點數量對應視窗數量（最多顯示 3 個）

#### Scenario: 運行指示器消失
- **WHEN** 應用程式所有視窗都關閉
- **THEN** 運行指示器消失

---

### Requirement: Visual Design
系統介面 SHALL 採用現代化、簡潔的視覺設計風格。

#### Scenario: 深色/淺色主題基礎
- **WHEN** 系統載入
- **THEN** 使用預設主題配色（淺色或深色擇一）
- **AND** CSS Variables 定義主要顏色供後續主題切換使用

#### Scenario: 響應式設計
- **WHEN** 使用者在不同螢幕尺寸的裝置上存取系統
- **THEN** 介面元素能適當調整以保持可用性

---

### Requirement: Session Management
系統 SHALL 使用瀏覽器儲存機制管理使用者 session。

#### Scenario: Session 持久化
- **WHEN** 使用者成功登入
- **THEN** session 資料儲存於 localStorage 或 sessionStorage

#### Scenario: Session 檢查
- **WHEN** 桌面頁面載入
- **THEN** 系統檢查是否存在有效 session
- **AND** 若無有效 session 則重新導向至登入頁面

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

### Requirement: Window Snap
系統 SHALL 支援視窗拖曳到螢幕邊緣時自動調整大小並貼齊。

#### Scenario: Snap 到左邊緣
- **WHEN** 使用者拖曳視窗標題列到桌面左邊緣
- **THEN** 系統顯示 Snap 預覽區域（左半邊）
- **AND** 放開滑鼠後視窗調整為桌面寬度的 1/2 並貼齊左側

#### Scenario: Snap 到右邊緣
- **WHEN** 使用者拖曳視窗標題列到桌面右邊緣
- **THEN** 系統顯示 Snap 預覽區域（右半邊）
- **AND** 放開滑鼠後視窗調整為桌面寬度的 1/2 並貼齊右側

#### Scenario: Snap 到左上角
- **WHEN** 使用者拖曳視窗標題列到桌面左上角
- **THEN** 系統顯示 Snap 預覽區域（左上 1/4）
- **AND** 放開滑鼠後視窗調整為桌面的 1/4 並貼齊左上角

#### Scenario: Snap 到右上角
- **WHEN** 使用者拖曳視窗標題列到桌面右上角
- **THEN** 系統顯示 Snap 預覽區域（右上 1/4）
- **AND** 放開滑鼠後視窗調整為桌面的 1/4 並貼齊右上角

#### Scenario: Snap 到左下角
- **WHEN** 使用者拖曳視窗標題列到桌面左下角
- **THEN** 系統顯示 Snap 預覽區域（左下 1/4）
- **AND** 放開滑鼠後視窗調整為桌面的 1/4 並貼齊左下角

#### Scenario: Snap 到右下角
- **WHEN** 使用者拖曳視窗標題列到桌面右下角
- **THEN** 系統顯示 Snap 預覽區域（右下 1/4）
- **AND** 放開滑鼠後視窗調整為桌面的 1/4 並貼齊右下角

#### Scenario: Snap 到上邊緣最大化
- **WHEN** 使用者拖曳視窗標題列到桌面正上邊緣（非角落）
- **THEN** 系統顯示 Snap 預覽區域（全螢幕）
- **AND** 放開滑鼠後視窗最大化

#### Scenario: 取消 Snap 預覽
- **WHEN** 使用者拖曳視窗離開邊緣區域
- **THEN** Snap 預覽區域消失

#### Scenario: Snap 預覽視覺效果
- **WHEN** Snap 預覽區域顯示
- **THEN** 預覽區域以半透明樣式顯示目標位置和大小

### Requirement: 桌面圖示權限控制

桌面模組 SHALL 根據使用者權限顯示或隱藏應用程式圖示。

#### Scenario: 登入後載入權限
- Given 使用者成功登入
- When 系統載入桌面
- Then 呼叫 `GET /api/user/me` 取得權限資訊
- And 儲存權限資訊到 `window.currentUser`

#### Scenario: 顯示有權限的應用程式
- Given 使用者已登入且權限已載入
- When 桌面渲染應用程式圖示
- Then 只顯示使用者有權限的應用程式圖示
- And 無權限的應用程式圖示不顯示

#### Scenario: 管理員看到所有應用程式
- Given 管理員已登入
- When 桌面渲染應用程式圖示
- Then 顯示所有應用程式圖示

#### Scenario: 開啟無權限應用程式提示
- Given 應用程式圖示被隱藏
- When 使用者透過其他方式嘗試開啟該應用程式
- Then 顯示 toast 通知「您沒有使用 {應用程式名稱} 的權限，請聯繫管理員」

---

### Requirement: 使用者管理介面

系統設定應用程式 SHALL 提供使用者管理分頁供管理員使用。

#### Scenario: 顯示使用者管理分頁
- Given 管理員開啟系統設定
- When 系統設定視窗載入
- Then 顯示「使用者管理」分頁

#### Scenario: 非管理員隱藏使用者管理
- Given 非管理員使用者開啟系統設定
- When 系統設定視窗載入
- Then 不顯示「使用者管理」分頁

#### Scenario: 使用者列表顯示
- Given 管理員點擊「使用者管理」分頁
- When 分頁載入
- Then 顯示使用者列表表格
- And 每列顯示使用者名稱、顯示名稱、最後登入時間、操作按鈕
- And 管理員帳號標記為「🔒 管理員」

#### Scenario: 開啟權限設定對話框
- Given 管理員在使用者管理分頁
- When 點擊某使用者的「設定權限」按鈕
- Then 顯示權限設定對話框
- And 對話框顯示該使用者目前的權限設定

#### Scenario: 權限設定對話框內容
- Given 權限設定對話框已開啟
- When 對話框顯示
- Then 顯示「應用程式權限」區塊，列出所有應用程式勾選框
- And 顯示「知識庫權限」區塊，包含全域知識寫入與刪除勾選框
- And 顯示「取消」和「儲存」按鈕

#### Scenario: 儲存權限設定
- Given 管理員修改了權限設定
- When 點擊「儲存」按鈕
- Then 呼叫 API 更新權限
- And 顯示成功 toast 通知
- And 關閉對話框
- And 更新使用者列表

#### Scenario: 管理員權限不可編輯
- Given 管理員在使用者管理分頁
- When 查看管理員帳號的列
- Then 不顯示「設定權限」按鈕
- And 顯示「🔒 管理員」標記

