# file-common Specification

## Purpose
TBD - created by archiving change unify-file-display. Update Purpose after archive.
## Requirements
### Requirement: 檔案類型顏色

系統 SHALL 定義統一的檔案類型顏色變數。

#### Scenario: 圖片類型顏色
- **Given** 檔案類型為 `image`
- **When** 套用 `.file-icon-wrapper.image` class
- **Then** 背景使用 `--tag-bg-green`，文字使用 `--tag-color-green`

#### Scenario: 影片類型顏色
- **Given** 檔案類型為 `video`
- **When** 套用 `.file-icon-wrapper.video` class
- **Then** 背景使用 `--tag-bg-purple`，文字使用 `--tag-color-purple`

#### Scenario: 音訊類型顏色
- **Given** 檔案類型為 `audio`
- **When** 套用 `.file-icon-wrapper.audio` class
- **Then** 背景使用 `--tag-bg-yellow`，文字使用 `--tag-color-yellow`

#### Scenario: PDF 類型顏色
- **Given** 檔案類型為 `pdf`
- **When** 套用 `.file-icon-wrapper.pdf` class
- **Then** 背景使用 `--tag-bg-red`，文字使用 `--tag-color-red`

#### Scenario: 程式碼類型顏色
- **Given** 檔案類型為 `code`
- **When** 套用 `.file-icon-wrapper.code` class
- **Then** 背景使用 `--tag-bg-cyan`，文字使用 `--tag-color-cyan`

#### Scenario: CAD 類型顏色
- **Given** 檔案類型為 `cad`
- **When** 套用 `.file-icon-wrapper.cad` class
- **Then** 背景使用 `--tag-bg-orange`，文字使用 `--tag-color-orange`

### Requirement: 儲存位置標籤

系統 SHALL 顯示檔案儲存位置標籤。

#### Scenario: 顯示 NAS 標籤
- **Given** 檔案有 `nas_path` 或 `storage_path` 以 `nas://` 開頭
- **When** 渲染儲存位置標籤
- **Then** 顯示藍色「NAS」標籤

#### Scenario: 顯示本機標籤
- **Given** 檔案沒有 NAS 路徑且有本機路徑
- **When** 渲染儲存位置標籤
- **Then** 顯示灰色「本機」標籤

#### Scenario: 不顯示標籤
- **Given** LineBot 檔案沒有 `nas_path`（儲存失敗）
- **When** 渲染儲存位置標籤
- **Then** 不顯示任何標籤

### Requirement: 專案管理附件預覽

系統 SHALL 支援專案管理附件的雙擊預覽功能。

#### Scenario: 雙擊附件開啟預覽
- **Given** 使用者在專案管理的附件列表中
- **When** 使用者雙擊某個附件卡片
- **Then** 系統開啟對應的檔案預覽器（ImageViewer、PdfViewer、TextViewer 等）

#### Scenario: 單擊附件不觸發預覽
- **Given** 使用者在專案管理的附件列表中
- **When** 使用者單擊某個附件卡片
- **Then** 不觸發預覽（保留原有的按鈕操作）

### Requirement: 知識庫附件預覽

系統 SHALL 支援知識庫附件的雙擊預覽功能。

#### Scenario: 雙擊附件開啟預覽
- **Given** 使用者在知識庫的附件區域中
- **When** 使用者雙擊某個附件卡片
- **Then** 系統開啟對應的檔案預覽器

#### Scenario: 單擊附件不觸發預覽
- **Given** 使用者在知識庫的附件區域中
- **When** 使用者單擊某個附件卡片
- **Then** 不觸發預覽（保留原有的按鈕操作）

### Requirement: LineBot 檔案標籤修正

系統 SHALL 修正 LineBot 檔案的儲存狀態標籤顯示邏輯。

#### Scenario: 有 NAS 路徑顯示 NAS 標籤
- **Given** LineBot 檔案有 `nas_path`
- **When** 渲染檔案卡片
- **Then** 顯示藍色「NAS」標籤

#### Scenario: 無 NAS 路徑不顯示標籤
- **Given** LineBot 檔案沒有 `nas_path`（表示儲存失敗）
- **When** 渲染檔案卡片
- **Then** 不顯示任何儲存位置標籤

