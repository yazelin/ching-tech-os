# pdf-viewer Specification

## Purpose
TBD - created by archiving change unify-file-viewers. Update Purpose after archive.
## Requirements
### Requirement: PDF 檢視器視窗
系統 SHALL 提供獨立的 PDF 檢視器模組。

#### Scenario: 開啟 PDF 檢視器
- **WHEN** 呼叫 `PdfViewerModule.open(filePath, filename)`
- **THEN** 開啟 PDF 檢視器視窗
- **AND** 使用 PDF.js 載入並渲染 PDF 文件
- **AND** 視窗標題顯示檔案名稱

#### Scenario: 關閉 PDF 檢視器
- **WHEN** 呼叫 `PdfViewerModule.close()` 或點擊視窗關閉按鈕
- **THEN** 關閉 PDF 檢視器視窗
- **AND** 釋放 PDF.js 資源

---

### Requirement: PDF 頁面導航
PDF 檢視器 SHALL 提供頁面導航功能。

#### Scenario: 顯示頁碼資訊
- **GIVEN** PDF 檢視器已開啟
- **THEN** 工具列顯示目前頁碼和總頁數（如「1 / 10」）

#### Scenario: 下一頁
- **GIVEN** PDF 檢視器已開啟且不在最後一頁
- **WHEN** 點擊「下一頁」按鈕
- **THEN** 顯示下一頁內容
- **AND** 頁碼資訊更新

#### Scenario: 上一頁
- **GIVEN** PDF 檢視器已開啟且不在第一頁
- **WHEN** 點擊「上一頁」按鈕
- **THEN** 顯示上一頁內容
- **AND** 頁碼資訊更新

#### Scenario: 跳至指定頁
- **GIVEN** PDF 檢視器已開啟
- **WHEN** 在頁碼輸入框輸入頁碼並按 Enter
- **AND** 輸入的頁碼在有效範圍內
- **THEN** 跳至指定頁面

#### Scenario: 無效頁碼處理
- **GIVEN** PDF 檢視器已開啟
- **WHEN** 輸入超出範圍的頁碼
- **THEN** 頁碼輸入框恢復為目前頁碼
- **AND** 不進行頁面跳轉

---

### Requirement: PDF 縮放功能
PDF 檢視器 SHALL 提供縮放功能。

#### Scenario: 放大 PDF
- **GIVEN** PDF 檢視器已開啟
- **WHEN** 點擊放大按鈕
- **THEN** PDF 頁面放大顯示
- **AND** 縮放比例顯示在工具列

#### Scenario: 縮小 PDF
- **GIVEN** PDF 檢視器已開啟
- **WHEN** 點擊縮小按鈕
- **THEN** PDF 頁面縮小顯示
- **AND** 縮放比例顯示在工具列

#### Scenario: 適合寬度
- **GIVEN** PDF 檢視器已開啟
- **WHEN** 點擊「適合寬度」按鈕
- **THEN** PDF 頁面縮放至適合視窗寬度

#### Scenario: 適合頁面
- **GIVEN** PDF 檢視器已開啟
- **WHEN** 點擊「適合頁面」按鈕
- **THEN** PDF 頁面縮放至完整顯示在視窗內

---

### Requirement: PDF 資訊顯示
PDF 檢視器 SHALL 在狀態列顯示文件資訊。

#### Scenario: 顯示 PDF 資訊
- **GIVEN** PDF 檢視器已開啟並載入文件
- **THEN** 狀態列顯示檔案名稱
- **AND** 狀態列顯示目前縮放比例

