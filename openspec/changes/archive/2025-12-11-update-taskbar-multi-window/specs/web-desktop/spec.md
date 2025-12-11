## MODIFIED Requirements

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

## ADDED Requirements

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
