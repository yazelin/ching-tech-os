## ADDED Requirements

### Requirement: 訊息資料模型
訊息中心 SHALL 支援多維度分類的訊息儲存系統。

#### Scenario: 訊息嚴重程度分類
- **GIVEN** 系統需要記錄訊息
- **WHEN** 建立新訊息
- **THEN** 必須指定嚴重程度：debug、info、warning、error、critical

#### Scenario: 訊息來源分類
- **GIVEN** 系統需要記錄訊息
- **WHEN** 建立新訊息
- **THEN** 必須指定來源：system、security、app、user

#### Scenario: 訊息細分類
- **GIVEN** 訊息需要更精細的分類
- **WHEN** 建立訊息並指定 category
- **THEN** 系統儲存細分類（如 auth、file-manager、ai-assistant）

#### Scenario: 訊息 metadata
- **GIVEN** 訊息需要附加結構化資料
- **WHEN** 建立訊息並提供 metadata
- **THEN** 系統以 JSONB 格式儲存附加資料

---

### Requirement: 訊息查詢 API
訊息中心 SHALL 提供完整的訊息查詢功能。

#### Scenario: 依嚴重程度過濾
- **GIVEN** 使用者已登入
- **WHEN** 呼叫 GET /api/messages?severity=error,warning
- **THEN** 系統回傳符合嚴重程度的訊息列表

#### Scenario: 依來源過濾
- **GIVEN** 使用者已登入
- **WHEN** 呼叫 GET /api/messages?source=security
- **THEN** 系統回傳來自指定來源的訊息列表

#### Scenario: 依日期範圍過濾
- **GIVEN** 使用者已登入
- **WHEN** 呼叫 GET /api/messages?start_date=2025-01-01&end_date=2025-01-31
- **THEN** 系統回傳指定日期範圍內的訊息

#### Scenario: 關鍵字搜尋
- **GIVEN** 使用者已登入
- **WHEN** 呼叫 GET /api/messages?search=登入
- **THEN** 系統回傳標題或內容包含關鍵字的訊息

#### Scenario: 分頁查詢
- **GIVEN** 訊息數量超過單頁限制
- **WHEN** 呼叫 GET /api/messages?page=2&limit=20
- **THEN** 系統回傳第 2 頁、每頁 20 筆的訊息
- **AND** 回應包含總筆數與分頁資訊

#### Scenario: 取得單一訊息詳情
- **GIVEN** 使用者已登入
- **WHEN** 呼叫 GET /api/messages/{id}
- **THEN** 系統回傳該訊息的完整資訊（含 metadata）

---

### Requirement: 訊息已讀狀態
訊息中心 SHALL 追蹤訊息的已讀狀態。

#### Scenario: 取得未讀訊息數量
- **GIVEN** 使用者已登入
- **WHEN** 呼叫 GET /api/messages/unread-count
- **THEN** 系統回傳該使用者的未讀訊息數量

#### Scenario: 標記訊息為已讀
- **GIVEN** 使用者已登入且有未讀訊息
- **WHEN** 呼叫 POST /api/messages/mark-read 並提供訊息 ID 列表
- **THEN** 指定訊息標記為已讀

#### Scenario: 標記全部為已讀
- **GIVEN** 使用者已登入且有未讀訊息
- **WHEN** 呼叫 POST /api/messages/mark-read 並設定 all=true
- **THEN** 該使用者所有訊息標記為已讀

---

### Requirement: 即時訊息推送
訊息中心 SHALL 透過 WebSocket 即時推送新訊息。

#### Scenario: 推送新訊息通知
- **GIVEN** 使用者已登入且連接 WebSocket
- **WHEN** 系統產生與該使用者相關的新訊息
- **THEN** 透過 WebSocket 推送 message:new 事件
- **AND** 事件包含訊息摘要資訊

#### Scenario: 推送未讀數量更新
- **GIVEN** 使用者已登入且連接 WebSocket
- **WHEN** 未讀訊息數量變更
- **THEN** 透過 WebSocket 推送 message:unread_count 事件

#### Scenario: 警告以上自動顯示 Toast
- **GIVEN** 收到 severity 為 warning、error 或 critical 的新訊息
- **WHEN** 前端收到 message:new 事件
- **THEN** 自動顯示 Toast 通知提醒使用者

---

### Requirement: 登入記錄追蹤
訊息中心 SHALL 記錄完整的登入歷史資訊。

#### Scenario: 記錄成功登入
- **GIVEN** 使用者嘗試登入
- **WHEN** 登入成功
- **THEN** 系統記錄：時間、使用者、IP、User-Agent、Session ID
- **AND** 解析並記錄地理位置（國家、城市、經緯度）
- **AND** 記錄裝置指紋與裝置類型

