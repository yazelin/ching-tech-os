# 擎添OS（ChingTech OS）品牌與設計指南

## 品牌定位

擎添OS（ChingTech OS）是擎添工業打造的次世代企業級「作業系統級工作平台」。
它不是單一工具，而是一套驅動全公司數位流程、知識、工程與 AI 的整合性生態系。

擎添OS 承擔企業中樞角色，協助連結人員、專案、設備、資料與 AI Agent，讓所有任務能以一致的工作體驗被創建、追蹤、執行與優化。

## 品牌主張

**「以智慧為底層，打造企業的第二作業系統。」**

ChingTech OS 讓資料會流動、流程會自動化、知識會累積、AI 會協助。

## 系統價值

### 1. 統一工作空間（Unified Workspace）
無論是業務、PM、工程師或管理職，都能在一個平台完成所有工作：
專案、排程、程式撰寫、版本控管、CI/CD、LINEBot 訊息、內部知識庫等。

### 2. AI 驅動（AI-Driven）
內建多代理（Multi-Agent）架構，能協助：
- 尋找資料、整理知識
- 撰寫 PLC / Python 程式
- 協助文件生成、流程建議
- 自動處理訊息與分類內容

### 3. 工程與自動化導向（Engineering-First）
支援 DevOps、工控、程式、流程自動化與企業級部署。

### 4. 可成長的內部大腦（Growing Enterprise Brain）
擎添OS 會學習企業的作業模式，使流程越來越高效。

## 標語（Slogan）

**英文**：Empowering Ching-Tech with an Intelligent Operating System.

**中文**：讓擎添，以智慧驅動。

---

## 品牌色票（Color Palette）

### 主色系（Primary Colors）

| 用途 | CSS 變數 | 色碼 | 說明 |
|------|----------|------|------|
| ChingTech Cyan | `--color-primary` | #0891b2 | 主要按鈕/品牌色，青色調 |
| Background | `--color-background` | #1a1a1a | 純黑灰背景（無彩度） |
| Accent Orange | `--color-accent` | #ea580c | 強調/特殊元素，橙色 |

### 中性色（Neutral Colors）

| 用途 | CSS 變數 | 色碼 |
|------|----------|------|
| Light Gray | `--color-gray-light` | #f0f0f0 |
| Mid Gray | `--color-gray-mid` | #909090 |
| Dark Gray | `--color-gray-dark` | #404040 |

### 狀態色（Status Colors）

| 用途 | CSS 變數 | 色碼 | 說明 |
|------|----------|------|------|
| Success | `--color-success` | #16a34a | 成功狀態 |
| Warning | `--color-warning` | #d97706 | 警告狀態 |
| Error | `--color-error` | #dc2626 | 錯誤狀態 |

### 文字顏色

| 用途 | CSS 變數 | 色碼 |
|------|----------|------|
| 主要文字 | `--color-text-primary` | #f0f0f0 |
| 次要文字 | `--color-text-secondary` | #a0a0a0 |
| 靜音文字 | `--color-text-muted` | #606060 |
| 主要按鈕文字 | `--btn-text-on-primary` | #ffffff |
| 強調按鈕文字 | `--btn-text-on-accent` | #ffffff |
| Ghost 按鈕文字 | `--btn-text-on-ghost` | var(--color-text-primary) |

---

## 字體（Typography）

### 系統字型堆疊

```css
--font-primary: -apple-system, BlinkMacSystemFont, 'Ubuntu', 'Segoe UI', 'Microsoft JhengHei', 'Noto Sans CJK TC', sans-serif;
--font-mono: 'Ubuntu Mono', 'Consolas', 'Monaco', monospace;
```

### 字體大小

| CSS 變數 | 尺寸 | 用途 |
|----------|------|------|
| `--font-size-xs` | 12px | 小型標籤、提示 |
| `--font-size-sm` | 14px | 次要文字、說明 |
| `--font-size-md` | 15px | 一般內容 |
| `--font-size-base` | 16px | 基準字體 |
| `--font-size-lg` | 18px | 標題 |
| `--font-size-xl` | 20px | 大標題 |
| `--font-size-2xl` | 24px | 特大標題 |

---

## UI 設計方向

### 設計風格
- **半扁平設計（Semi-flat）**
- 大量留白，深色主題為主（工程感與可長時間閱讀）
- 模組化卡片（Cards）呈現專案 / Agent / 模組
- 動畫節奏慢、科技感線條光芒效果適度使用

### 主題支援
- **暗色主題**（預設）：無彩度灰階背景
- **亮色主題**：白色背景，保持相同色彩語言

### 佈局變數

| CSS 變數 | 數值 | 說明 |
|----------|------|------|
| `--header-height` | 40px | Header Bar 高度 |
| `--taskbar-height` | 64px | Taskbar 高度 |
| `--taskbar-icon-size` | 48px | Taskbar 圖示大小 |
| `--desktop-icon-size` | 64px | 桌面圖示大小 |

### 圓角（Border Radius）

| CSS 變數 | 數值 | 用途 |
|----------|------|------|
| `--radius-sm` | 4px | 小型元素 |
| `--radius-md` | 8px | 按鈕、輸入框 |
| `--radius-lg` | 12px | 卡片、面板 |
| `--radius-xl` | 16px | 大型容器 |

### 間距（Spacing）

| CSS 變數 | 數值 |
|----------|------|
| `--spacing-xs` | 4px |
| `--spacing-sm` | 8px |
| `--spacing-md` | 16px |
| `--spacing-lg` | 24px |
| `--spacing-xl` | 32px |

---

## 詳細 CSS 變數

完整的 CSS 設計系統定義請參考：
- **設計系統文件**：`docs/design-system.md`
- **CSS 原始碼**：`frontend/css/main.css`
