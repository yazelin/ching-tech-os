# Tasks: add-user-profile-window

## Section 1: 後端 API

- [ ] 1.1 建立 `backend/src/ching_tech_os/api/user.py` 使用者路由
- [ ] 1.2 實作 `GET /api/user/me` 取得目前使用者資訊
- [ ] 1.3 實作 `PATCH /api/user/me` 更新使用者資訊（display_name）
- [ ] 1.4 在 `main.py` 註冊 user router
- [ ] 1.5 測試 API

## Section 2: 前端視窗元件

- [ ] 2.1 建立 `frontend/css/user-profile.css` 樣式
- [ ] 2.2 建立 `frontend/js/user-profile.js` 使用者資訊視窗模組
- [ ] 2.3 實作視窗開啟/關閉邏輯
- [ ] 2.4 實作載入使用者資訊
- [ ] 2.5 實作編輯 display_name 功能
- [ ] 2.6 實作儲存功能

## Section 3: Header 整合

- [ ] 3.1 修改 `frontend/js/header.js` 加入點擊使用者名稱事件
- [ ] 3.2 在 `frontend/index.html` 引入新的 CSS 和 JS
- [ ] 3.3 端對端測試

---

## Verification Checklist
- [ ] 點擊右上角使用者名稱可開啟視窗
- [ ] 視窗顯示 username、display_name、created_at、last_login_at
- [ ] 可編輯 display_name 並儲存
- [ ] 儲存後資料庫已更新
- [ ] 重新開啟視窗可看到更新後的 display_name