#### Scenario: 記錄失敗登入
- **GIVEN** 使用者嘗試登入
- **WHEN** 登入失敗
- **THEN** 系統記錄所有資訊（同成功登入）
- **AND** 記錄失敗原因

#### Scenario: 查詢登入記錄
- **GIVEN** 使用者已登入
- **WHEN** 呼叫 GET /api/login-records
- **THEN** 系統回傳登入記錄列表（支援過濾與分頁）

#### Scenario: 查詢最近登入
- **GIVEN** 使用者已登入
- **WHEN** 呼叫 GET /api/login-records/recent?limit=10
- **THEN** 系統回傳該使用者最近 10 筆登入記錄

---

### Requirement: 裝置指紋識別
訊息中心 SHALL 支援裝置指紋以識別登入裝置。

#### Scenario: 產生裝置指紋
- **GIVEN** 使用者在登入頁面
- **WHEN** 頁面載入完成
- **THEN** 前端產生裝置指紋（結合螢幕、語言、Canvas 等資訊）

#### Scenario: 傳送裝置指紋
- **GIVEN** 使用者提交登入
- **WHEN** 送出登入請求
- **THEN** 請求包含裝置指紋與裝置資訊（類型、瀏覽器、OS）

#### Scenario: 識別同一裝置
- **GIVEN** 同一裝置多次登入
- **WHEN** 查詢登入記錄
- **THEN** 可依裝置指紋辨識來自同一裝置的登入

---

### Requirement: 地理位置解析
訊息中心 SHALL 支援 IP 地理位置解析。

#### Scenario: 解析 IP 地理位置
- **GIVEN** 登入請求包含 IP 位址
- **WHEN** 記錄登入
- **THEN** 系統使用 GeoIP 資料庫解析地理位置
- **AND** 記錄國家、城市、經緯度

#### Scenario: 無法解析時處理
- **GIVEN** IP 位址無法解析（如內網 IP）
- **WHEN** 記錄登入
- **THEN** 地理位置欄位設為 null
- **AND** 不影響登入記錄的建立

---

### Requirement: 訊息保留與清理
訊息中心 SHALL 自動管理訊息生命週期。

#### Scenario: 訊息保留期限
- **GIVEN** 系統設定訊息保留 1 年
- **WHEN** 訊息存在超過 1 年
- **THEN** 該訊息在清理排程執行時被刪除

#### Scenario: 自動清理排程
- **GIVEN** 清理排程已設定
- **WHEN** 排程執行時間到達（每日）
- **THEN** 系統刪除超過保留期限的訊息分區

#### Scenario: 分區表管理
- **GIVEN** 訊息使用分區表儲存
- **WHEN** 新月份開始
- **THEN** 系統自動建立新的月度分區

---

### Requirement: 訊息中心前端視窗
訊息中心 SHALL 提供獨立的前端視窗應用程式。

#### Scenario: 開啟訊息中心
- **GIVEN** 使用者已登入
- **WHEN** 點擊 Header Bar 的訊息圖示或 Taskbar 的訊息中心圖示
- **THEN** 開啟訊息中心視窗

#### Scenario: 顯示訊息列表
- **GIVEN** 訊息中心視窗已開啟
- **WHEN** 視窗載入
- **THEN** 顯示依時間分組的訊息列表（今天、昨天、更早）

#### Scenario: 過濾訊息
- **GIVEN** 訊息中心視窗已開啟
- **WHEN** 選擇嚴重程度、來源或日期範圍過濾
- **THEN** 列表即時更新顯示符合條件的訊息

#### Scenario: 搜尋訊息
- **GIVEN** 訊息中心視窗已開啟
- **WHEN** 輸入關鍵字並送出搜尋
- **THEN** 列表顯示符合關鍵字的訊息

#### Scenario: 查看訊息詳情
- **GIVEN** 訊息中心視窗顯示訊息列表
- **WHEN** 點擊某訊息
- **THEN** 展開或切換至詳情面板
- **AND** 顯示完整內容與 metadata

#### Scenario: 分頁瀏覽
- **GIVEN** 訊息數量超過單頁顯示
- **WHEN** 點擊分頁控制項
- **THEN** 載入並顯示對應頁的訊息

---

### Requirement: Header Bar 整合
訊息中心 SHALL 與系統 Header Bar 整合顯示未讀狀態。

#### Scenario: 顯示未讀數量
- **GIVEN** 使用者有未讀訊息
- **WHEN** 桌面載入
- **THEN** Header Bar 訊息圖示顯示未讀數量徽章

#### Scenario: 即時更新未讀數量
- **GIVEN** Header Bar 已顯示未讀數量
- **WHEN** 收到新訊息或標記已讀
- **THEN** 徽章數字即時更新

#### Scenario: 清除徽章
- **GIVEN** 使用者已讀取所有訊息
- **WHEN** 未讀數量變為 0
- **THEN** 隱藏未讀數量徽章
