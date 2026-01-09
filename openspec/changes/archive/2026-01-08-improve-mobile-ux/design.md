# Design: 手機版 UI/UX 改進

## Context

系統原本設計為桌機優先的類 OS 介面。目前手機使用有以下問題：
- 雙擊開啟圖示在手機上體驗差
- Dock 列佔用空間且功能與桌面圖示重複
- 應用程式視窗未針對手機優化

### 限制條件
- 不使用前端框架，純 HTML/CSS/JavaScript
- 維持程式碼共用性

## Goals / Non-Goals

### Goals
- 手機用戶能流暢操作
- 簡化介面，減少不必要的元素
- 統一桌機與手機的操作邏輯

### Non-Goals
- 不開發獨立手機 App
- 不細分平板（平板視為桌機）

## Decisions

### Decision 1: 移除 Dock 列

**選擇**：完全移除 Dock 列（桌機與手機皆移除）

**原因**：
- Dock 列功能與桌面圖示重複
- 應用程式無狀態保存需求
- 減少程式碼維護複雜度
- 增加可用畫面空間

**移除範圍**：
- `frontend/js/taskbar.js` - 移除整個檔案
- `frontend/css/taskbar.css` - 移除整個檔案
- `frontend/index.html` - 移除 `.taskbar` 元素

### Decision 2: 響應式設計斷點

只分兩種，不細分平板：

```css
/* 手機：≤768px */
@media (max-width: 768px) { ... }

/* 桌機（含平板）：>768px */
@media (min-width: 769px) { ... }
```

### Decision 3: 桌面圖示互動

**選擇**：統一使用單擊開啟（移除雙擊、移除選取狀態）

**原因**：
- 手機無法有效雙擊
- 選取狀態無實際用途
- 簡化互動邏輯

### Decision 4: 手機版視窗行為

- 視窗開啟時自動全螢幕（填滿 desktop-area）
- 隱藏拖曳、縮放、最大化、最小化功能
- 保留關閉按鈕

### Decision 5: 返回桌面方式

**選擇**：點擊 Header Bar logo + 支援瀏覽器返回

**實作**：
1. Header Bar 的 logo 可點擊，關閉當前視窗返回桌面
2. 使用 `history.pushState` 管理狀態
3. 監聽 `popstate` 事件處理瀏覽器返回

**不做**：
- 不在 Header Bar 顯示「運行中的應用程式」
- 不需要最小化功能（沒有 Dock 也不需要）

### Decision 6: 桌機視窗簡化

移除 Dock 後，桌機視窗也可以簡化：
- 移除最小化按鈕（無處可收）
- 保留最大化、關閉按鈕
- 保留拖曳、縮放功能

## Risks / Trade-offs

| 風險 | 緩解措施 |
|------|----------|
| 無法快速切換應用 | 關閉當前應用再開新的，符合手機習慣 |
| 用戶習慣改變 | Dock 使用率低，影響有限 |

## Open Questions

無（已確認方向）
