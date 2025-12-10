# Change: 新增使用者資訊視窗

## Why
目前登入後無法修改顯示名稱，使用者也無法查看自己的帳號資訊。需要提供一個視窗讓使用者檢視和編輯個人資料。

## What Changes
- 點擊右上角使用者名稱時開啟「使用者資訊」視窗
- 視窗顯示使用者資訊（username、display_name、created_at、last_login_at）
- 可編輯 display_name 並儲存
- 後端新增取得/更新使用者資訊的 API

## Impact
- Affected specs: backend-auth, web-desktop
- Affected code:
  - `backend/src/ching_tech_os/api/user.py` (新增)
  - `backend/src/ching_tech_os/services/user.py` (擴充)
  - `frontend/js/header.js` (點擊事件)
  - `frontend/js/user-profile.js` (新增)
  - `frontend/css/user-profile.css` (新增)
