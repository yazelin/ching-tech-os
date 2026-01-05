# file-viewer Specification

## Purpose
統一檔案檢視器架構，提供 FileOpener 入口自動判斷檔案類型並路由到對應的 Viewer 模組。

## ADDED Requirements

### Requirement: FileOpener 統一入口
系統 SHALL 提供 FileOpener 統一入口，自動判斷檔案類型並開啟對應的檢視器。

#### Scenario: 開啟圖片檔
- **GIVEN** 使用者呼叫 `FileOpener.open(url, filename)`
- **AND** filename 副檔名為圖片格式（jpg, jpeg, png, gif, svg, webp, bmp, ico）
- **THEN** 系統呼叫 ImageViewerModule 開啟圖片

#### Scenario: 開啟文字檔
- **GIVEN** 使用者呼叫 `FileOpener.open(url, filename)`
- **AND** filename 副檔名為文字格式（txt, md, json, yaml, yml, xml, html, css, js, py, log, ini, conf, sh, sql）
- **THEN** 系統呼叫 TextViewerModule 開啟文字檔

#### Scenario: 開啟 PDF 檔
- **GIVEN** 使用者呼叫 `FileOpener.open(url, filename)`
- **AND** filename 副檔名為 pdf
- **THEN** 系統呼叫 PdfViewerModule 開啟 PDF

#### Scenario: 不支援的檔案類型
- **GIVEN** 使用者呼叫 `FileOpener.open(url, filename)`
- **AND** filename 副檔名不在支援列表中
- **THEN** 系統顯示提示訊息「不支援的檔案類型」

---

### Requirement: FileOpener 檔案類型查詢
系統 SHALL 提供 API 讓調用方查詢檔案類型支援狀況。

#### Scenario: 判斷檔案是否支援開啟
- **WHEN** 呼叫 `FileOpener.canOpen(filename)`
- **THEN** 回傳布林值表示該檔案類型是否支援開啟

#### Scenario: 取得檔案對應的 Viewer 類型
- **WHEN** 呼叫 `FileOpener.getViewerType(filename)`
- **AND** 檔案類型有對應的 Viewer
- **THEN** 回傳 Viewer 類型字串（'image', 'text', 'pdf'）
- **WHEN** 檔案類型無對應的 Viewer
- **THEN** 回傳 null

---

### Requirement: Viewer 模組契約
每個 Viewer 模組 SHALL 實作統一的介面契約。

#### Scenario: Viewer 基本介面
- **GIVEN** 任何 Viewer 模組（ImageViewer, TextViewer, PdfViewer）
- **THEN** 該模組提供 `open(filePath, filename)` 方法開啟檔案
- **AND** 該模組提供 `close()` 方法關閉檢視器

#### Scenario: Viewer 視窗行為
- **GIVEN** 某類型的 Viewer 已開啟一個檔案
- **WHEN** 再次呼叫 open() 開啟另一個檔案
- **THEN** 關閉舊視窗並開啟新檔案
- **AND** 不會同時存在多個同類型的 Viewer 視窗
