# Design: Web 桌面作業系統介面

## Context
擎添OS (ChingTech OS) 是擎添工業的企業級作業系統級工作平台。UI 設計需反映品牌的科技感、專業工程氛圍，並支援長時間閱讀使用。

參考資料：`design/brand.md`、`design/ching-tech-os-logo-bg.png`、`design/ching-tech-os-text-reference.png`

## Goals / Non-Goals

### Goals
- 實作符合擎添OS品牌規範的視覺設計
- 建立可重用的 CSS Variables 設計系統
- 深色主題配色方案（唯一主題）
- 半扁平設計風格（Semi-flat）

### Non-Goals
- 淺色主題或主題切換功能
- 複雜動畫效果
- Taskbar 圖示放大動畫
- 響應式平板/手機版面（第一階段以桌面為主）

## Decisions

### 色票系統 (Color Palette)

根據 `design/brand.md` 定義的品牌色票：

```css
:root {
  /* Primary Colors */
  --color-primary: #1C4FA8;           /* ChingTech Blue - 主視覺基礎色 */
  --color-background: #0F1C2E;        /* Deep Industrial Navy - 深色背景 */
  --color-accent: #21D4FD;            /* AI Neon Cyan - AI/智能元素高亮 */

  /* Neutral Colors */
  --color-gray-light: #F5F7FA;
  --color-gray-mid: #A4ACB5;
  --color-gray-dark: #3A3F45;

  /* Status Colors */
  --color-success: #4CC577;           /* Action Green */
  --color-warning: #FFC557;           /* Warning Amber */
  --color-error: #E65050;             /* Error Red */

  /* Text Colors */
  --color-text-primary: #F5F7FA;
  --color-text-secondary: #A4ACB5;
  --color-text-muted: #3A3F45;
}
```

### 字體系統 (Typography)

```css
:root {
  /* Font Families */
  --font-primary: 'Inter', 'Noto Sans TC', sans-serif;
  --font-technical: 'IBM Plex Sans', 'Noto Sans TC', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* Font Sizes */
  --font-size-xs: 0.75rem;    /* 12px */
  --font-size-sm: 0.875rem;   /* 14px */
  --font-size-base: 1rem;     /* 16px */
  --font-size-lg: 1.125rem;   /* 18px */
  --font-size-xl: 1.25rem;    /* 20px */
  --font-size-2xl: 1.5rem;    /* 24px */
}
```

### 佈局尺寸

```css
:root {
  /* Layout */
  --header-height: 40px;
  --taskbar-height: 64px;
  --taskbar-icon-size: 48px;
  --desktop-icon-size: 64px;
  --desktop-icon-gap: 24px;

  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;

  /* Border Radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
}
```

### UI 元素設計方向

| 元素 | 設計方向 |
|------|----------|
| **Header Bar** | 深色背景 (`--color-background`)，高度 40px，右側系統圖示區 |
| **Desktop Area** | 深色背景，可設定桌布圖片，圖示網格排列 |
| **Taskbar/Dock** | 半透明深色背景，居中顯示，圓角容器，無動畫效果 |
| **App Icons** | 64x64px 圖示，下方白色文字標籤 |
| **Login Page** | 置中表單卡片，Logo 顯示，深色背景 |

### Logo 處理

| 用途 | 檔案 | 處理方式 |
|------|------|----------|
| **Favicon** | `ching-tech-os-logo-bg.png` | 六邊形圖示，裁切/縮放為正方形 |
| **登入頁 Logo** | 新建正方形 Logo | 從 `ching-tech-os-text-reference.png` 處理為 1:1 比例 |
| **Header 小圖示** | 新建正方形 Logo | 同上，縮小版本 |

**待處理任務**：將現有寬版 Logo 處理為正方形版本，供 Favicon 及介面使用。

### 圖示庫 (Icon Library)

使用 **Material Design Icons (MDI)** 作為系統圖示來源：

**CDN 引入方式：**

```html
<!-- Material Design Icons -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@mdi/font@7/css/materialdesignicons.min.css">
```

**系統圖示對照表：**

| 用途 | MDI 圖示 |
|------|----------|
| 使用者 | `mdi-account` |
| 登出 | `mdi-logout` |
| 時鐘 | `mdi-clock-outline` |
| 設定 | `mdi-cog` |

**應用程式圖示對照表（自行設計）：**

| 應用程式 | MDI 圖示 | 說明 |
|----------|----------|------|
| 檔案管理 | `mdi-folder` | 資料夾管理 |
| 終端機 | `mdi-console` | 命令列工具 |
| 程式編輯器 | `mdi-code-braces` | PLC/Python 開發 |
| 專案管理 | `mdi-clipboard-check-outline` | PM 專案追蹤 |
| AI 助手 | `mdi-robot` | AI Agent 介面 |
| 訊息中心 | `mdi-message-text` | LINEBot 訊息 |
| 知識庫 | `mdi-book-open-page-variant` | 資料搜尋與知識 |
| 系統設定 | `mdi-cog` | 系統配置 |

## Risks / Trade-offs

| 風險 | 緩解措施 |
|------|----------|
| 自訂字體載入時間 | 使用 `font-display: swap` 避免 FOIT |
| CDN 依賴 | 可選擇下載 MDI 字體到本地 |
| Logo 需額外處理 | 加入 tasks.md 處理正方形 Logo |
