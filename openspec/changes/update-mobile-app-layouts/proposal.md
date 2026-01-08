# 手機版 App 內部佈局設計規範

## 摘要

建立統一的手機版 app 內部佈局設計規範，讓所有 app 在手機上有一致的操作體驗。目前各 app 皆以桌面版為主設計，在手機全螢幕模式下需要針對內部佈局進行優化。

## 現況分析

### 現有 App 佈局類型

經分析，現有 12 個 app 可歸類為以下佈局類型：

| 類型 | App | 桌面版結構 | 手機版問題 |
|------|-----|-----------|-----------|
| **A. 側邊欄 + 主內容** | 系統設定、AI 助手 | 固定寬度側邊欄（200-260px）+ 主內容 | 側邊欄佔用過多空間 |
| **B. 列表 + 詳情雙欄** | 專案管理、知識庫、檔案管理 | 列表面板（300-320px）+ 詳情面板 | 雙欄並排不適合小螢幕 |
| **C. Tab + 雙欄** | Line Bot | Tab 切換 + 分割佈局（300px 左欄） | 分割佈局需調整 |
| **D. 工具列 + 列表/表格** | AI Log、分享管理 | 頂部工具列 + 資料列表/表格 | 表格太寬、工具列擁擠 |
| **E. 全螢幕單一內容** | 終端機、程式編輯器 | 全螢幕單一內容區 | 無需調整（已適配） |
| **F. Prompt/Agent 編輯** | Prompt 編輯器、Agent 設定 | 編輯器 + 預覽區 | 雙欄需調整 |

### 共通問題

1. **側邊欄/列表面板**：固定寬度在手機上佔用過多空間
2. **雙欄佈局**：左右並排在 < 768px 螢幕無法正常顯示
3. **工具列**：多個按鈕/篩選器橫向排列會溢出
4. **表格**：水平滾動體驗差，資訊難以閱讀
5. **操作按鈕**：觸控區域過小（< 44px）

---

## 設計規範

### 一、通用原則

1. **斷點定義**：
   - 手機版：`max-width: 768px`（與現有 `window.css` 一致）

2. **觸控友善**：
   - 最小觸控區域：44px × 44px
   - 按鈕間距：至少 8px

3. **空間優化**：
   - 優先顯示核心內容
   - 次要功能收納至選單或底部

---

### 二、佈局類型 A：側邊欄導航型（系統設定、AI 助手）

**桌面版**：
```
┌─────────┬──────────────────────┐
│ 側邊欄  │      主內容區         │
│ (導航)  │                      │
│         │                      │
└─────────┴──────────────────────┘
```

**手機版策略**：將側邊欄轉為**底部 Tab Bar**

```
┌──────────────────────────────┐
│         主內容區              │
│                              │
│                              │
├──────────────────────────────┤
│ [Tab1] [Tab2] [Tab3] [Tab4]  │  ← 底部 Tab Bar (固定)
└──────────────────────────────┘
```

**實作重點**：
- 側邊欄 `display: none`
- 新增底部 Tab Bar（固定高度 56px）
- Tab 圖示 + 文字標籤
- 主內容區需留出底部空間 `padding-bottom: 56px`

**適用 App**：
- ✅ 系統設定（外觀、使用者管理 → 2 個 Tab）
- ✅ AI 助手（聊天列表收納為 drawer 或 Tab）

---

### 三、佈局類型 B：列表 + 詳情型（專案管理、知識庫）

**桌面版**：
```
┌─────────────┬──────────────────┐
│   列表面板   │     詳情面板      │
│  (300-320px)│                  │
│             │                  │
└─────────────┴──────────────────┘
```

**手機版策略**：**堆疊式導航**（Stack Navigation）

```
頁面 1：列表頁                   頁面 2：詳情頁
┌────────────────────┐          ┌────────────────────┐
│ [工具列/搜尋]      │          │ [← 返回] [標題]    │
├────────────────────┤          ├────────────────────┤
│ ┌────────────────┐ │  點擊→   │                    │
│ │ 項目 1         │ │ ──────→  │     詳情內容       │
│ └────────────────┘ │          │                    │
│ ┌────────────────┐ │          │                    │
│ │ 項目 2         │ │          │                    │
│ └────────────────┘ │          │                    │
└────────────────────┘          └────────────────────┘
```

**實作重點**：
- 手機版隱藏詳情面板，列表全寬顯示
- 點擊列表項目：
  - 滑入顯示詳情頁面（CSS `transform` 動畫）
  - 或切換 `.mobile-showing-detail` 狀態
- 詳情頁頂部加入「返回」按鈕
- 使用 CSS 類別控制：
  ```css
  .mobile-list-view .pm-content-panel { display: none; }
  .mobile-detail-view .pm-list-panel { display: none; }
  .mobile-detail-view .pm-content-panel { width: 100%; }
  ```

**適用 App**：
- ✅ 專案管理
- ✅ 知識庫
- ✅ 檔案管理（檔案列表 / 預覽）

---

### 四、佈局類型 C：Tab + 子內容（Line Bot）

**現況**：已有基本響應式（`.linebot-split-layout` 會轉直排），需優化細節

**手機版策略**：保持 Tab，內部分割轉為堆疊

```
┌──────────────────────────────┐
│ [群組] [訊息] [用戶] [檔案]  │  ← Tab Bar (橫向滾動)
├──────────────────────────────┤
│                              │
│        Tab 內容區             │
│   (分割佈局轉為堆疊式)        │
│                              │
└──────────────────────────────┘
```

