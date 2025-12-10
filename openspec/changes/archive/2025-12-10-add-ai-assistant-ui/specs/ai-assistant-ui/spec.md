## ADDED Requirements

### Requirement: Window System
系統 SHALL 提供視窗管理功能，讓應用程式能以視窗形式在桌面上運行。

#### Scenario: 開啟應用程式視窗
- **WHEN** 使用者雙擊桌面應用程式圖示
- **THEN** 系統開啟對應的應用程式視窗
- **AND** 視窗顯示於桌面區域中央

#### Scenario: 關閉視窗
- **WHEN** 使用者點擊視窗標題列的關閉按鈕
- **THEN** 視窗從桌面移除

#### Scenario: 拖曳移動視窗
- **WHEN** 使用者按住視窗標題列並拖曳
- **THEN** 視窗隨滑鼠移動位置

#### Scenario: 視窗聚焦
- **WHEN** 使用者點擊任一視窗
- **THEN** 該視窗移至最上層（z-index 最高）
- **AND** 視窗標題列顯示聚焦狀態

---

### Requirement: AI Assistant Window Layout
AI 助手應用程式 SHALL 提供類似 ChatGPT 的左右分欄式介面佈局。

#### Scenario: 顯示完整介面佈局
- **WHEN** AI 助手應用程式視窗開啟
- **THEN** 視窗內顯示左側邊欄（對話列表）與右側主區域（對話內容）

#### Scenario: 左側邊欄內容
- **WHEN** AI 助手應用程式視窗開啟
- **THEN** 左側邊欄顯示歷史對話列表
- **AND** 每個對話項目顯示對話標題

#### Scenario: 左側邊欄展開收合
- **WHEN** 使用者點擊邊欄收合按鈕
- **THEN** 左側邊欄收合僅顯示圖示
- **WHEN** 使用者再次點擊展開按鈕
- **THEN** 左側邊欄展開顯示完整內容

---

### Requirement: AI Assistant Toolbar
AI 助手應用程式 SHALL 提供頂部工具列以進行對話管理。

#### Scenario: 新增對話
- **WHEN** 使用者點擊「新對話」按鈕
- **THEN** 系統建立一個新的空白對話
- **AND** 新對話加入左側對話列表
- **AND** 右側主區域切換至新對話

#### Scenario: 模型選擇
- **WHEN** 使用者點擊模型選擇下拉選單
- **THEN** 系統顯示可用的 AI 模型列表
- **WHEN** 使用者選擇一個模型
- **THEN** 當前對話的模型設定更新為所選模型

---

### Requirement: AI Assistant Message Display
AI 助手應用程式 SHALL 在右側主區域顯示對話訊息。

#### Scenario: 顯示對話訊息
- **WHEN** 使用者選擇一個對話
- **THEN** 右側主區域顯示該對話的所有訊息
- **AND** 使用者訊息與 AI 回應有明顯的視覺區分

#### Scenario: 訊息捲動
- **WHEN** 對話訊息超出顯示區域
- **THEN** 訊息區域可捲動瀏覽
- **AND** 新訊息自動捲動至可見範圍

---

### Requirement: AI Assistant Message Input
AI 助手應用程式 SHALL 提供訊息輸入區域。

#### Scenario: 輸入訊息
- **WHEN** AI 助手應用程式視窗開啟
- **THEN** 右側主區域底部顯示訊息輸入框與送出按鈕

#### Scenario: 送出訊息
- **WHEN** 使用者在輸入框輸入文字並點擊送出按鈕
- **THEN** 訊息顯示於對話訊息區
- **AND** 輸入框清空
- **AND** 系統顯示模擬的 AI 回應（暫定）

#### Scenario: 按 Enter 送出
- **WHEN** 使用者在輸入框按下 Enter 鍵
- **THEN** 系統送出訊息（等同點擊送出按鈕）

---

### Requirement: AI Assistant Chat Management
AI 助手應用程式 SHALL 支援多個對話 session 管理。

#### Scenario: 切換對話
- **WHEN** 使用者點擊左側對話列表中的某個對話
- **THEN** 右側主區域切換顯示該對話的訊息

#### Scenario: 對話標題自動生成
- **WHEN** 使用者在新對話中送出第一則訊息
- **THEN** 系統自動根據訊息內容生成對話標題（擷取前 N 字）

#### Scenario: 對話資料暫存
- **WHEN** 使用者進行對話操作
- **THEN** 對話資料暫存於瀏覽器 localStorage
- **AND** 重新載入頁面後對話資料保留
