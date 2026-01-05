# file-utils Specification

## Purpose
TBD - created by archiving change unify-file-display. Update Purpose after archive.
## Requirements
### Requirement: 檔案類型判斷

系統 SHALL 根據檔案名稱（副檔名）判斷檔案類型分類。

#### Scenario: 判斷圖片檔
- **Given** 檔案名稱為 `photo.jpg`
- **When** 呼叫 `FileUtils.getFileCategory('photo.jpg')`
- **Then** 回傳 `'image'`

#### Scenario: 判斷 PDF 檔
- **Given** 檔案名稱為 `document.pdf`
- **When** 呼叫 `FileUtils.getFileCategory('document.pdf')`
- **Then** 回傳 `'pdf'`

#### Scenario: 判斷程式碼檔
- **Given** 檔案名稱為 `app.js`
- **When** 呼叫 `FileUtils.getFileCategory('app.js')`
- **Then** 回傳 `'code'`

#### Scenario: 判斷 CAD 檔
- **Given** 檔案名稱為 `drawing.dwg`
- **When** 呼叫 `FileUtils.getFileCategory('drawing.dwg')`
- **Then** 回傳 `'cad'`

#### Scenario: 無法判斷類型
- **Given** 檔案名稱為 `unknown.xyz`
- **When** 呼叫 `FileUtils.getFileCategory('unknown.xyz')`
- **Then** 回傳 `'default'`

#### Scenario: 使用 fileType 參數輔助判斷
- **Given** 檔案名稱為 `file_123` 且 `fileType` 為 `'image'`
- **When** 呼叫 `FileUtils.getFileCategory('file_123', 'image')`
- **Then** 回傳 `'image'`

### Requirement: 檔案圖示取得

系統 SHALL 根據檔案類型取得對應的圖示名稱（對應 icons.js）。

#### Scenario: 取得圖片檔圖示
- **Given** 檔案名稱為 `photo.png`
- **When** 呼叫 `FileUtils.getFileIcon('photo.png')`
- **Then** 回傳 `'image'`

#### Scenario: 取得 PDF 檔圖示
- **Given** 檔案名稱為 `report.pdf`
- **When** 呼叫 `FileUtils.getFileIcon('report.pdf')`
- **Then** 回傳 `'file-pdf-box'`

#### Scenario: 取得資料夾圖示
- **Given** `isDirectory` 為 `true`
- **When** 呼叫 `FileUtils.getFileIcon('folder', null, true)`
- **Then** 回傳 `'folder'`

#### Scenario: 取得壓縮檔圖示
- **Given** 檔案名稱為 `archive.zip`
- **When** 呼叫 `FileUtils.getFileIcon('archive.zip')`
- **Then** 回傳 `'folder-zip'`

### Requirement: 檔案類型 CSS class

系統 SHALL 根據檔案類型取得對應的 CSS class 名稱（用於顏色樣式）。

#### Scenario: 取得圖片類型 class
- **Given** 檔案名稱為 `photo.jpg`
- **When** 呼叫 `FileUtils.getFileTypeClass('photo.jpg')`
- **Then** 回傳 `'image'`

#### Scenario: 取得影片類型 class
- **Given** 檔案名稱為 `video.mp4`
- **When** 呼叫 `FileUtils.getFileTypeClass('video.mp4')`
- **Then** 回傳 `'video'`

### Requirement: 檔案大小格式化

系統 SHALL 將位元組數格式化為人類可讀的字串。

#### Scenario: 格式化 KB
- **Given** 位元組數為 `1536`
- **When** 呼叫 `FileUtils.formatFileSize(1536)`
- **Then** 回傳 `'1.5 KB'`

#### Scenario: 格式化 MB
- **Given** 位元組數為 `1572864`
- **When** 呼叫 `FileUtils.formatFileSize(1572864)`
- **Then** 回傳 `'1.5 MB'`

#### Scenario: 格式化 0 位元組
- **Given** 位元組數為 `0`
- **When** 呼叫 `FileUtils.formatFileSize(0)`
- **Then** 回傳 `'0 B'`

#### Scenario: 格式化 null
- **Given** 位元組數為 `null`
- **When** 呼叫 `FileUtils.formatFileSize(null)`
- **Then** 回傳 `'-'`

### Requirement: 檔案類型輔助判斷

系統 SHALL 提供快速判斷檔案類型的輔助函式。

#### Scenario: 判斷是否為文字檔
- **Given** 檔案名稱為 `readme.md`
- **When** 呼叫 `FileUtils.isTextFile('readme.md')`
- **Then** 回傳 `true`

#### Scenario: 判斷是否為圖片檔
- **Given** 檔案名稱為 `photo.png`
- **When** 呼叫 `FileUtils.isImageFile('photo.png')`
- **Then** 回傳 `true`

#### Scenario: 判斷是否為 PDF
- **Given** 檔案名稱為 `document.pdf`
- **When** 呼叫 `FileUtils.isPdfFile('document.pdf')`
- **Then** 回傳 `true`

