# Change: 新增主題設定功能

## Why
完成 CSS 變數統一後，系統已支援透過 CSS 變數切換主題。現在需要提供使用者一個設定介面，讓他們可以選擇亮色/暗色主題，並將偏好儲存在資料庫中，確保跨裝置與重新登入後仍保持一致的使用體驗。

## What Changes
- **資料庫**：擴充 `users` 資料表，新增 `preferences` JSONB 欄位儲存使用者偏好設定
- **後端 API**：新增取得/更新使用者偏好設定的 API 端點
- **前端 CSS**：定義亮色主題的 CSS 變數覆蓋
- **前端 UI**：新增「主題設定」分頁，包含：
  - 主題預覽卡片（暗色/亮色）
  - 即時切換預覽效果
  - 儲存偏好按鈕
- **登入流程**：登入成功後自動套用使用者的主題偏好

## Impact
- Affected specs: 新增 `user-settings` capability
- Affected code:
  - `backend/migrations/versions/007_add_user_preferences.py`（新增）
  - `backend/src/ching_tech_os/services/user.py`（修改）
  - `backend/src/ching_tech_os/api/user.py`（新增）
  - `frontend/css/main.css`（修改 - 新增亮色主題變數）
  - `frontend/css/settings.css`（新增）
  - `frontend/js/settings.js`（新增）
  - `frontend/js/theme.js`（新增）
  - `frontend/js/login.js`（修改）
  - `frontend/js/desktop.js`（修改）
  - `frontend/index.html`（修改）