**實作重點**：
- Tab 過多時允許橫向滾動
- 分割佈局內部採用類型 B 的堆疊式導航
- 群組列表 → 點擊進入詳情（全螢幕）

---

### 五、佈局類型 D：工具列 + 列表/表格（AI Log、分享管理）

**桌面版**：
```
┌──────────────────────────────┐
│ [篩選1] [篩選2] [搜尋] [重整]│  ← 工具列
├──────────────────────────────┤
│  表頭1  │ 表頭2 │ 表頭3 │... │
├─────────┼───────┼───────┼────┤
│  資料   │  資料  │  資料  │   │
└──────────────────────────────┘
```

**手機版策略**：

1. **工具列**：摺疊為篩選按鈕
```
┌──────────────────────────────┐
│ [≡ 篩選]           [🔄 重整] │
├──────────────────────────────┤
│  (篩選面板 - 可展開收合)      │
└──────────────────────────────┘
```

2. **表格**：轉為卡片列表
```
┌────────────────────────────┐
│ 狀態: ✓ 成功               │
│ 時間: 2025-01-08 14:30     │
│ Agent: general-assistant   │
│ Token: 1,234 / 5,678       │
└────────────────────────────┘
```

**實作重點**：
- 工具列使用 `flex-wrap: wrap` 或收合選單
- 表格隱藏，改為卡片式列表
- 卡片內以 key-value 形式呈現重要欄位
- 詳情面板改為點擊卡片展開或全螢幕顯示

**適用 App**：
- ✅ AI Log
- ✅ 分享管理

---

### 六、佈局類型 F：編輯器型（Prompt 編輯器、Agent 設定）

**手機版策略**：Tab 切換編輯/預覽

```
┌──────────────────────────────┐
│ [編輯] [預覽]                │  ← 切換 Tab
├──────────────────────────────┤
│                              │
│        編輯區 或 預覽區       │
│        (全寬單一顯示)         │
│                              │
└──────────────────────────────┘
```

---

## 共用 CSS 類別設計

建議在 `main.css` 新增手機版通用類別：

```css
/* ==========================================================================
   Mobile App Layout Utilities
   ========================================================================== */

/* 手機版底部 Tab Bar */
.mobile-tab-bar {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: var(--bg-surface-dark);
  border-top: 1px solid var(--border-subtle);
  z-index: 100;
}

@media (max-width: 768px) {
  .mobile-tab-bar {
    display: flex;
    justify-content: space-around;
    align-items: center;
  }
}

.mobile-tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 12px;
  color: var(--text-secondary);
  font-size: 10px;
  cursor: pointer;
}

.mobile-tab-item.active {
  color: var(--color-primary);
}

.mobile-tab-item .icon {
  font-size: 20px;
}

/* 堆疊式導航 */
.mobile-stack-nav {
  position: relative;
  height: 100%;
  overflow: hidden;
}

.mobile-stack-page {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--color-background);
  transition: transform 0.25s ease;
}

.mobile-stack-page.list-page {
  transform: translateX(0);
}

.mobile-stack-page.detail-page {
  transform: translateX(100%);
}

.mobile-stack-nav.showing-detail .list-page {
  transform: translateX(-30%);
}

.mobile-stack-nav.showing-detail .detail-page {
  transform: translateX(0);
}

/* 手機版返回按鈕 */
.mobile-back-btn {
  display: none;
}

@media (max-width: 768px) {
  .mobile-back-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 8px;
    background: transparent;
    border: none;
    color: var(--color-primary);
    cursor: pointer;
  }
}

/* 手機版隱藏/顯示 */
@media (max-width: 768px) {
  .hide-on-mobile { display: none !important; }
  .show-on-mobile { display: block !important; }
  .flex-on-mobile { display: flex !important; }
}
```

---

## 實施順序

建議按複雜度由低到高的順序實施：

| 優先順序 | App | 複雜度 | 說明 |
|---------|-----|-------|------|
| 1 | 系統設定 | ⭐ | 最簡單，只有 2 個導航項目，適合先驗證底部 Tab Bar 方案 |
| 2 | 分享管理 | ⭐ | 結構簡單，主要是工具列 + 列表 |
| 3 | AI Log | ⭐⭐ | 工具列 + 表格轉卡片 |
| 4 | Line Bot | ⭐⭐ | 已有基礎響應式，需優化細節 |
| 5 | AI 助手 | ⭐⭐⭐ | 側邊欄聊天列表 + 主對話區 |
| 6 | 知識庫 | ⭐⭐⭐ | 列表 + 詳情雙欄 |
| 7 | 專案管理 | ⭐⭐⭐ | 列表 + 詳情雙欄 + 多 Tab 內容 |
| 8 | 檔案管理 | ⭐⭐⭐ | 檔案列表 + 預覽面板 |
| 9 | Prompt 編輯器 | ⭐⭐ | 編輯器 + 預覽 |
| 10 | Agent 設定 | ⭐⭐ | 列表 + 編輯 |
| - | 終端機 | - | 已適配，無需調整 |
| - | 程式編輯器 | - | 外部 VSCode，無需調整 |

---

## 成功指標

1. 所有 app 在 375px 寬度（iPhone SE）下可正常操作
2. 觸控區域符合 44px 最小標準
3. 無水平滾動（除了特殊情況如表格）
4. 載入效能不受影響（CSS-only 解決方案優先）

---

## 相關檔案

- `frontend/css/main.css` - 新增共用手機版類別
- `frontend/css/window.css` - 現有手機版視窗樣式
- 各 app 的 CSS 檔案 - 新增 `@media (max-width: 768px)` 區塊
