# 設計系統（Design System）

## 概覽

ChingTech OS 使用 CSS Custom Properties（CSS 變數）建立一致的設計系統，支援亮色/暗色主題切換。

所有 CSS 變數定義於 `frontend/css/main.css`。

## 主題切換

系統透過 `data-theme` 屬性在 `:root` 元素上切換主題：

```css
:root { /* 暗色主題（預設） */ }
:root[data-theme="light"] { /* 亮色主題 */ }
```

```javascript
// 切換主題
document.documentElement.setAttribute('data-theme', 'light');
```

---

## 顏色系統

### 主色

| CSS 變數 | 暗色主題 | 亮色主題 | 用途 |
|----------|----------|----------|------|
| `--color-primary` | #0891b2 | #0891b2 | 主要按鈕、品牌色 |
| `--color-background` | #1a1a1a | #f5f5f5 | 頁面背景 |
| `--color-accent` | #ea580c | #ea580c | 強調元素 |

### 狀態色

| CSS 變數 | 色碼 | 用途 |
|----------|------|------|
| `--color-success` | #16a34a | 成功狀態 |
| `--color-warning` | #d97706 | 警告狀態 |
| `--color-error` | #dc2626 | 錯誤狀態 |

### 中性色

| CSS 變數 | 暗色主題 | 亮色主題 |
|----------|----------|----------|
| `--color-gray-light` | #f0f0f0 | #1a1a1a |
| `--color-gray-mid` | #909090 | #707070 |
| `--color-gray-dark` | #404040 | #d0d0d0 |

### 文字顏色

| CSS 變數 | 暗色主題 | 亮色主題 | 用途 |
|----------|----------|----------|------|
| `--color-text-primary` | #f0f0f0 | #1a1a1a | 主要文字 |
| `--color-text-secondary` | #a0a0a0 | #505050 | 次要文字 |
| `--color-text-muted` | #606060 | #a0a0a0 | 靜音文字 |

### 按鈕文字顏色

| CSS 變數 | 值 | 用途 |
|----------|---|------|
| `--btn-text-on-primary` | #ffffff | 主要按鈕文字 |
| `--btn-text-on-accent` | #ffffff | 強調按鈕文字 |
| `--btn-text-on-ghost` | var(--color-text-primary) | Ghost 按鈕文字 |

### Hover 顏色

| CSS 變數 | 暗色主題 | 亮色主題 |
|----------|----------|----------|
| `--color-primary-hover` | #0ea5c9 | #0e7490 |
| `--color-accent-hover` | #f97316 | #c2410c |

---

## 表面與邊框

### 表面背景

| CSS 變數 | 暗色主題 | 亮色主題 | 用途 |
|----------|----------|----------|------|
| `--bg-surface` | `rgba(0,0,0,0.1)` | `rgba(0,0,0,0.03)` | 基礎表面 |
| `--bg-surface-dark` | `rgba(0,0,0,0.2)` | `rgba(0,0,0,0.05)` | 較深表面 |
| `--bg-surface-darker` | `rgba(0,0,0,0.3)` | `rgba(0,0,0,0.08)` | 最深表面 |
| `--bg-overlay` | `rgba(0,0,0,0.6)` | `rgba(0,0,0,0.4)` | 疊層背景 |
| `--bg-overlay-dark` | `rgba(0,0,0,0.8)` | `rgba(0,0,0,0.6)` | 深色疊層（模態框遮罩） |

### 玻璃效果

| CSS 變數 | 暗色主題 | 亮色主題 | 用途 |
|----------|----------|----------|------|
| `--bg-glass` | `rgba(26,26,26,0.95)` | `rgba(255,255,255,0.95)` | Header、Taskbar |
| `--bg-glass-light` | `rgba(26,26,26,0.85)` | `rgba(255,255,255,0.88)` | 淺玻璃效果 |
| `--bg-glass-heavy` | `rgba(26,26,26,0.98)` | `rgba(255,255,255,0.98)` | 重玻璃效果 |

### 視窗背景

| CSS 變數 | 暗色主題 | 亮色主題 | 用途 |
|----------|----------|----------|------|
| `--window-bg` | #252525 | #ffffff | 視窗內容背景 |
| `--window-titlebar-bg` | #1e1e1e | #f0f0f0 | 視窗標題列 |

### 邊框

| CSS 變數 | 暗色主題 | 亮色主題 | 用途 |
|----------|----------|----------|------|
| `--border-subtle` | `rgba(255,255,255,0.05)` | `rgba(0,0,0,0.05)` | 極淡邊框 |
| `--border-light` | `rgba(255,255,255,0.1)` | `rgba(0,0,0,0.1)` | 淺色邊框 |
| `--border-medium` | `rgba(255,255,255,0.15)` | `rgba(0,0,0,0.15)` | 中等邊框 |
| `--border-strong` | `rgba(255,255,255,0.2)` | `rgba(0,0,0,0.2)` | 明顯邊框 |

