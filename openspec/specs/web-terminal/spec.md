# web-terminal Specification

## Purpose
TBD - created by archiving change add-web-terminal. Update Purpose after archive.
## Requirements
### Requirement: 終端機視窗
系統 SHALL 提供終端機應用程式視窗，讓使用者執行伺服器命令。

#### Scenario: 開啟終端機
- **WHEN** 使用者雙擊桌面上的「終端機」圖示或點擊 Taskbar 上的終端機圖示
- **THEN** 系統開啟終端機視窗
- **AND** 視窗內顯示終端機模擬器介面
- **AND** 自動建立一個新的 shell session

#### Scenario: 終端機視窗佈局
- **WHEN** 終端機視窗開啟
- **THEN** 視窗標題列顯示「終端機」
- **AND** 視窗內容區顯示黑色背景的終端機畫面
- **AND** 終端機顯示 shell prompt（如 `user@host:~$`）

#### Scenario: 關閉終端機
- **WHEN** 使用者點擊終端機視窗的關閉按鈕
- **THEN** 系統關閉視窗
- **AND** 系統終止對應的 shell session

---

### Requirement: Shell Session 持久化
系統 SHALL 透過 PTY (Pseudo Terminal) 維護持久化的 shell session。

#### Scenario: 工作目錄保留
- **WHEN** 使用者執行 `cd /tmp` 命令
- **AND** 接著執行 `pwd` 命令
- **THEN** 輸出為 `/tmp`

#### Scenario: 環境變數保留
- **WHEN** 使用者執行 `export MY_VAR=hello` 命令
- **AND** 接著執行 `echo $MY_VAR` 命令
- **THEN** 輸出為 `hello`

#### Scenario: 命令歷史記錄
- **WHEN** 使用者在終端機中按下上方向鍵
- **THEN** 顯示上一個執行過的命令

---

### Requirement: 即時雙向通訊
系統 SHALL 透過 WebSocket 實現終端機的即時雙向通訊。

#### Scenario: 輸入即時傳送
- **WHEN** 使用者在終端機中輸入文字
- **THEN** 輸入內容即時發送到伺服器
- **AND** 伺服器回應即時顯示在終端機中

#### Scenario: 連續輸出串流
- **WHEN** 使用者執行會產生連續輸出的命令（如 `ping localhost`）
- **THEN** 輸出內容逐行即時顯示在終端機中
- **AND** 使用者可隨時按 Ctrl+C 中斷命令

#### Scenario: 長時間執行命令
- **WHEN** 使用者執行長時間執行的命令（如 `sleep 60`）
- **THEN** 終端機保持響應
- **AND** 使用者可等待命令完成或按 Ctrl+C 中斷

---

### Requirement: 互動式程式支援
系統 SHALL 支援互動式終端機程式的正確顯示與操作。

#### Scenario: 文字編輯器
- **WHEN** 使用者執行 `vim test.txt` 或 `nano test.txt`
- **THEN** 編輯器介面正確顯示
- **AND** 方向鍵、功能鍵正常運作
- **AND** 退出編輯器後恢復正常終端機狀態

#### Scenario: 系統監控工具
- **WHEN** 使用者執行 `htop` 或 `top`
- **THEN** 監控介面正確顯示
- **AND** 介面自動更新
- **AND** 按鍵操作正常運作

#### Scenario: 進度顯示
- **WHEN** 使用者執行帶有進度條的命令（如下載或壓縮）
- **THEN** 進度條正確顯示並更新

---

### Requirement: 終端機尺寸調整
系統 SHALL 支援終端機視窗尺寸調整時自動適應。

#### Scenario: 視窗縮放
- **WHEN** 使用者拖曳終端機視窗邊緣調整大小
- **THEN** 終端機內容區自動調整行數和列數
- **AND** PTY 接收到新的尺寸設定
- **AND** 正在執行的程式（如 vim）自動適應新尺寸

#### Scenario: 視窗最大化
- **WHEN** 使用者點擊視窗最大化按鈕
- **THEN** 終端機擴展至全螢幕
- **AND** 終端機行列數自動調整

---

### Requirement: 斷線重連
系統 SHALL 支援 WebSocket 斷線後自動重連並恢復 session。

#### Scenario: 短暫斷線重連
- **WHEN** 網路短暫斷線後恢復
- **THEN** WebSocket 自動重新連線
- **AND** 恢復原有的終端機 session
- **AND** 斷線期間的輸出不會遺失（在 PTY buffer 範圍內）

#### Scenario: 頁面刷新重連
- **WHEN** 使用者刷新瀏覽器頁面
- **AND** 在 5 分鐘內重新開啟終端機
- **THEN** 可選擇恢復先前的 session

#### Scenario: Session 超時
- **WHEN** WebSocket 斷線超過 5 分鐘
- **THEN** 伺服器自動清理對應的 PTY session
- **AND** 重連時顯示「Session 已過期」訊息
- **AND** 系統建立新的 session

---

### Requirement: 多終端機支援
系統 SHALL 支援同時開啟多個終端機視窗。

#### Scenario: 開啟多個終端機
- **WHEN** 使用者多次雙擊終端機圖示
- **THEN** 系統開啟多個獨立的終端機視窗
- **AND** 每個視窗擁有獨立的 shell session

#### Scenario: 獨立 Session
- **WHEN** 使用者在第一個終端機執行 `cd /tmp`
- **AND** 在第二個終端機執行 `pwd`
- **THEN** 第二個終端機顯示的目錄不受第一個終端機影響

---

### Requirement: 終端機外觀
系統 SHALL 提供符合現代終端機風格的視覺外觀。

#### Scenario: 預設配色
- **WHEN** 終端機開啟
- **THEN** 使用深色背景（黑色或深灰）
- **AND** 使用淺色前景文字（白色或淺灰）
- **AND** 使用等寬字型（monospace）

#### Scenario: 游標顯示
- **WHEN** 終端機獲得焦點
- **THEN** 顯示閃爍的游標
- **WHEN** 終端機失去焦點
- **THEN** 游標停止閃爍或變為半透明

#### Scenario: URL 識別
- **WHEN** 終端機輸出中包含 URL（如 `https://example.com`）
- **THEN** URL 文字變為可點擊的超連結
- **AND** 點擊後在新分頁開啟該 URL

