# Change: CSS 變數重構與主題系統優化

## Why
目前 CSS 變數命名（`--color-text-primary`、`--color-text-secondary`、`--color-text-muted`）與業界標準不一致。業界慣例是使用較簡潔的命名如 `--text-primary`，而非加上多餘的 `color-` 前綴。

此外，主題設定目前會同步到後端資料庫，但這增加了不必要的複雜度。主題偏好應該只存在客戶端 localStorage，讓用戶在登入前就能選擇偏好的配色。

## What Changes

### 1. CSS 變數命名重構
- `--color-text-primary` → `--text-primary`
- `--color-text-secondary` → `--text-secondary`
- `--color-text-muted` → `--text-muted`
- 影響約 362 處（20+ CSS 檔案）

### 2. 主題儲存改為僅 localStorage
- **移除** API 同步功能（`/user/preferences` 端點的主題部分）
- 主題設定完全由 `localStorage` 管理
- 刪除 `ThemeManager.loadUserPreference()` 和 `ThemeManager.saveUserPreference()`

### 3. 登入頁新增主題切換按鈕
- 在 `login.html` 新增主題切換 toggle
- 用戶可在登入前切換為偏好的配色

## Impact
- Affected specs: `design-system`, `user-settings`
- Affected code:
  - `frontend/css/main.css` - CSS 變數定義
  - `frontend/css/*.css` - 所有使用這些變數的檔案（約 20 個）
  - `frontend/js/theme.js` - 移除 API 同步
  - `frontend/js/settings.js` - 簡化儲存邏輯
  - `frontend/login.html` - 新增主題 toggle
  - `backend/api/user_router.py` - 可能需要移除主題相關 API（若只用於主題）

## Design Decisions

### CSS 變數命名策略
採用業界標準命名：
- **文字顏色**：`--text-*`（無 color 前綴）
- **背景顏色**：`--bg-*`（已符合標準）
- **品牌/狀態顏色**：`--color-*`（保留，因為這些是語義化顏色）

這樣的區分讓變數用途更明確：
- `--text-*` = 文字專用
- `--bg-*` = 背景專用
- `--color-*` = 通用顏色（可用於 border、icon 等）

### 為何移除 API 同步
1. 主題是視覺偏好，不需要跨裝置同步
2. 減少不必要的 API 請求
3. 讓未登入用戶也能使用偏好主題
4. 簡化程式碼架構

### 向後相容性
- CSS 變數重構是 **BREAKING** 變更
- 需要一次性更新所有 CSS 檔案
- 不提供舊變數別名（避免維護負擔）
