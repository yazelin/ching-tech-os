# Tasks: add-markdown-rendering-unified

## 任務列表

### Phase 1: 通用樣式建立

- [x] **T1.1** 在 `main.css` 中建立 `.markdown-rendered` 通用類別
  - 整合知識庫 `.kb-markdown` 的樣式
  - 使用 CSS 變數確保暗色/亮色主題相容
  - 驗證：在測試頁面中使用此類別渲染範例 Markdown

- [x] **T1.2** 新增結構化資料格式化的 CSS 變數
  - 在 `main.css` 或 CSS 變數檔案中定義
  - 變數包含：字串色、數字色、布林色、null色、鍵名色、標點色
  - 暗色/亮色主題各一組
  - 驗證：主題切換時變數正確套用

- [x] **T1.3** 建立結構化資料格式化樣式
  - `.formatted-data` 容器類別
  - `.fd-string`, `.fd-number`, `.fd-boolean`, `.fd-null`, `.fd-key` 等子類別
  - 驗證：在測試頁面中顯示格式化 JSON 並確認色彩

### Phase 2: AI 助手 Markdown 支援

- [x] **T2.1** 修改 `ai-assistant.js` 中的 `renderMessages()` 函式
  - AI 回應訊息使用 `marked.parse()` 渲染
  - 使用者訊息保持純文字顯示
  - 驗證：AI 回應中的 Markdown 格式正確渲染

- [x] **T2.2** 為 AI 訊息套用 Markdown 樣式
  - 在 `.ai-message-text` 中套用 `.markdown-rendered` 樣式
  - 或在 `ai-assistant.css` 中複製相關樣式
  - 驗證：標題、列表、代碼塊、引用等樣式正確

- [x] **T2.3** 測試 AI 助手主題切換
  - 切換暗色/亮色主題
  - 驗證 Markdown 元素的色彩正確更新

### Phase 3: 專案管理會議內容樣式增強

- [x] **T3.1** 為 `.pm-meeting-content` 增加完整 Markdown 樣式
  - 代碼塊樣式 (`pre`, `code`)
  - 引用樣式 (`blockquote`)
  - 表格樣式 (`table`, `th`, `td`)
  - 列表樣式 (`ul`, `ol`, `li`)
  - 水平線樣式 (`hr`)
  - 驗證：會議內容中的各種 Markdown 元素正確顯示

- [x] **T3.2** 測試專案管理主題切換
  - 切換暗色/亮色主題
  - 驗證會議內容 Markdown 的色彩正確

### Phase 4: TextViewer 顯示模式切換

- [x] **T4.1** 修改 `text-viewer.js` 新增狀態管理
  - 新增 `displayMode` 狀態變數
  - 支援模式：`raw`, `markdown`, `json`, `yaml`, `xml`
  - 驗證：狀態變數正確切換

- [x] **T4.2** 新增 TextViewer 工具列 UI
  - 顯示模式切換按鈕或下拉選單
  - 根據副檔名自動選擇預設模式
  - 驗證：工具列正確渲染

- [x] **T4.3** 實作 Markdown 預覽模式
  - 使用 `marked.parse()` 渲染內容
  - 套用 `.markdown-rendered` 樣式
  - 驗證：`.md` 檔案正確預覽

- [x] **T4.4** 實作 JSON 格式化模式
  - 使用 `JSON.parse()` + `JSON.stringify(null, 2)` 美化
  - 實作語法色彩渲染函式
  - 錯誤處理：格式不正確時顯示原始文字 + 錯誤提示
  - 驗證：`.json` 檔案正確格式化顯示

- [x] **T4.5** 實作 YAML 格式化模式
  - 實作簡易 YAML 語法色彩渲染
  - 解析鍵值對、字串、數字、布林等
  - 錯誤處理：格式不正確時顯示原始文字
  - 驗證：`.yaml`, `.yml` 檔案正確格式化顯示

- [x] **T4.6** 實作 XML 格式化模式
  - 使用 DOMParser 解析 XML
  - 美化縮排並套用語法色彩
  - 錯誤處理：格式不正確時顯示原始文字
  - 驗證：`.xml` 檔案正確格式化顯示

- [x] **T4.7** 新增 TextViewer 工具列樣式
  - 在 `viewer.css` 中新增工具列樣式
  - 模式切換按鈕樣式（active 狀態）
  - 支援暗色/亮色主題
  - 驗證：工具列外觀符合設計系統

- [x] **T4.8** 測試 TextViewer 主題切換
  - 各顯示模式下切換暗色/亮色主題
  - 驗證所有格式化樣式正確更新

### Phase 5: 整合測試與收尾

- [x] **T5.1** 整合測試 - AI 助手
  - 多種 Markdown 格式的 AI 回應
  - 暗色/亮色主題切換
  - 長訊息效能測試

- [x] **T5.2** 整合測試 - 專案管理
  - 會議內容包含各種 Markdown 元素
  - 主題切換測試

- [x] **T5.3** 整合測試 - TextViewer
  - 各種檔案類型的顯示模式切換
  - 格式錯誤的檔案處理
  - 大型檔案效能測試
  - 主題切換測試

- [x] **T5.4** 安全性檢查
  - 確認 Markdown 渲染無 XSS 風險
  - 確認格式化顯示無注入風險

## 任務依賴關係

```
T1.1 ──────┬──> T2.1 ──> T2.2 ──> T2.3 ──> T5.1
           │
           ├──> T3.1 ──> T3.2 ──> T5.2
           │
T1.2 ──┬──>│
       │   │
T1.3 ──┴───┴──> T4.1 ──> T4.2 ──> T4.3 ──┬──> T4.7 ──> T4.8 ──> T5.3
                              ├──> T4.4 ──┤
                              ├──> T4.5 ──┤
                              └──> T4.6 ──┘

T5.1, T5.2, T5.3 ──> T5.4
```

## 可平行執行的任務

- T1.1, T1.2, T1.3 可平行進行
- T2.x, T3.x, T4.x 在 Phase 1 完成後可平行進行
- T4.3, T4.4, T4.5, T4.6 可平行進行

## 完成記錄

**實作完成日期**: 2025-12-12

### 修改的檔案

1. `frontend/css/main.css`
   - 新增 Markdown 渲染 CSS 變數（暗色/亮色主題）
   - 新增格式化資料語法色彩 CSS 變數（暗色/亮色主題）
   - 新增 `.markdown-rendered` 通用類別
   - 新增 `.formatted-data` 及 `.fd-*` 語法色彩類別

2. `frontend/js/ai-assistant.js`
   - 新增 `renderMarkdown()` 函式
   - 修改 `renderMessages()` 讓 AI 回應使用 Markdown 渲染

3. `frontend/css/project-management.css`
   - 擴展 `.pm-meeting-content` 的 Markdown 樣式

4. `frontend/js/text-viewer.js`
   - 重構為支援多種顯示模式
   - 新增顯示模式狀態管理
   - 實作 Markdown/JSON/YAML/XML 格式化函式
   - 根據副檔名自動選擇預設模式

5. `frontend/css/viewer.css`
   - 新增 TextViewer 工具列樣式
   - 新增模式切換按鈕樣式
   - 新增錯誤提示列樣式
