# Tasks: 新增主題設定功能

## 1. 資料庫擴充
- [ ] 1.1 建立 migration `007_add_user_preferences.py`，為 `users` 表新增 `preferences` JSONB 欄位
- [ ] 1.2 執行 migration 確認資料庫結構正確

## 2. 後端 API 開發
- [ ] 2.1 在 `services/user.py` 新增 `get_user_preferences()` 函數
- [ ] 2.2 在 `services/user.py` 新增 `update_user_preferences()` 函數
- [ ] 2.3 建立 `api/user.py` 新增 API 端點：
  - `GET /api/user/preferences` - 取得使用者偏好
  - `PUT /api/user/preferences` - 更新使用者偏好
- [ ] 2.4 在 `main.py` 註冊新的 API 路由

## 3. 前端主題系統
- [ ] 3.1 建立 `js/theme.js` 主題管理模組：
  - `ThemeManager.init()` - 初始化主題系統
  - `ThemeManager.setTheme(theme)` - 設定主題（'dark' | 'light'）
  - `ThemeManager.getTheme()` - 取得目前主題
  - `ThemeManager.loadUserPreference()` - 從 API 載入偏好
  - `ThemeManager.saveUserPreference()` - 儲存偏好到 API
- [ ] 3.2 在 `main.css` 新增亮色主題 CSS 變數（`:root[data-theme="light"]`）

## 4. 設定頁面 UI
- [ ] 4.1 建立 `css/settings.css` 設定頁面樣式
- [ ] 4.2 建立 `js/settings.js` 設定頁面邏輯：
  - 主題預覽卡片元件
  - 預覽面板顯示各種 UI 元件
  - 儲存偏好功能
- [ ] 4.3 在 `desktop.js` 註冊「系統設定」應用程式
- [ ] 4.4 在 `index.html` 引入新的 CSS/JS 檔案

## 5. 整合登入流程
- [ ] 5.1 修改 `login.js` 登入成功後載入使用者主題偏好
- [ ] 5.2 修改 `desktop.js` 初始化時套用主題

## 6. 驗證
- [ ] 6.1 測試主題切換即時預覽
- [ ] 6.2 測試偏好儲存與載入
- [ ] 6.3 測試重新登入後主題是否正確套用
