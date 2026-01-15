# document-reader Specification

## Purpose
提供文件內容讀取功能，支援 Word、Excel、PowerPoint、PDF 等常見文件格式的文字提取，供 AI 進行分析、總結或查詢。

## Requirements

## ADDED Requirements

### Requirement: Document Reader Service
系統 SHALL 提供 Document Reader Service 用於提取文件文字內容。

#### Scenario: 解析 Word 文件 (.docx)
- **GIVEN** 一個有效的 .docx 檔案
- **WHEN** 呼叫 `extract_text(file_path)`
- **THEN** 系統使用 python-docx 解析文件
- **AND** 回傳包含所有段落文字的 DocumentContent
- **AND** 包含文件中的表格內容（以 | 分隔欄位）

#### Scenario: 解析 Excel 試算表 (.xlsx)
- **GIVEN** 一個有效的 .xlsx 檔案
- **WHEN** 呼叫 `extract_text(file_path)`
- **THEN** 系統使用 openpyxl 解析試算表
- **AND** 回傳包含所有工作表的完整內容
- **AND** 每個工作表以「=== 工作表: {名稱} ===」分隔
- **AND** 每行以 | 分隔欄位
- **AND** AI 可根據內容自行判斷或詢問用戶需要哪些資訊

#### Scenario: 解析 PowerPoint 簡報 (.pptx)
- **GIVEN** 一個有效的 .pptx 檔案
- **WHEN** 呼叫 `extract_text(file_path)`
- **THEN** 系統使用 python-pptx 解析簡報
- **AND** 回傳包含所有投影片的文字內容
- **AND** 每張投影片以「=== 投影片 {編號} ===」分隔

#### Scenario: 解析 PDF 文件
- **GIVEN** 一個有效的 .pdf 檔案
- **WHEN** 呼叫 `extract_text(file_path)`
- **THEN** 系統使用 PyMuPDF 解析 PDF
- **AND** 回傳包含所有頁面的文字內容

#### Scenario: 檔案大小超過限制
- **GIVEN** 檔案大小超過 10MB
- **WHEN** 呼叫 `extract_text(file_path)`
- **THEN** 系統回傳錯誤訊息「檔案過大，請使用小於 10MB 的檔案」

#### Scenario: 文字內容超過限制
- **GIVEN** 提取的文字超過 100,000 字元
- **WHEN** 解析完成
- **THEN** 系統截斷內容並標註 `truncated = true`
- **AND** 回傳訊息說明「內容已截斷，原文共 X 字元」

#### Scenario: 加密文件
- **GIVEN** 檔案有密碼保護
- **WHEN** 呼叫 `extract_text(file_path)`
- **THEN** 系統回傳錯誤訊息「此文件有密碼保護，無法讀取」
- **AND** 不支援輸入密碼解鎖

#### Scenario: 純圖片 PDF
- **GIVEN** PDF 為掃描圖片（沒有文字層）
- **WHEN** 呼叫 `extract_text(file_path)`
- **THEN** 系統回傳提示「此 PDF 為掃描圖片，建議截圖後上傳讓 AI 讀取」

#### Scenario: 損壞的文件
- **GIVEN** 檔案損壞或格式無效
- **WHEN** 呼叫 `extract_text(file_path)`
- **THEN** 系統回傳 CorruptedFileError
- **AND** 錯誤訊息為「文件損壞或格式無效」

#### Scenario: 不支援的格式
- **GIVEN** 檔案格式不在支援清單中
- **WHEN** 呼叫 `extract_text(file_path)`
- **THEN** 系統回傳 UnsupportedFormatError
- **AND** 錯誤訊息說明支援的格式

---

## MODIFIED Requirements

### Requirement: Line Bot 對話歷史包含檔案資訊
Line Bot 的對話歷史 SHALL 包含用戶上傳的可讀取檔案資訊，讓 AI 能夠感知並自行決定是否處理。