---

## 強調色變體

| CSS 變數 | 用途 |
|----------|------|
| `--accent-bg-subtle` | 淡強調色背景（選中項目） |
| `--accent-bg-light` | 淺強調色背景 |
| `--accent-bg-medium` | 中等強調色背景 |
| `--accent-border` | 強調色邊框 |

---

## 互動效果

| CSS 變數 | 暗色主題 | 亮色主題 | 用途 |
|----------|----------|----------|------|
| `--hover-bg` | `rgba(255,255,255,0.1)` | `rgba(0,0,0,0.05)` | 一般 hover |
| `--interactive-hover` | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.05)` | 互動元素 hover |
| `--interactive-active` | `rgba(255,255,255,0.12)` | `rgba(0,0,0,0.08)` | 互動元素 active |
| `--interactive-border` | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.1)` | 互動元素邊框 |

---

## 標籤顏色

### 基礎標籤

| CSS 變數 | 色碼 | 用途 |
|----------|------|------|
| `--tag-color-purple` | #818cf8 | 分類/專案 |
| `--tag-color-green` | #34d399 | 類型/成功 |
| `--tag-color-yellow` | #fbbf24 | 警告/等級 |
| `--tag-color-pink` | #f472b6 | 角色/特殊 |
| `--tag-color-blue` | #3b82f6 | 資訊/進行中 |
| `--tag-color-gray` | #707070 | 已取消/待處理 |
| `--tag-color-red` | #ef4444 | 錯誤/緊急 |
| `--tag-color-orange` | #f59e0b | 高優先 |
| `--tag-color-cyan` | #22d3ee | 特殊標記 |

### 標籤背景

每個標籤顏色都有對應的半透明背景：`--tag-bg-{color}`

### 狀態標籤

| CSS 變數 | 用途 |
|----------|------|
| `--status-completed-color/bg` | 已完成 |
| `--status-in-progress-color/bg` | 進行中 |
| `--status-pending-color/bg` | 待處理 |
| `--status-cancelled-color/bg` | 已取消 |

### 優先級標籤

| CSS 變數 | 用途 |
|----------|------|
| `--priority-critical-color/bg` | 最高優先級 |
| `--priority-urgent-color/bg` | 緊急 |
| `--priority-high-color/bg` | 高優先級 |
| `--priority-normal-color/bg` | 一般 |
| `--priority-low-color/bg` | 低優先級 |

---

## 模態框

| CSS 變數 | 暗色主題 | 亮色主題 | 用途 |
|----------|----------|----------|------|
| `--modal-bg` | #1e1e1e | #ffffff | 模態框背景 |
| `--modal-bg-alt` | #1a1a1a | #fafafa | 替代背景 |
| `--modal-border` | `var(--border-light)` | `var(--border-light)` | 邊框 |

---

## 終端機主題

### 基礎

| CSS 變數 | 暗色主題 | 亮色主題 |
|----------|----------|----------|
| `--terminal-bg` | #1a1a1a | #f5f5f5 |
| `--terminal-fg` | #e0e0e0 | #1e1e1e |
| `--terminal-cursor` | #ffffff | #1e1e1e |
| `--terminal-selection` | `rgba(255,255,255,0.3)` | `rgba(0,0,0,0.15)` |

### ANSI 16 色

系統定義完整的 ANSI 16 色（8 基本色 + 8 亮色）：
- `--terminal-black`, `--terminal-red`, `--terminal-green`, `--terminal-yellow`
- `--terminal-blue`, `--terminal-magenta`, `--terminal-cyan`, `--terminal-white`
- `--terminal-bright-*` 對應的亮色版本

---

## 字體

| CSS 變數 | 值 | 用途 |
|----------|---|------|
| `--font-primary` | 系統字型堆疊 | 一般 UI |
| `--font-technical` | 系統字型堆疊 | 技術內容 |
| `--font-mono` | `'Ubuntu Mono', 'Consolas', monospace` | 程式碼 |

### 字體大小

| CSS 變數 | 值 |
|----------|---|
| `--font-size-xs` | 0.75rem (12px) |
| `--font-size-sm` | 0.875rem (14px) |
| `--font-size-md` | 0.9375rem (15px) |
| `--font-size-base` | 1rem (16px) |
| `--font-size-lg` | 1.125rem (18px) |
| `--font-size-xl` | 1.25rem (20px) |
| `--font-size-2xl` | 1.5rem (24px) |

---

## 佈局

| CSS 變數 | 值 | 說明 |
|----------|---|------|
| `--header-height` | 40px | Header Bar 高度 |
| `--taskbar-height` | 64px | Taskbar 高度 |
| `--taskbar-icon-size` | 48px | Taskbar 圖示 |
| `--desktop-icon-size` | 64px | 桌面圖示 |
| `--desktop-icon-gap` | 24px | 桌面圖示間距 |

