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

#### Scenario: 點擊聚焦已開啟的應用程式
- **WHEN** 使用者點擊 Taskbar 上已開啟但不在最上層的應用程式圖示
- **THEN** 系統將該應用程式視窗帶到最上層並聚焦

#### Scenario: 點擊恢復最小化的應用程式
- **WHEN** 使用者點擊 Taskbar 上已最小化的應用程式圖示
- **THEN** 系統恢復該視窗並聚焦

#### Scenario: 顯示運行指示器
- **WHEN** 應用程式視窗開啟中
- **THEN** 該應用程式在 Taskbar 上的圖示下方顯示運行指示器（小點）
- **WHEN** 應用程式視窗關閉
- **THEN** 運行指示器消失

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

