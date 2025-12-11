# Design: 主題設定功能

## Context
系統已完成 CSS 變數統一工作（unify-ui-design-system），所有顏色都已使用 CSS 變數定義。現在需要建立使用者介面讓使用者可以切換主題，並將偏好持久化到資料庫。

### 現有架構
- **使用者資料表**：`users(id, username, display_name, created_at, last_login_at)`
- **CSS 變數**：定義於 `frontend/css/main.css` 的 `:root`
- **認證機制**：透過 NAS 認證，session 儲存於記憶體

## Goals / Non-Goals

### Goals
- 提供使用者友善的主題切換介面
- 即時預覽主題變更效果
- 持久化使用者偏好設定
- 跨裝置/重新登入後保持一致體驗

### Non-Goals
- 自訂顏色（僅提供預設的暗色/亮色主題）
- 匯出/匯入主題設定
- 系統跟隨作業系統主題（prefers-color-scheme）- 此為未來擴充

## Decisions

### 1. 資料庫結構

**決定**：使用 JSONB 欄位儲存使用者偏好，而非新增多個欄位。

**理由**：
- 彈性：未來可輕鬆新增其他偏好設定而不需 migration
- 簡潔：避免 users 表過度膨脹
- 效能：PostgreSQL JSONB 查詢效能良好

```sql
ALTER TABLE users ADD COLUMN preferences JSONB DEFAULT '{}';
```

**預設結構**：
```json
{
  "theme": "dark"  // "dark" | "light"
}
```

### 2. 主題切換機制

**決定**：透過 `document.documentElement.dataset.theme` 切換主題。

**理由**：
- 與現有 CSS 變數架構一致（已預留 `[data-theme="light"]`）
- 無需重新載入頁面
- 所有子元素自動繼承

```javascript
// 切換主題
document.documentElement.dataset.theme = 'light';

// CSS 變數自動套用
:root[data-theme="light"] {
  --color-background: #F5F7FA;
  // ...
}
```

### 3. 設定頁面設計

**決定**：設定頁面為獨立視窗應用程式，首個分頁為「外觀」。

**UI 結構**：
```
┌─────────────────────────────────────────────────────┐
│ 系統設定                                    [─][□][×]│
├────────────┬────────────────────────────────────────┤
│ 外觀       │ 主題設定                              │
│ (未來擴充) │                                        │
│            │ ┌──────────────┐  ┌──────────────┐   │
│            │ │   暗色主題   │  │   亮色主題   │   │
│            │ │  [預覽圖]    │  │  [預覽圖]    │   │
│            │ │   ● 已選取   │  │   ○ 選取     │   │
│            │ └──────────────┘  └──────────────┘   │
│            │                                        │
│            │ 預覽面板:                             │
│            │ ┌──────────────────────────────────┐ │
│            │ │ [按鈕] [標籤] [卡片] [輸入框]   │ │
│            │ └──────────────────────────────────┘ │
│            │                                        │
│            │               [儲存設定]               │
└────────────┴────────────────────────────────────────┘
```

### 4. API 設計

**決定**：RESTful API，使用 PATCH 語意更新部分偏好。

```
GET  /api/user/preferences
  Response: { "theme": "dark" }

PUT  /api/user/preferences
  Body: { "theme": "light" }
  Response: { "success": true, "preferences": { "theme": "light" } }
```

### 5. 主題載入時機

**決定**：
1. 登入成功後立即從 API 載入偏好
2. 頁面載入時先檢查 localStorage 快取，避免閃爍
3. API 回應後更新 localStorage 快取

**流程**：
```
[登入頁] → 認證成功 → 取得偏好 → 儲存 localStorage → 跳轉桌面
                                      ↓
[桌面頁] → 讀取 localStorage → 套用主題 → (背景)同步 API
```

## Risks / Trade-offs

| 風險 | 緩解措施 |
|------|----------|
| localStorage 與 DB 不同步 | 每次登入強制更新 localStorage |
| 主題切換時 xterm 不更新 | 終端機重新讀取 CSS 變數並呼叫 terminal.options.theme |
| 亮色主題可讀性不佳 | 仔細設計亮色主題對比度，符合 WCAG AA |

## Migration Plan

1. **資料庫**：新增欄位，預設值為空 `{}`，向後相容
2. **前端**：新增 theme.js，不影響現有功能
3. **CSS**：新增 `[data-theme="light"]` 規則，不影響現有暗色主題
4. **登入流程**：漸進式整合，API 失敗時 fallback 到預設暗色主題

## Open Questions

- Q: 是否需要支援 `prefers-color-scheme` 自動偵測？
  - A: 列為未來擴充功能，目前先提供手動選擇
