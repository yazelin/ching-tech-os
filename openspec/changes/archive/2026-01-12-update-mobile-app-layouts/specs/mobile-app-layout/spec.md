# 手機版 App 內部佈局規範

## ADDED Requirements

### Requirement: 手機版底部 Tab Bar 導航
系統 SHALL 在手機版（≤768px）提供底部 Tab Bar 元件，讓 app 可快速切換 2-5 個主要功能區塊。

#### Scenario: 系統設定使用底部 Tab Bar
- **GIVEN** 使用者在手機上開啟系統設定
- **WHEN** 畫面寬度 ≤ 768px
- **THEN** 側邊欄隱藏，底部顯示固定 56px 的 Tab Bar
- **AND** 主內容區留出 `padding-bottom: 56px`

---

### Requirement: 手機版堆疊式導航
系統 SHALL 在手機版提供堆疊式導航（Stack Navigation），用於列表 → 詳情的階層式瀏覽。

#### Scenario: 專案管理列表切換詳情
- **GIVEN** 使用者在手機上瀏覽專案列表
- **WHEN** 點擊某個專案
- **THEN** 詳情頁從右側滑入覆蓋列表
- **AND** 顯示返回按鈕可返回列表

#### Scenario: 知識庫列表切換詳情
- **GIVEN** 使用者在手機上瀏覽知識庫列表
- **WHEN** 點擊某個知識項目
- **THEN** 詳情頁堆疊顯示
- **AND** 顯示返回按鈕可返回列表

---

### Requirement: 手機版可收合工具列
系統 SHALL 在手機版將多個篩選器/操作按鈕收合為可展開面板。

#### Scenario: AI Log 篩選器收合
- **GIVEN** 使用者在手機上開啟 AI Log
- **WHEN** 畫面寬度 ≤ 768px
- **THEN** 篩選器預設收合，只顯示「篩選」按鈕
- **AND** 點擊後展開完整篩選面板

---

### Requirement: 手機版卡片式列表取代表格
系統 SHALL 在手機版將資料表格轉換為卡片式列表顯示。

#### Scenario: AI Log 表格轉卡片
- **GIVEN** 使用者在手機上瀏覽 AI Log
- **WHEN** 畫面寬度 ≤ 768px
- **THEN** 資料以卡片列表形式顯示（非表格）
- **AND** 每張卡片包含狀態、時間、Agent、Token 等資訊

---

### Requirement: 手機版觸控友善設計
系統 SHALL 確保手機版所有互動元素符合觸控友善規範。

#### Scenario: 按鈕觸控區域
- **GIVEN** 任何可點擊的按鈕或連結
- **WHEN** 在手機版顯示
- **THEN** 觸控區域至少 44px × 44px
- **AND** 按鈕間距至少 8px

---

### Requirement: 手機版 Drawer 側邊欄
系統 SHALL 在手機版將側邊欄轉換為全螢幕 Drawer 形式。

#### Scenario: AI 助手聊天列表
- **GIVEN** 使用者在手機上開啟 AI 助手
- **WHEN** 點擊聊天列表切換按鈕
- **THEN** 聊天列表以全螢幕 Drawer 形式從左側滑入
- **AND** 背景顯示遮罩層

---

### Requirement: 手機版 Tab 橫向滾動
系統 SHALL 在手機版讓過多的 Tab 支援橫向滾動。

#### Scenario: Line Bot Tab 過多
- **GIVEN** Line Bot 有多個 Tab（群組、個人、設定等）
- **WHEN** 在手機版顯示
- **THEN** Tab 列可橫向滾動
- **AND** 不會擠壓或換行

#### Scenario: 專案管理內部 Tab
- **GIVEN** 專案詳情有多個 Tab（概覽、成員、會議、附件等）
- **WHEN** 在手機版顯示
- **THEN** Tab 列可橫向滾動
