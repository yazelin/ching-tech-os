# 手機版 App 佈局 - 任務清單

## 前置準備

- [x] 在 `main.css` 新增共用手機版 CSS 類別
  - 底部 Tab Bar 元件
  - 堆疊式導航元件
  - 手機版返回按鈕
  - 通用顯示/隱藏工具類別

---

## Phase 1：簡單佈局（優先）

### 1.1 系統設定 ⭐

**檔案**：`frontend/css/settings.css`, `frontend/js/settings.js`

**目標**：側邊欄導航 → 底部 Tab Bar

- [x] CSS：隱藏 `.settings-sidebar`
- [x] CSS：新增 `.settings-mobile-tabs` 底部 Tab Bar
- [x] JS：動態生成手機版 Tab Bar HTML
- [x] JS：綁定 Tab 點擊切換 section
- [x] 測試：真機驗證通過

### 1.2 分享管理 ⭐

**檔案**：`frontend/css/share-manager.css`

**目標**：工具列優化 + 列表卡片

- [x] CSS：工具列精簡（隱藏文字、只顯示圖示）
- [x] CSS：統計資訊平均分配
- [x] CSS：卡片樣式適配（URL 換行、觸控區域）
- [x] 測試：真機驗證通過

---

## Phase 2：工具列 + 資料型

### 2.1 AI Log ⭐⭐

**檔案**：`frontend/css/ai-log.css`, `frontend/js/ai-log.js`

**目標**：篩選器收合 + 表格轉卡片

- [x] CSS：篩選器改為可展開面板
- [x] CSS：隱藏表格，新增卡片列表樣式
- [x] JS：手機版偵測 → 渲染卡片而非表格
- [x] CSS：詳情面板改為全螢幕 modal（含 Tab 分頁）
- [x] 測試

### 2.2 Line Bot ⭐⭐

**檔案**：`frontend/css/linebot.css`, `frontend/js/linebot.js`

**目標**：優化現有響應式

- [x] CSS：群組列表點擊後全螢幕詳情
- [x] CSS：Tab 過多時橫向滾動
- [x] JS：新增手機版返回按鈕邏輯
- [x] CSS：檔案卡片操作按鈕優化
- [x] CSS：綁定狀態框手機版優化
- [x] JS：過期檔案標示
- [x] 測試

---

## Phase 3：雙欄型

### 3.1 AI 助手 ⭐⭐⭐

**檔案**：`frontend/css/ai-assistant.css`, `frontend/js/ai-assistant.js`

**目標**：聊天列表收納

- [x] 評估方案：底部 Tab / Drawer / 浮動按鈕（選擇 Drawer）
- [x] CSS：側邊欄手機版處理（全螢幕 Drawer + 遮罩層）
- [x] JS：手機版聊天列表切換邏輯（toggleSidebar、closeMobileSidebar）
- [x] CSS：輸入區固定底部 + 工具列優化（Grid 兩行佈局）
- [x] 測試

### 3.2 知識庫 ⭐⭐⭐

**檔案**：`frontend/css/knowledge-base.css`, `frontend/js/knowledge-base.js`

**目標**：列表 ↔ 詳情堆疊導航

- [x] CSS：手機版列表全寬（`.kb-list-panel { width: 100% }`）
- [x] CSS：詳情頁堆疊動畫（`.showing-detail` + `transform`）
- [x] JS：返回按鈕邏輯（`hideMobileDetail()`）
- [x] CSS：Tab 橫向滾動（`.kb-tags-section { overflow-x: auto }`）
- [ ] 測試

### 3.3 專案管理 ⭐⭐⭐

**檔案**：`frontend/css/project-management.css`, `frontend/js/project-management.js`

**目標**：列表 ↔ 詳情堆疊導航

- [ ] CSS：手機版列表全寬
- [ ] CSS：詳情頁堆疊動畫
- [ ] JS：返回按鈕邏輯
- [ ] CSS：內部 Tab（概覽/成員/會議...）優化
- [ ] CSS：成員卡片、會議卡片適配
- [ ] 測試

### 3.4 檔案管理 ⭐⭐⭐

**檔案**：`frontend/css/file-manager.css`, `frontend/js/file-manager.js`

**目標**：檔案列表 ↔ 預覽堆疊

- [ ] CSS：預覽面板手機版處理
- [ ] CSS：工具列優化
- [ ] JS：預覽改為全螢幕 modal
- [ ] 測試

---

## Phase 4：編輯器型

### 4.1 Prompt 編輯器 ⭐⭐

**檔案**：`frontend/css/prompt-editor.css`, `frontend/js/prompt-editor.js`

**目標**：編輯/預覽 Tab 切換

- [ ] CSS：雙欄轉為單欄
- [ ] JS：新增編輯/預覽切換 Tab
- [ ] 測試

### 4.2 Agent 設定 ⭐⭐

**檔案**：`frontend/css/agent-settings.css`, `frontend/js/agent-settings.js`

**目標**：列表 ↔ 編輯堆疊

- [ ] CSS：列表全寬
- [ ] JS：編輯面板改為全螢幕
- [ ] 測試

---

## 驗證清單

每個 App 完成後需驗證：

- [ ] iPhone SE (375px) 正常顯示
- [ ] iPhone 14 (390px) 正常顯示
- [ ] iPad 直立 (768px) 切換正確
- [ ] 觸控區域 ≥ 44px
- [ ] 無非預期水平滾動
- [ ] 深色/淺色主題正常
