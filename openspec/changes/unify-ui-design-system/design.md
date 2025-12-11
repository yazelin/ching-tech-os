# Design: 統一 UI 設計系統

## Context

ChingTech OS 是一個 Web-based 桌面作業系統，需要一致的視覺風格。目前系統有 15 個 CSS 檔案，其中多處使用硬編碼顏色值，無法透過 CSS 變數統一管理。

### 現況分析

經過全面掃描，發現以下硬編碼顏色問題：

#### CSS 硬編碼顏色（非 main.css :root 定義處）

| 類型 | 數量 | 主要檔案 |
|------|------|----------|
| HEX 顏色 | 50+ | project-management, knowledge-base, message-center |
| rgba() 顏色 | 80+ | 分散於所有檔案 |

#### 問題分類

1. **狀態標籤顏色不一致**
   - `project-management.css`: `#28a745`, `#007bff`, `#ffc107`, `#6c757d`
   - `knowledge-base.css`: `#818cf8`, `#34d399`, `#fbbf24`, `#f472b6`
   - `message-center.css`: `#3b82f6`, `#f59e0b`, `#ef4444`

2. **模態框背景色不一致**
   - `#1e1e2e`（project-management, knowledge-base）
   - `#1e1e1e`（code-editor）
   - `#1a1a1a`（terminal）

3. **按鈕 hover 顏色硬編碼**
   - `#2560c2`（btn-primary:hover）
   - `#4fe0ff`（btn-accent:hover）

## Goals / Non-Goals

### Goals
- 所有 UI 顏色透過 CSS 變數定義
- 支援未來亮色/暗色主題切換
- 保持現有視覺外觀不變
- 建立語義化顏色命名規範

### Non-Goals
- 本次不實作亮色主題（僅確保架構支援）
- 不重新設計 UI 視覺風格
- 不修改 JavaScript 業務邏輯

## Decisions

### 1. CSS 變數命名規範

```css
/* 基礎顏色 - 保持現有 */
--color-primary
--color-background
--color-accent

/* 狀態顏色 - 保持現有 */
--color-success
--color-warning
--color-error

/* 新增：語義化標籤顏色 */
--tag-color-purple: #818cf8;     /* 用於：分類標籤 */
--tag-color-green: #34d399;      /* 用於：成功狀態 */
--tag-color-yellow: #fbbf24;     /* 用於：警告狀態 */
--tag-color-pink: #f472b6;       /* 用於：特殊標記 */
--tag-color-blue: #3b82f6;       /* 用於：資訊提示 */
--tag-color-gray: #6c757d;       /* 用於：已取消/待處理 */

/* 新增：模態框變數 */
--modal-bg: #1e1e2e;
--modal-border: var(--border-light);

/* 新增：終端機變數 */
--terminal-bg: #1a1a1a;
--terminal-fg: #e0e0e0;

/* 新增：按鈕 hover 變數 */
--color-primary-hover: #2560c2;
--color-accent-hover: #4fe0ff;

/* 新增：RGB 變數支援 rgba() 運算 */
--accent-rgb: 33, 212, 253;
```

### 2. rgba() 顏色處理策略

對於 `rgba(r, g, b, alpha)` 形式的顏色：
- 若 alpha < 0.5：使用現有 `--bg-surface*` 系列變數
- 若為品牌色的透明版本：使用 `--*-bg-subtle` 系列
- 若為狀態色的透明版本：新增 `--tag-bg-*` 變數

### 3. 終端機主題處理

由於 xterm.js 需要在 JavaScript 中設定主題色，採用以下方案：

```javascript
// 從 CSS 變數讀取顏色
const getColor = (varName) =>
  getComputedStyle(document.documentElement).getPropertyValue(varName).trim();

const theme = {
  background: getColor('--terminal-bg'),
  foreground: getColor('--terminal-fg'),
  // ...
};
```

## Risks / Trade-offs

| 風險 | 影響 | 緩解策略 |
|------|------|----------|
| 視覺回歸 | 修改後外觀改變 | 逐檔案修改並視覺確認 |
| CSS 變數過多 | 維護複雜度增加 | 使用語義化命名並分組註解 |
| 瀏覽器相容性 | IE 不支援 CSS 變數 | 已明確不支援 IE |

## Migration Plan

1. **Phase 1**: 擴充 `main.css` CSS 變數定義
2. **Phase 2**: 逐檔案修正硬編碼顏色
3. **Phase 3**: 修正 JavaScript 硬編碼
4. **Phase 4**: 視覺驗證

每個 Phase 完成後進行視覺檢查，確保無回歸。

## Open Questions

1. 是否需要為所有 xterm ANSI 顏色（16 色）都建立 CSS 變數？
   - 建議：是，以支援未來主題切換

2. `rgba()` 中使用的透明度值是否需要也變數化？
   - 建議：否，保持 inline 以減少複雜度
