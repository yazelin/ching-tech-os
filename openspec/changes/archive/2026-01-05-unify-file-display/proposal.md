# Proposal: unify-file-display

## Why

目前檔案顯示（圖示、顏色、互動）在不同模組中實作不一致：

1. **圖示判斷重複且不完整**：
   - `file-manager.js` 有自己的 `FILE_ICONS` 映射（txt, md, json, js, css, html, jpg, pdf 等）
   - `project-management.js` 只有簡單的 `getAttachmentIcon()` (image, pdf, cad, document)
   - `knowledge-base.js` 只有 `getAttachmentIcon()` (image, video, document)
   - `linebot.js` 使用最簡化的分類 (image, video, audio, file)

2. **顏色分類不統一**：各模組用不同的方式分類檔案類型顏色

3. **互動行為不一致**：
   - 檔案管理器：雙擊開啟檔案
   - LineBot：雙擊開啟預覽
   - 專案管理：需點擊「預覽」按鈕
   - 知識庫：需點擊「預覽」按鈕

4. **LineBot「未儲存」標籤誤導**：`nas_path` 為空只代表儲存失敗，而非「未儲存」

## What Changes

1. **建立 `FileUtils` 統一工具模組**：
   - `getFileIcon(filename)` - 根據副檔名取得圖示名稱
   - `getFileCategory(filename)` - 取得檔案分類（image, video, audio, pdf, document, code, cad, archive, text）
   - `getFileTypeClass(filename)` - 取得 CSS class 名稱（用於顏色）
   - `formatFileSize(bytes)` - 統一的檔案大小格式化

2. **統一檔案卡片樣式**：定義統一的 CSS 變數和類別

3. **統一互動行為**：
   - 專案管理附件：加入雙擊預覽
   - 知識庫附件：加入雙擊預覽

4. **修正 LineBot 標籤**：移除「未儲存」標籤，改為只在有 NAS 路徑時顯示「NAS」

## Scope

- 新增 `frontend/js/file-utils.js` - 統一檔案工具模組
- 新增 `frontend/css/file-common.css` - 統一檔案樣式變數
- 修改 `frontend/js/file-manager.js` - 改用 FileUtils
- 修改 `frontend/js/project-management.js` - 改用 FileUtils + 雙擊預覽
- 修改 `frontend/js/knowledge-base.js` - 改用 FileUtils + 雙擊預覽
- 修改 `frontend/js/linebot.js` - 改用 FileUtils + 修正標籤
- 補充 `icons.js` 缺少的圖示

## Out of Scope

- 檔案檢視器本身（已在 `unify-file-viewers` 處理）
- 檔案上傳邏輯統一（未來工作）
- 影片/音訊播放器（未來工作）

## Dependencies

- 依賴 `unify-file-viewers` 提供的 `FileOpener` 統一入口
