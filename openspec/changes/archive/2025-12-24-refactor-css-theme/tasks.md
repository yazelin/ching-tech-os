## 1. CSS 變數重構

- [x] 1.1 更新 `main.css` 中的變數定義
  - 將 `--color-text-primary` 重新命名為 `--text-primary`
  - 將 `--color-text-secondary` 重新命名為 `--text-secondary`
  - 將 `--color-text-muted` 重新命名為 `--text-muted`
  - 同時更新暗色和亮色主題區塊

- [x] 1.2 批次更新所有 CSS 檔案中的變數引用
  - 替換所有 `var(--color-text-primary)` → `var(--text-primary)`
  - 替換所有 `var(--color-text-secondary)` → `var(--text-secondary)`
  - 替換所有 `var(--color-text-muted)` → `var(--text-muted)`

- [x] 1.3 更新 CLAUDE.md 中的 CSS 變數對照表

## 2. 主題系統簡化

- [x] 2.1 修改 `theme.js`
  - 移除 `loadUserPreference()` 函數
  - 移除 `saveUserPreference()` 函數
  - 移除 `initWithUserPreference()` 函數
  - 新增 `toggleTheme()` 函數
  - 更新公開 API

- [x] 2.2 修改 `settings.js`
  - 更新主題儲存邏輯，改為直接呼叫 `ThemeManager.setTheme()`
  - 移除對 `saveUserPreference()` 的呼叫

- [x] 2.3 檢查並清理後端程式碼（若需要）
  - 確認 `/user/preferences` 端點是否還有其他用途
  - 保留端點供未來其他偏好設定使用

## 3. 登入頁主題切換

- [x] 3.1 在 `login.html` 新增主題切換 UI
  - 在右上角新增 toggle 按鈕
  - 使用 sun/moon 圖示表示切換

- [x] 3.2 確保 `theme.js` 在登入頁正確載入並初始化
  - 驗證 localStorage 主題在未登入時也能正確套用

## 4. Bug 修復

- [x] 4.1 修復 Session 驗證問題
  - 發現前端只檢查 localStorage，不驗證後端 session
  - 新增 `validateSession()` 函數到 `LoginModule`
  - 更新 `index.html` 在載入時驗證 session
  - 移除已刪除的 `initWithUserPreference()` 呼叫

## 5. 測試驗證

- [x] 5.1 視覺測試
  - 確認暗色主題下所有頁面顯示正確
  - 確認亮色主題下所有頁面顯示正確
  - 確認登入頁主題切換功能正常

- [x] 5.2 功能測試
  - 確認主題切換後重新整理仍保持選擇
  - 確認登入後主題設定保留
  - 確認在不同瀏覽器分頁中主題一致
  - 確認後端重啟後前端會自動登出
