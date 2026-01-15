## ADDED Requirements

### Requirement: PDF 轉圖片 MCP 工具
MCP Server SHALL 提供 `convert_pdf_to_images` 工具讓 AI 將 PDF 檔案轉換為圖片。

#### Scenario: 查詢 PDF 頁數（不轉換）
- **GIVEN** AI 需要先知道 PDF 有幾頁
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="0")`
- **THEN** 系統只回傳 PDF 頁數資訊，不進行轉換
- **AND** 回傳格式包含 `total_pages` 和 `converted_pages: 0`

#### Scenario: 單頁 PDF 轉換
- **GIVEN** AI 有單頁 PDF 檔案路徑
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...")`
- **THEN** 系統將該頁轉換為 PNG 圖片
- **AND** 圖片儲存到 NAS 的 `linebot/files/pdf-converted/{date}/{uuid}/` 目錄
- **AND** 回傳轉換結果，包含圖片路徑

#### Scenario: 指定頁面範圍轉換
- **GIVEN** AI 需要轉換特定頁面
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="1-3")`
- **THEN** 系統只轉換第 1、2、3 頁
- **AND** 回傳轉換的圖片路徑列表

#### Scenario: 轉換指定的單頁
- **GIVEN** AI 只需要轉換特定一頁
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="2")`
- **THEN** 系統只轉換第 2 頁

#### Scenario: 轉換多個不連續頁面
- **GIVEN** AI 需要轉換不連續的頁面
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="1,3,5")`
- **THEN** 系統轉換第 1、3、5 頁

#### Scenario: 轉換全部頁面
- **GIVEN** AI 需要轉換全部頁面
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="all")`
- **THEN** 系統轉換所有頁面（最多 max_pages 頁）

#### Scenario: 指定輸出格式
- **GIVEN** AI 需要特定格式的圖片
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", output_format="jpg")`
- **THEN** 系統將 PDF 轉換為 JPG 格式圖片

#### Scenario: 指定解析度
- **GIVEN** AI 需要高解析度圖片
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", dpi=300)`
- **THEN** 系統使用 300 DPI 進行轉換

#### Scenario: PDF 檔案不存在
- **WHEN** 呼叫 `convert_pdf_to_images` 且 PDF 路徑不存在
- **THEN** 回傳錯誤訊息「PDF 檔案不存在」

#### Scenario: 非 PDF 檔案
- **WHEN** 呼叫 `convert_pdf_to_images` 且檔案不是 PDF 格式
- **THEN** 回傳錯誤訊息「檔案不是 PDF 格式」

#### Scenario: 轉換成功回傳格式
- **WHEN** 轉換成功
- **THEN** 回傳 JSON 格式結果：
  - `success`: true
  - `total_pages`: PDF 總頁數
  - `converted_pages`: 實際轉換的頁數
  - `images`: 圖片路徑陣列
  - `message`: 人類可讀的結果描述

#### Scenario: 搭配 prepare_file_message 發送圖片
- **GIVEN** AI 已完成 PDF 轉換
- **WHEN** AI 呼叫 `prepare_file_message` 傳入轉換後的圖片路徑
- **THEN** 系統準備檔案訊息供 Line Bot 發送
- **AND** 用戶可以在 Line 中直接查看圖片

---

### Requirement: PDF 轉換工具參數規格
`convert_pdf_to_images` 工具 SHALL 支援以下參數：

#### Scenario: 工具參數定義
- **WHEN** AI 呼叫 `convert_pdf_to_images` 工具
- **THEN** 工具接受以下參數：
  - `pdf_path`：PDF 檔案路徑（必填）
  - `pages`：要轉換的頁面，預設 "all"
    - "0"：只查詢頁數，不轉換
    - "1"：只轉換第 1 頁
    - "1-3"：轉換第 1 到 3 頁
    - "1,3,5"：轉換第 1、3、5 頁
    - "all"：轉換全部頁面
  - `output_format`：輸出格式，可選 "png"（預設）或 "jpg"
  - `dpi`：解析度，預設 150，範圍 72-600
  - `max_pages`：最大頁數限制，預設 20

---

### Requirement: 專案附件 PDF 轉換支援
`get_project_attachments` 工具 SHALL 回傳附件的儲存路徑，讓 AI 可以轉換專案附件中的 PDF。

#### Scenario: 查詢專案附件包含路徑
- **GIVEN** 專案有 PDF 附件
- **WHEN** AI 呼叫 `get_project_attachments(project_id="...")`
- **THEN** 回傳結果包含每個附件的 `路徑` 欄位（storage_path）
- **AND** AI 可以使用該路徑呼叫 `convert_pdf_to_images`

#### Scenario: 轉換專案附件 PDF
- **GIVEN** AI 從 `get_project_attachments` 取得 PDF 附件路徑
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="nas://...")`
- **THEN** 系統轉換該 PDF 為圖片
- **AND** AI 可透過 `prepare_file_message` 發送給用戶
