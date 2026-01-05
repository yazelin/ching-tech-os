# Tasks: unify-file-display

## Phase 1: 建立統一工具模組

- [x] 建立 `frontend/js/file-utils.js` 模組
  - [x] 定義副檔名分類常數（EXTENSIONS）
  - [x] 定義圖示映射常數（ICON_MAP）
  - [x] 實作 `getExtension(filename)`
  - [x] 實作 `getFileCategory(filename, fileType, isDirectory)`
  - [x] 實作 `getFileIcon(filename, fileType, isDirectory)`
  - [x] 實作 `getFileTypeClass(filename, fileType, isDirectory)`
  - [x] 實作 `formatFileSize(bytes)`
  - [x] 實作輔助函式：`isTextFile`, `isImageFile`, `isVideoFile`, `isAudioFile`, `isPdfFile`

- [x] 補充 `icons.js` 缺少的圖示
  - [x] `file-excel` (試算表)
  - [x] `file-powerpoint` (簡報)
  - [x] `folder-zip` (壓縮檔)

## Phase 2: 建立統一樣式

- [x] 建立 `frontend/css/file-common.css`
  - [x] 定義檔案類型顏色變數
  - [x] 定義檔案卡片基礎樣式
  - [x] 定義圖示包裝器樣式（依類型著色）
  - [x] 定義儲存位置標籤樣式

- [x] 在 `index.html` 引入新檔案

## Phase 3: 更新 LineBot 模組

- [x] 更新 `linebot.js` 使用 FileUtils
  - [x] 移除 `getFileTypeIconName()` 函式
  - [x] 改用 `FileUtils.getFileIcon()`
  - [x] 改用 `FileUtils.getFileTypeClass()`
  - [x] 改用 `FileUtils.formatFileSize()`
  - [x] 修正儲存標籤邏輯：移除「未儲存」，只在有 NAS 時顯示「NAS」

- [x] 更新樣式使用統一 `.file-icon-btn` 類別

## Phase 4: 更新專案管理模組

- [x] 更新 `project-management.js` 使用 FileUtils
  - [x] 移除 `getAttachmentIcon()` 函式
  - [x] 改用 `FileUtils.getFileIcon()`
  - [x] 改用 `FileUtils.getFileTypeClass()`
  - [x] 新增附件卡片雙擊事件監聽
  - [x] 雙擊觸發 `previewAttachment()`

- [x] 更新樣式使用統一 `.file-icon-wrapper` 和 `.file-icon-btn` 類別

## Phase 5: 更新知識庫模組

- [x] 更新 `knowledge-base.js` 使用 FileUtils
  - [x] 移除 `getAttachmentIconType()` 和 `getAttachmentIcon()` 函式
  - [x] 改用 `FileUtils.getFileIcon()`
  - [x] 改用 `FileUtils.getFileTypeClass()`
  - [x] 新增附件卡片雙擊事件監聽
  - [x] 雙擊觸發預覽

- [x] 更新樣式使用統一 `.file-icon-wrapper`、`.storage-badge` 和 `.file-icon-btn` 類別

## Phase 6: 更新檔案管理模組

- [x] 更新 `file-manager.js` 使用 FileUtils
  - [x] 移除本地的 `FILE_ICONS` 常數
  - [x] 移除本地的 `TEXT_EXTENSIONS`、`IMAGE_EXTENSIONS` 常數
  - [x] 改寫 `getFileIcon()` 和 `getFileTypeClass()` 委派給 FileUtils
  - [x] 改用 `FileUtils.isImageFile()` 和 `FileUtils.isTextFile()`

## Phase 7: 驗證測試

- [x] 測試檔案管理器圖示顯示
- [x] 測試專案管理附件圖示和雙擊預覽
- [x] 測試知識庫附件圖示和雙擊預覽
- [x] 測試 LineBot 檔案圖示和標籤顯示
- [x] 驗證所有副檔名都能正確映射到圖示
