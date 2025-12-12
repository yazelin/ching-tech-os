# Change: 統一 Markdown 渲染與格式化顯示功能

## Why
各模組（AI 助手、專案管理、文字讀取器）的 Markdown 與結構化資料顯示效果不一致。知識庫已有良好的 Markdown 渲染，但其他模組缺乏相同的視覺體驗，且文字讀取器無法預覽 Markdown 或格式化顯示 JSON/YAML/XML。

## What Changes
- 建立通用 Markdown CSS 樣式類別，支援暗色/亮色主題
- AI 助手訊息新增 Markdown 渲染支援
- 專案管理會議內容新增完整 Markdown 樣式
- 文字讀取器新增顯示模式切換（原始/Markdown/JSON/YAML/XML）
- 新增結構化資料（JSON/YAML/XML）語法色彩樣式

## Impact
- Affected specs: ai-assistant-ui, project-management, text-viewer (新建)
- Affected code: `frontend/css/main.css`, `frontend/js/ai-assistant.js`, `frontend/js/text-viewer.js`, `frontend/css/viewer.css`, `frontend/css/project-management.css`

---

## Problem Statement

### 問題現況

1. **知識庫 Markdown 顯示良好**
   - 使用 `marked.js` 渲染 Markdown
   - 有完整的 `.kb-markdown` CSS 樣式（標題、代碼塊、引用、表格等）
   - 視覺效果美觀

2. **AI 助手的訊息顯示簡陋**
   - 僅使用 `escapeHtml()` + `<br>` 轉換換行
   - 沒有使用 `marked.js` 渲染 Markdown
   - AI 回應中的程式碼、列表、標題等無法正確顯示

3. **專案管理的會議內容顯示不佳**
   - 雖然使用了 `marked.parse()`，但沒有專用的 Markdown CSS 樣式
   - 只有基本的 `.pm-meeting-content h1/h2/h3` 樣式
   - 缺少代碼塊、引用、表格等樣式

4. **文字讀取器 (TextViewer) 功能受限**
   - 僅以純文字 `<pre>` 方式顯示
   - 沒有 Markdown 預覽模式
   - 沒有 JSON/YAML/XML 格式化顯示功能

### 期望結果

- 所有模組的 Markdown 渲染效果一致且美觀
- TextViewer 支援切換顯示模式（原始文字 / Markdown 預覽 / JSON 格式化 / YAML 格式化 / XML 格式化）
- 統一的 Markdown CSS 樣式可被各模組共用
- 所有樣式同時支援暗色與亮色主題

## Proposed Solution

### 方案設計

1. **建立通用 Markdown CSS 類別**
   - 在 `main.css` 中新增 `.markdown-rendered` 通用類別
   - 整合知識庫現有的 `.kb-markdown` 樣式
   - 使用 CSS 變數支援暗色/亮色主題切換
   - 各模組只需套用此類別即可獲得一致的渲染效果

2. **AI 助手訊息支援 Markdown**
   - 修改 `ai-assistant.js` 中的 `renderMessages()` 函式
   - 對 AI 回應使用 `marked.parse()` 渲染
   - 套用 `.markdown-rendered` 類別
   - 確保主題切換時樣式正確更新

3. **專案管理會議內容樣式增強**
   - 為 `.pm-meeting-content` 新增完整的 Markdown 樣式
   - 或直接套用 `.markdown-rendered` 類別
   - 確保暗色/亮色主題相容

4. **TextViewer 新增顯示模式切換**
   - 新增工具列，包含顯示模式切換按鈕
   - 支援五種模式：
     - **原始文字**：純文字顯示（現有行為）
     - **Markdown 預覽**：渲染 Markdown 格式
     - **JSON 格式化**：解析並美化 JSON，支援縮排、語法色彩
     - **YAML 格式化**：解析並美化 YAML，支援縮排、語法色彩
     - **XML 格式化**：解析並美化 XML，支援縮排、語法色彩
   - 根據檔案副檔名自動判斷預設模式
   - 格式化顯示需支援暗色/亮色主題

5. **結構化資料格式化樣式**
   - 新增 JSON/YAML/XML 的語法色彩樣式
   - 使用 CSS 變數支援主題切換
   - 樣式元素：
     - 字串（string）
     - 數字（number）
     - 布林值（boolean）
     - null 值
     - 鍵名（key）
     - 標點符號
     - XML 標籤、屬性

## Scope

### In Scope
- AI 助手訊息的 Markdown 渲染
- 專案管理會議內容的 Markdown 樣式
- TextViewer 顯示模式切換功能
- 通用 Markdown CSS 樣式
- JSON/YAML/XML 格式化顯示及語法色彩
- 暗色與亮色主題支援

### Out of Scope
- 進階程式碼語法高亮（如使用 highlight.js）- 可作為後續改進
- Markdown 編輯預覽功能
- 新增外部函式庫（僅使用原生 JSON.parse 等）

## Affected Components

### 前端檔案
- `frontend/css/main.css` - 新增通用 Markdown 樣式、格式化資料樣式
- `frontend/js/ai-assistant.js` - 修改訊息渲染邏輯
- `frontend/css/ai-assistant.css` - 新增 AI 訊息 Markdown 樣式
- `frontend/js/text-viewer.js` - 新增顯示模式切換功能、格式化邏輯
- `frontend/css/viewer.css` - 新增 TextViewer 工具列樣式、格式化樣式
- `frontend/css/project-management.css` - 增強會議內容樣式
- `frontend/css/variables.css` 或 `theme.js` - 新增格式化相關的主題變數

### 相依性
- 現有的 `marked.js` 函式庫（已引入）
- 無需新增外部依賴

## Risks & Considerations

1. **渲染安全性**
   - AI 回應可能包含惡意 HTML
   - 需確保 `marked.js` 的 sanitize 設定正確
   - 考慮使用 DOMPurify 進行額外的 XSS 防護

2. **效能影響**
   - 長訊息的 Markdown 渲染可能影響效能
   - 大型 JSON/YAML/XML 檔案格式化可能較慢
   - 建議對超大檔案設定上限或分段處理

3. **向後相容**
   - 現有的知識庫樣式不應受影響
   - 需確保通用樣式不會覆蓋現有特定樣式

4. **主題相容**
   - 所有新增樣式必須使用 CSS 變數
   - 測試暗色/亮色主題切換時的視覺效果

5. **格式化解析錯誤處理**
   - 若 JSON/YAML/XML 格式不正確，需優雅降級顯示原始文字
   - 顯示錯誤提示讓使用者知道格式有問題

## Status
PROPOSED
