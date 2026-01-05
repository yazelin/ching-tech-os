# Proposal: unify-file-viewers

## Why

目前 `ImageViewerModule` 和 `TextViewerModule` 是獨立的 IIFE 模組，被多處使用（file-manager、knowledge-base、project-management）。但存在以下問題：

1. **缺乏統一入口**：各 app 需要自己判斷檔案類型並調用對應的 viewer
2. **Spec 不完整**：`image-viewer` 沒有獨立 spec
3. **擴展性不足**：未來新增 PDF、影片等 viewer 時，每個調用處都需要修改
4. **API 不一致**：雖然目前兩個 viewer API 相似，但沒有統一的契約定義

## What Changes

1. **建立 `file-viewer` spec**：定義統一的檔案檢視器架構
2. **新增 `FileOpener` 統一入口**：自動判斷檔案類型並開啟對應 viewer
3. **建立 `image-viewer` 獨立 spec**：從 file-manager spec 分離出來
4. **新增 `PdfViewerModule`**：支援 PDF 檔案檢視
5. **重構現有調用處**：改用 `FileOpener.open()` 統一 API

## Scope

- 新增 `frontend/js/file-opener.js` - 統一入口模組
- 新增 `frontend/js/pdf-viewer.js` - PDF 檢視器
- 新增 `frontend/css/pdf-viewer.css` - PDF 檢視器樣式
- 修改 `file-manager.js`、`knowledge-base.js`、`project-management.js` - 改用 FileOpener
- 從 `file-manager` spec 移除 viewer 相關 requirements
- 建立新的 specs：`file-viewer`、`image-viewer`、`pdf-viewer`

## Out of Scope

- 影片檢視器（未來工作）
- 音訊播放器（未來工作）
- 檔案編輯功能（目前只做檢視）
