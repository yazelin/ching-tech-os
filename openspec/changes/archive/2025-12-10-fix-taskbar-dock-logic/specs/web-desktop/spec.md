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
