# Design: AI 助手應用程式 UI

## Context
ChingTech OS 需要一個類似 ChatGPT 的 AI 對話介面，作為桌面應用程式運行。此設計專注於純前端 UI 實作，後端整合將另案處理。

## Goals / Non-Goals

**Goals:**
- 提供直覺的聊天介面，參考 ChatGPT/LINE/Messenger 設計
- 支援多個對話 session（左側列表切換）
- 支援模型選擇 UI（為後續後端整合預留）
- 在 ChingTech OS 視窗系統內運行

**Non-Goals:**
- 實際的 AI API 整合
- 對話資料後端持久化
- 即時通訊功能

## Decisions

### 視窗系統架構
- **Decision**: 使用 DOM 元素模擬視窗，不使用 iframe
- **Rationale**: 簡化開發、共享 CSS 變數、更好的效能
- **Alternative**: iframe 隔離 - 過於複雜，暫不需要

### UI 佈局
- **Decision**: 採用 ChatGPT 風格的左右分欄式設計
- **Layout**:
  ```
  ┌──────────────────────────────────────────┐
  │ [≡] AI 助手          [模型: ▼] [+ 新對話] │  ← 視窗標題列
  ├──────────┬───────────────────────────────┤
  │ 對話列表  │  對話標題                      │
  │          │                               │
  │ • 對話 1  │  [User] 訊息內容...            │
  │ • 對話 2  │  [AI]   回應內容...            │
  │ • 對話 3  │                               │
  │          │                               │
  │          ├───────────────────────────────┤
  │          │  [輸入訊息...]        [送出]    │
  └──────────┴───────────────────────────────┘
  ```

### 資料結構
```javascript
// 對話 Session
{
  id: 'session-uuid',
  title: '對話標題',
  model: 'claude-3-opus',
  messages: [
    { role: 'user', content: '...', timestamp: 1234567890 },
    { role: 'assistant', content: '...', timestamp: 1234567891 }
  ],
  createdAt: 1234567890,
  updatedAt: 1234567891
}

// 可用模型列表（UI 顯示用）
const availableModels = [
  { id: 'claude-3-opus', name: 'Claude 3 Opus' },
  { id: 'claude-3-sonnet', name: 'Claude 3 Sonnet' },
  { id: 'claude-3-haiku', name: 'Claude 3 Haiku' }
];
```

### 模組化設計
```
WindowModule          - 視窗管理器（通用）
├── createWindow()    - 建立視窗
├── closeWindow()     - 關閉視窗
├── focusWindow()     - 聚焦視窗
└── minimizeWindow()  - 最小化視窗

AIAssistantApp        - AI 助手應用程式
├── open()            - 開啟應用程式
├── close()           - 關閉應用程式
├── newChat()         - 新增對話
├── switchChat()      - 切換對話
├── sendMessage()     - 送出訊息（模擬）
└── renderMessages()  - 渲染訊息列表
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| 視窗系統複雜度 | 第一版只實作基本功能，後續迭代 |
| 響應式設計挑戰 | 設定最小視窗尺寸，小螢幕自動收合邊欄 |
| 模擬資料管理 | 使用 localStorage 暫存，方便測試 |

## Open Questions
- 是否需要支援視窗最大化？（建議第一版暫不實作）
- 左側邊欄預設展開或收合？（建議預設展開）