---

## 間距

| CSS 變數 | 值 |
|----------|---|
| `--spacing-xs` | 4px |
| `--spacing-sm` | 8px |
| `--spacing-md` | 16px |
| `--spacing-lg` | 24px |
| `--spacing-xl` | 32px |

---

## 圓角

| CSS 變數 | 值 | 用途 |
|----------|---|------|
| `--radius-sm` | 4px | 小型元素 |
| `--radius-md` | 8px | 按鈕、輸入框 |
| `--radius-lg` | 12px | 卡片、面板 |
| `--radius-xl` | 16px | 大型容器 |

---

## 陰影

| CSS 變數 | 暗色主題 | 亮色主題 |
|----------|----------|----------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.3)` | `0 1px 2px rgba(0,0,0,0.08)` |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.3)` | `0 4px 6px rgba(0,0,0,0.1)` |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.4)` | `0 10px 15px rgba(0,0,0,0.12)` |

---

## 轉場動畫

| CSS 變數 | 值 | 用途 |
|----------|---|------|
| `--transition-fast` | 150ms ease | 快速互動 |
| `--transition-normal` | 250ms ease | 一般轉場 |
| `--transition-slow` | 350ms ease | 慢速轉場 |

---

## Markdown 樣式

通用 Markdown 渲染樣式，使用 `.markdown-rendered` 類別套用。

| CSS 變數 | 暗色主題 | 亮色主題 | 用途 |
|----------|----------|----------|------|
| `--md-heading-color` | #e2e8f0 | #1e293b | 標題顏色 |
| `--md-text-color` | #cbd5e1 | #334155 | 內文顏色 |
| `--md-link-color` | #60a5fa | #2563eb | 連結顏色 |
| `--md-code-bg` | rgba(139,92,246,0.15) | rgba(139,92,246,0.1) | 行內代碼背景 |
| `--md-code-color` | #c4b5fd | #7c3aed | 行內代碼顏色 |
| `--md-pre-bg` | #1e293b | #f1f5f9 | 代碼塊背景 |
| `--md-pre-border` | #334155 | #e2e8f0 | 代碼塊邊框 |
| `--md-blockquote-border` | #60a5fa | #2563eb | 引用區塊邊框 |
| `--md-blockquote-bg` | rgba(96,165,250,0.1) | rgba(37,99,235,0.05) | 引用區塊背景 |
| `--md-table-border` | #334155 | #e2e8f0 | 表格邊框 |
| `--md-table-header-bg` | #1e293b | #f8fafc | 表格標題背景 |
| `--md-hr-color` | #334155 | #e2e8f0 | 水平線顏色 |

---

## 格式化資料語法色彩

TextViewer 中 JSON/YAML/XML 格式化顯示的語法色彩，使用 `.formatted-data` 類別套用。

| CSS 變數 | 暗色主題 | 亮色主題 | 用途 |
|----------|----------|----------|------|
| `--fd-string-color` | #a5d6a7 | #2e7d32 | 字串 |
| `--fd-number-color` | #90caf9 | #1565c0 | 數字 |
| `--fd-boolean-color` | #ce93d8 | #7b1fa2 | 布林值 |
| `--fd-null-color` | #ef9a9a | #c62828 | null 值 |
| `--fd-key-color` | #81d4fa | #0277bd | 鍵名 |
| `--fd-punctuation-color` | #9e9e9e | #616161 | 標點符號 |
| `--fd-tag-color` | #ef5350 | #d32f2f | XML 標籤 |
| `--fd-attribute-color` | #ffb74d | #ef6c00 | XML 屬性 |
| `--fd-comment-color` | #757575 | #9e9e9e | 註解 |

CSS 類別對應：

| 類別 | 用途 |
|------|------|
| `.fd-string` | 字串值 |
| `.fd-number` | 數字值 |
| `.fd-boolean` | 布林值（true/false） |
| `.fd-null` | null 值 |
| `.fd-key` | JSON/YAML 鍵名 |
| `.fd-punctuation` | 標點符號 |
| `.fd-tag` | XML 標籤名 |
| `.fd-attribute` | XML 屬性名 |
| `.fd-comment` | 註解 |

---

## 使用範例

### 按鈕

```css
.my-button {
  background-color: var(--color-primary);
  color: white;
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  transition: background-color var(--transition-fast);
}

.my-button:hover {
  background-color: var(--color-primary-hover);
}
```

### 卡片

```css
.my-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-md);
}
```

### 模態框

```css
.my-modal-overlay {
  background-color: var(--bg-overlay-dark);
}

.my-modal {
  background-color: var(--modal-bg);
  border: 1px solid var(--modal-border);
  border-radius: var(--radius-lg);
}
```
