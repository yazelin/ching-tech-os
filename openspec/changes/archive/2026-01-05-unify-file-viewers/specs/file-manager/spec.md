# file-manager Specification

## REMOVED Requirements

### Requirement: 圖片檢視器
> 移至獨立的 `image-viewer` spec

---

### Requirement: 文字檢視器
> 移至獨立的 `text-viewer` spec（已存在）

## MODIFIED Requirements

### Requirement: 檔案預覽面板
系統 SHALL 在檔案管理視窗右側提供快速預覽面板。

#### Scenario: 雙擊開啟檔案
- **GIVEN** 檔案管理視窗已開啟
- **WHEN** 雙擊支援的檔案類型（圖片、文字、PDF）
- **THEN** 呼叫 `FileOpener.open()` 開啟對應的檢視器
> 原本直接呼叫各 Viewer，改為統一使用 FileOpener