#### Scenario: 對話歷史包含 Office 文件
- **WHEN** 系統組合對話歷史給 AI
- **AND** 歷史中包含 Office 文件（.docx, .xlsx, .pptx）
- **THEN** 系統呼叫 Document Reader Service 解析文件
- **AND** 將純文字結果存入暫存檔
- **AND** 檔案訊息格式化為 `[上傳檔案: /tmp/linebot-files/{line_message_id}_{filename}.txt]`
- **AND** AI 可以看到用戶上傳了文件及其純文字路徑

#### Scenario: 對話歷史包含 PDF 文件
- **WHEN** 系統組合對話歷史給 AI
- **AND** 歷史中包含 PDF 文件
- **THEN** 系統呼叫 Document Reader Service 解析 PDF
- **AND** 將純文字結果存入暫存檔
- **AND** AI 可透過 Read 工具讀取純文字內容

#### Scenario: Office 文件解析失敗
- **WHEN** Document Reader Service 解析失敗
- **THEN** 對話歷史顯示 `[上傳檔案: {filename}（解析失敗：{錯誤原因}）]`
- **AND** AI 可告知用戶文件無法讀取的原因

### Requirement: Line Bot 檔案類型支援
Line Bot SHALL 支援讀取以下檔案類型。

#### Scenario: 擴充可讀取的副檔名
- **WHEN** 系統判斷檔案是否可讀取
- **THEN** 可讀取的副檔名包含：
  - 純文字：`.txt`, `.md`, `.json`, `.csv`, `.log`, `.xml`, `.yaml`, `.yml`
  - Office 文件：`.docx`, `.xlsx`, `.pptx`
  - PDF 文件：`.pdf`

#### Scenario: 舊版 Office 格式提示
- **WHEN** 用戶上傳 `.doc`, `.xls`, `.ppt` 舊版格式
- **THEN** 對話歷史顯示 `[上傳檔案: {filename}（不支援舊版格式，請轉存為 .docx/.xlsx/.pptx）]`
- **AND** AI 應建議用戶使用 Office 或 Google Docs 轉存為新版格式

---

## ADDED Requirements

### Requirement: read_document MCP 工具
MCP Server SHALL 提供 `read_document` 工具讓 AI 助手讀取文件內容。

#### Scenario: 讀取 NAS 上的 Word 文件
- **GIVEN** AI 需要讀取 NAS 上的 .docx 檔案
- **WHEN** 呼叫 `read_document(file_path="/mnt/nas/projects/.../xxx.docx")`
- **THEN** 系統解析文件並回傳純文字內容

#### Scenario: 讀取 Excel 試算表
- **GIVEN** AI 需要讀取 NAS 上的 .xlsx 檔案
- **WHEN** 呼叫 `read_document(file_path="...")`
- **THEN** 系統解析試算表並回傳格式化的內容
- **AND** 包含工作表名稱和表格資料

#### Scenario: 讀取 PowerPoint 簡報
- **GIVEN** AI 需要讀取 NAS 上的 .pptx 檔案
- **WHEN** 呼叫 `read_document(file_path="...")`
- **THEN** 系統解析簡報並回傳各投影片的文字內容

#### Scenario: 讀取 PDF 文件
- **GIVEN** AI 需要讀取 NAS 上的 .pdf 檔案
- **WHEN** 呼叫 `read_document(file_path="...")`
- **THEN** 系統解析 PDF 並回傳純文字內容

#### Scenario: 內容過長時截斷
- **GIVEN** AI 呼叫 `read_document`
- **AND** 提取的文字超過 `max_chars` 參數（預設 50000）
- **WHEN** 解析完成
- **THEN** 系統截斷內容
- **AND** 附加訊息「內容已截斷，原文共 X 字元」

#### Scenario: 檔案不存在
- **WHEN** 呼叫 `read_document` 且檔案路徑不存在
- **THEN** 回傳錯誤訊息「檔案不存在」

#### Scenario: 路徑超出允許範圍
- **WHEN** 呼叫 `read_document` 且路徑不在允許的 NAS 掛載點下
- **THEN** 回傳錯誤訊息「不允許存取此路徑」
