# Change: 統一 UI 設計系統與 CIS 品牌配色

## Why

目前系統中有大量硬編碼的顏色值散落在各個 CSS 檔案中，導致：
1. 無法透過單一修改點切換亮色/暗色主題
2. 品牌色彩不一致，部分元件使用非標準色彩
3. 維護困難，需要逐一檔案修改顏色

## What Changes

### 1. CSS 變數擴充
- 擴充 `main.css` 的 CSS 變數定義，涵蓋所有現有硬編碼顏色
- 新增語義化顏色變數（如 `--tag-color-*`、`--terminal-*` 等）
- 新增 `--accent-rgb` 變數支援 rgba() 透明度運算

### 2. 硬編碼顏色修正

以下檔案需要修正硬編碼顏色：

| 檔案 | 硬編碼數量 | 問題類型 |
|------|-----------|----------|
| `project-management.css` | 25+ | 狀態標籤顏色、模態框背景 |
| `knowledge-base.css` | 15+ | 分類標籤顏色、模態框背景 |
| `message-center.css` | 10+ | 優先級標籤顏色 |
| `terminal.css` | 5 | 終端機背景、狀態指示燈 |
| `file-manager.css` | 4 | 檔案類型圖示顏色 |
| `header.css` | 3 | 系統提示紅點、文字顏色 |
| `login.css` | 3 | 漸層背景、文字顏色 |
| `main.css` | 4 | 按鈕 hover 狀態 |
| `code-editor.css` | 1 | 背景色 |

### 3. JavaScript 硬編碼顏色修正

| 檔案 | 問題 |
|------|------|
| `terminal.js` | xterm.js 主題配色（17 個顏色）|
| `notification.js` | 動態樣式中有 fallback 值（已使用 CSS 變數，可接受）|
| `device-fingerprint.js` | Canvas 指紋用顏色（非 UI，可忽略）|

### 4. 品牌色票對齊

根據 `design/brand.md` 品牌規範，確保所有顏色符合：

**主色系（已定義於 main.css）：**
- ChingTech Blue: `#1C4FA8`
- Deep Industrial Navy: `#0F1C2E`
- AI Neon Cyan: `#21D4FD`

**狀態色（已定義於 main.css）：**
- Action Green: `#4CC577`
- Warning Amber: `#FFC557`
- Error Red: `#E65050`

**需要新增的語義化變數：**
- 標籤系統顏色（分類、狀態、優先級）
- 終端機主題顏色
- 模態框專用背景色

## Impact

- Affected specs: `web-desktop`（UI 設計系統為其子功能）
- Affected code:
  - `frontend/css/*.css`（15 個檔案）
  - `frontend/js/terminal.js`
  - `design/brand.md`（新增 CSS 變數對照表）

## 主題切換支援

修正後，系統將支援：
```css
/* 暗色主題（預設） */
:root {
  --color-background: #0F1C2E;
  /* ... */
}

/* 亮色主題（未來擴充） */
:root[data-theme="light"] {
  --color-background: #F5F7FA;
  /* ... */
}
```

## 非破壞性變更

此變更為純視覺重構，不影響任何功能邏輯。所有現有 UI 在修正後應維持相同外觀。
