# web-desktop Spec Delta

## REMOVED Requirements

### Requirement: Taskbar
**Reason**: Dock 列功能與桌面圖示重複，應用程式無狀態保存需求。移除可簡化系統、減少維護成本並增加可用空間。
**Migration**: 用戶透過桌面圖示開啟應用程式，透過關閉按鈕或瀏覽器返回鍵回到桌面。

---

## MODIFIED Requirements

### Requirement: Desktop Layout
桌面主畫面 SHALL 提供類似作業系統的佈局結構。

#### Scenario: 桌機版桌面佈局
- **WHEN** 使用者在桌機上（螢幕寬度 > 768px）成功登入後進入桌面
- **THEN** 系統顯示包含 Header Bar（頂部）、Desktop Area（中間）的佈局

#### Scenario: 手機版桌面佈局
- **WHEN** 使用者在手機上（螢幕寬度 ≤ 768px）成功登入後進入桌面
- **THEN** 系統顯示包含 Header Bar（頂部）、Desktop Area（中間）的佈局
- **AND** 佈局充分利用手機螢幕空間

#### Scenario: 全螢幕佈局
- **WHEN** 桌面載入完成
- **THEN** 佈局佔滿整個瀏覽器視窗
- **AND** 各區域不會出現溢出捲軸

---

### Requirement: Desktop Area
Desktop Area SHALL 作為主要工作區域，顯示應用程式圖示。

#### Scenario: 顯示應用程式圖示
- **WHEN** 桌面載入完成
- **THEN** Desktop Area 顯示預設的應用程式圖示
- **AND** 每個圖示包含圖片和名稱標籤

#### Scenario: 單擊開啟應用程式
- **WHEN** 使用者單擊任一應用程式圖示
- **THEN** 系統開啟該應用程式視窗

#### Scenario: 手機版圖示排列
- **WHEN** 使用者在手機上（螢幕寬度 ≤ 768px）存取桌面
- **THEN** 圖示以適合手機的尺寸與間距排列
- **AND** 圖示觸控區域至少 44px × 44px

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

#### Scenario: 點擊 Logo 返回桌面
- **WHEN** 使用者點擊 Header Bar 左側的 Logo
- **AND** 目前有應用程式視窗開啟中
- **THEN** 系統關閉當前應用程式視窗
- **AND** 使用者返回桌面

---

### Requirement: Window Snap
系統 SHALL 在桌機上支援視窗拖曳到螢幕邊緣時自動調整大小並貼齊。

#### Scenario: Snap 到左邊緣
- **WHEN** 使用者在桌機上拖曳視窗標題列到桌面左邊緣
- **THEN** 系統顯示 Snap 預覽區域（左半邊）
- **AND** 放開滑鼠後視窗調整為桌面寬度的 1/2 並貼齊左側

#### Scenario: Snap 到右邊緣
- **WHEN** 使用者在桌機上拖曳視窗標題列到桌面右邊緣
- **THEN** 系統顯示 Snap 預覽區域（右半邊）
- **AND** 放開滑鼠後視窗調整為桌面寬度的 1/2 並貼齊右側

#### Scenario: Snap 到角落
- **WHEN** 使用者在桌機上拖曳視窗標題列到桌面角落
- **THEN** 系統顯示 Snap 預覽區域（對應 1/4 區域）
- **AND** 放開滑鼠後視窗調整為桌面的 1/4 並貼齊該角落

#### Scenario: Snap 到上邊緣最大化
- **WHEN** 使用者在桌機上拖曳視窗標題列到桌面正上邊緣（非角落）
- **THEN** 系統顯示 Snap 預覽區域（全螢幕）
- **AND** 放開滑鼠後視窗最大化

#### Scenario: 手機上停用 Snap
- **WHEN** 使用者在手機上（螢幕寬度 ≤ 768px）
- **THEN** Window Snap 功能停用

---

## ADDED Requirements

### Requirement: 手機版視窗行為
系統 SHALL 針對手機裝置提供優化的視窗顯示與操作體驗。

#### Scenario: 手機版視窗自動全螢幕
- **WHEN** 使用者在手機上（螢幕寬度 ≤ 768px）開啟應用程式
- **THEN** 視窗自動以全螢幕模式開啟
- **AND** 視窗填滿整個 Desktop Area

#### Scenario: 手機版隱藏視窗控制功能
- **WHEN** 使用者在手機上檢視應用程式視窗
- **THEN** 視窗標題列不顯示最大化、最小化按鈕
- **AND** 視窗無法拖曳移動
- **AND** 視窗無法調整大小

#### Scenario: 手機版視窗關閉
- **WHEN** 使用者在手機上點擊視窗的關閉按鈕
- **THEN** 視窗關閉
- **AND** 使用者返回桌面

#### Scenario: 手機版關閉按鈕易於點擊
- **WHEN** 使用者在手機上檢視應用程式視窗
- **THEN** 關閉按鈕的觸控區域至少 44px × 44px

---

### Requirement: 瀏覽器歷史整合
系統 SHALL 整合瀏覽器歷史紀錄，支援返回操作。

#### Scenario: 開啟應用程式時推入歷史
- **WHEN** 使用者開啟應用程式視窗
- **THEN** 系統使用 `history.pushState` 記錄狀態

#### Scenario: 瀏覽器返回關閉視窗
- **WHEN** 使用者按下瀏覽器返回鍵或手機返回手勢
- **AND** 目前有應用程式視窗開啟中
- **THEN** 系統關閉當前應用程式視窗
- **AND** 使用者返回桌面

#### Scenario: 桌面狀態不可再返回
- **WHEN** 使用者在桌面（無視窗開啟）按下瀏覽器返回鍵
- **THEN** 系統不執行任何操作（或依瀏覽器預設行為）

---

### Requirement: 桌機視窗控制簡化
系統 SHALL 簡化桌機視窗的控制按鈕。

#### Scenario: 桌機視窗標題列按鈕
- **WHEN** 使用者在桌機上檢視應用程式視窗
- **THEN** 視窗標題列顯示最大化、關閉按鈕
- **AND** 不顯示最小化按鈕

#### Scenario: 桌機視窗可拖曳縮放
- **WHEN** 使用者在桌機上操作應用程式視窗
- **THEN** 視窗可拖曳移動
- **AND** 視窗可調整大小
