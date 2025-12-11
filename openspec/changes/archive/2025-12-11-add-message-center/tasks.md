## 1. 資料庫設計

- [x] 1.1 建立訊息資料表 migration
  - messages 表（含分區）
  - 索引（created_at, severity, source, user_id, category）
- [x] 1.2 建立登入記錄資料表 migration
  - login_records 表（含分區）
  - 索引（created_at, user_id, ip_address, success）
- [x] 1.3 建立自動分區管理函式
  - 自動建立下個月分區（APScheduler 每月 25 日執行）
  - 刪除超過 1 年的分區（APScheduler 每日凌晨 3 點執行）

## 2. 後端 - Models

- [x] 2.1 建立 `backend/src/ching_tech_os/models/message.py`
  - Message（基礎模型）
  - MessageCreate、MessageResponse
  - MessageListResponse（含分頁）
  - MessageFilter（查詢條件）
- [x] 2.2 建立登入記錄模型
  - LoginRecord
  - LoginRecordResponse
  - LoginRecordFilter
  - DeviceInfo（裝置資訊）

## 3. 後端 - Services

- [x] 3.1 建立 `backend/src/ching_tech_os/services/message.py`
  - `log_message()` - 記錄訊息
  - `search_messages()` - 搜尋訊息（多條件）
  - `get_message()` - 取得單一訊息
  - `get_unread_count()` - 取得未讀數量
  - `mark_as_read()` - 標記已讀
- [x] 3.2 建立 `backend/src/ching_tech_os/services/login_record.py`
  - `record_login()` - 記錄登入
  - `get_login_records()` - 查詢登入記錄
  - `get_recent_logins()` - 最近登入
- [x] 3.3 整合 GeoIP 地理位置解析
  - 安裝 geoip2 套件
  - 下載 GeoLite2-City 資料庫
  - 實作 IP 解析函式
- [x] 3.4 實作訊息清理排程
  - 使用 APScheduler 每日執行
  - 刪除超過 1 年的分區

## 4. 後端 - API

- [x] 4.1 建立 `backend/src/ching_tech_os/api/messages.py`
  - `GET /api/messages` - 搜尋訊息
  - `GET /api/messages/{id}` - 取得單一訊息
  - `GET /api/messages/unread-count` - 未讀數量
  - `POST /api/messages/mark-read` - 標記已讀
- [x] 4.2 建立登入記錄 API
  - `GET /api/login-records` - 查詢登入記錄
  - `GET /api/login-records/recent` - 最近登入
- [x] 4.3 註冊 Router 到 main.py

## 5. 後端 - WebSocket 整合

- [x] 5.1 實作訊息即時推送
  - `message:new` 事件
  - `message:unread_count` 事件
- [x] 5.2 擴充 auth 事件推送
  - 登入成功/失敗時推送 security 訊息

## 6. 後端 - Auth 擴充

- [x] 6.1 擴充登入 API 接收裝置資訊
  - 新增 device_fingerprint、device_type、browser、os 參數
- [x] 6.2 修改登入流程呼叫 record_login
  - 成功/失敗都記錄
  - 解析 GeoIP
- [x] 6.3 產生 security 訊息
  - 登入成功/失敗產生對應訊息

## 7. 前端 - 裝置指紋

- [x] 7.1 建立 `frontend/js/device-fingerprint.js`
  - 產生裝置指紋（Canvas、WebGL、Screen 等）
  - 偵測裝置類型、瀏覽器、OS
- [x] 7.2 修改登入頁面發送裝置資訊
  - 登入時附帶指紋與裝置資訊

## 8. 前端 - 訊息中心視窗

- [x] 8.1 建立 `frontend/css/message-center.css`
  - 視窗佈局樣式
  - 過濾器樣式
  - 訊息列表樣式
  - 訊息詳情樣式
  - 分頁樣式
- [x] 8.2 建立 `frontend/js/message-center.js`
  - MessageCenterApp 類別
  - 訊息列表載入與渲染
  - 過濾與搜尋功能
  - 分頁功能
  - 訊息詳情展開
  - 標記已讀功能
- [x] 8.3 整合桌面系統
  - ~~加入 Taskbar 圖示~~ (不需要)
  - ~~加入 Desktop 圖示~~ (不需要)
  - 視窗註冊 → 改為只從 Header Bar 開啟

## 9. 前端 - WebSocket 整合

- [x] 9.1 訂閱訊息事件
  - 監聽 message:new
  - 監聯 message:unread_count
- [x] 9.2 新訊息自動更新
  - 訊息中心開啟時自動新增訊息
  - warning 以上顯示 Toast

## 10. 前端 - Header Bar 整合

- [x] 10.1 新增訊息圖示到 Header Bar
  - 顯示未讀數量徽章
- [x] 10.2 即時更新未讀數量
  - 監聽 WebSocket 更新
  - 點擊開啟訊息中心

## 11. 整合現有系統

- [x] 11.1 將 AI Assistant 通知整合到訊息中心
  - AI 回應產生 user/info 訊息
- [x] 11.2 將檔案管理器操作整合
  - 上傳/刪除檔案產生 app/info 訊息
- [x] 11.3 將知識庫操作整合
  - CRUD 操作產生 app/info 訊息

## 12. 測試

- [x] 12.1 後端 API 測試
  - 訊息 CRUD 測試
  - 登入記錄測試
  - GeoIP 解析測試
- [x] 12.2 WebSocket 測試
  - 即時推送測試
- [x] 12.3 前端手動測試
  - 訊息中心完整流程
  - Header Bar 徽章更新

## 依賴關係

```
1.x → 2.x → 3.x → 4.x → 5.x
                    ↓
6.x → 7.x         12.1
  ↓
8.x → 9.x → 10.x → 11.x → 12.2-12.3
```

可平行進行：
- 後端 (2.x-6.x) 與 前端裝置指紋 (7.x) 可平行
- 前端視窗 (8.x) 需要等 API 完成
- 測試 (12.x) 在對應功能完成後進行
