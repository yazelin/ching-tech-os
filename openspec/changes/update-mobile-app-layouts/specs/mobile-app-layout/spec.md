# 手機版 App 內部佈局規範

## 概述

定義 ChingTech OS 所有 app 在手機版（≤768px）的內部佈局規範，確保一致的使用者體驗。

---

## 1. 佈局模式

### 1.1 底部 Tab Bar 導航

**適用場景**：app 有 2-5 個主要功能區塊需要快速切換

```
┌─────────────────────────────────┐
│                                 │
│          主內容區                │
│     padding-bottom: 56px        │
│                                 │
├─────────────────────────────────┤
│  [🏠]    [⚙️]    [👤]    [📊]   │  ← 固定底部 56px
└─────────────────────────────────┘
```

**CSS 結構**：
```css
.mobile-tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: var(--bg-surface-dark);
  border-top: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-around;
  align-items: center;
  z-index: 100;
}

.mobile-tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 12px;
  min-width: 64px;
  color: var(--text-secondary);
  font-size: 10px;
}

.mobile-tab-item.active {
  color: var(--color-primary);
}

.mobile-tab-item .icon {
  font-size: 20px;
}
```

---

### 1.2 堆疊式導航（Stack Navigation）

**適用場景**：列表 → 詳情 的階層式瀏覽

```
列表頁面                          詳情頁面
┌─────────────────┐              ┌─────────────────┐
│ [工具列]        │   點擊→      │ [← 返回] 標題   │
├─────────────────┤  ────────→   ├─────────────────┤
│ ┌─────────────┐ │              │                 │
│ │ 項目 1      │ │              │   詳情內容      │
│ └─────────────┘ │              │                 │
│ ┌─────────────┐ │              │                 │
│ │ 項目 2      │ │              │                 │
│ └─────────────┘ │              │                 │
└─────────────────┘              └─────────────────┘
```

**CSS 結構**：
```css
.mobile-stack-container {
  position: relative;
  height: 100%;
  overflow: hidden;
}

.mobile-stack-page {
  position: absolute;
  inset: 0;
  background: var(--color-background);
  overflow-y: auto;
  transition: transform 0.25s ease-out;
}

/* 列表頁 */
.mobile-stack-page.list-page {
  transform: translateX(0);
}

/* 詳情頁（初始在右側外） */
.mobile-stack-page.detail-page {
  transform: translateX(100%);
}

/* 顯示詳情時 */
.mobile-stack-container.showing-detail .list-page {
  transform: translateX(-30%);
  pointer-events: none;
}

.mobile-stack-container.showing-detail .detail-page {
  transform: translateX(0);
}
```

**返回按鈕**：
```css
.mobile-back-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-subtle);
}

.mobile-back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px;
  background: transparent;
  border: none;
  color: var(--color-primary);
  font-size: 14px;
  cursor: pointer;
}

.mobile-back-btn .icon {
  font-size: 18px;
}
```

---

### 1.3 可收合工具列

**適用場景**：多個篩選器/操作按鈕

```
收合狀態                         展開狀態
┌───────────────────────┐       ┌───────────────────────┐
│ [≡ 篩選]     [🔄 重整]│       │ [≡ 篩選]     [🔄 重整]│
└───────────────────────┘       ├───────────────────────┤
                                │ 狀態: [全部 ▼]        │
                                │ 日期: [____] ~ [____] │
                                │ 關鍵字: [__________]  │
                                │         [套用] [清除] │
                                └───────────────────────┘
```

**CSS 結構**：
```css
.mobile-filter-toggle {
  display: flex;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-surface-dark);
  border-bottom: 1px solid var(--border-subtle);
}

.mobile-filter-panel {
  display: none;
  padding: 16px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
}

.mobile-filter-panel.expanded {
  display: block;
}

.mobile-filter-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.mobile-filter-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
```

---

### 1.4 卡片式列表（取代表格）

**適用場景**：資料表格在手機上顯示

```
桌面版表格                       手機版卡片
┌────┬────────┬──────┬────┐     ┌──────────────────────┐
│狀態│時間    │Agent │Token│     │ ✓ 成功              │
├────┼────────┼──────┼────┤     │ 2025-01-08 14:30    │
│ ✓  │14:30   │assist│1.2K│     │ Agent: assistant    │
└────┴────────┴──────┴────┘     │ Token: 1,234        │
                                └──────────────────────┘
```

**CSS 結構**：
```css
.mobile-card-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
}

.mobile-card {
  padding: 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
}

.mobile-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.mobile-card-title {
  font-weight: 600;
  color: var(--text-primary);
}

.mobile-card-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.mobile-card-row {
  display: flex;
  justify-content: space-between;
}

.mobile-card-label {
  color: var(--text-secondary);
}

.mobile-card-value {
  color: var(--text-primary);
}
```

---

## 2. 通用規範

### 2.1 觸控區域

- 最小觸控目標：**44px × 44px**
- 按鈕間距：最小 **8px**
- 列表項目高度：最小 **48px**

### 2.2 間距

```css
/* 手機版間距調整 */
@media (max-width: 768px) {
  --spacing-page: 12px;      /* 頁面內邊距 */
  --spacing-card: 12px;      /* 卡片內邊距 */
  --spacing-section: 16px;   /* 區塊間距 */
}
```

### 2.3 字體大小

- 標題：16-18px
- 內文：14px
- 輔助文字：12px
- Tab 標籤：10-11px

### 2.4 工具類別

```css
@media (max-width: 768px) {
  .hide-on-mobile { display: none !important; }
  .show-on-mobile { display: block !important; }
  .flex-on-mobile { display: flex !important; }
}

@media (min-width: 769px) {
  .hide-on-desktop { display: none !important; }
  .show-on-desktop { display: block !important; }
}
```

---

## 3. 互動模式

### 3.1 下拉重整（Pull to Refresh）

預留擴展，目前不實作。

### 3.2 滑動操作（Swipe Actions）

預留擴展，目前不實作。

### 3.3 長按選單

預留擴展，目前不實作。

---

## 4. 實作注意事項

1. **效能優先**：盡量使用純 CSS 解決方案，減少 JS 運算
2. **漸進增強**：桌面版為基礎，手機版為增強
3. **狀態管理**：使用 CSS class 控制顯示狀態，避免直接操作 DOM style
4. **動畫**：使用 `transform` 和 `opacity`，避免觸發 layout
5. **測試**：優先在 375px（iPhone SE）寬度測試
