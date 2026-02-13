# printer-integration Specification

## Purpose
透過 CUPS 整合列印功能，讓 AI Agent 可以列印 NAS 檔案、上傳檔案及 AI 生成文件。

## Requirements

### Requirement: 列印檔案工具
系統 SHALL 提供 MCP 工具 `print_file`，可將檔案送至印表機列印，支援虛擬路徑自動轉換。

#### Scenario: 使用虛擬路徑列印知識庫附件
- Given AI Agent 收到列印請求
- And 檔案路徑為 `ctos://knowledge/attachments/report.pdf`
- When 呼叫 `print_file(file_path="ctos://knowledge/attachments/report.pdf")`
- Then PathManager 將路徑轉換為絕對路徑
- And 檔案透過 CUPS `lp` 指令送至預設印表機
- And 回傳列印成功訊息含工作編號

#### Scenario: 指定印表機與列印參數
- Given 使用者指定印表機名稱和參數
- When 呼叫 `print_file(file_path="ctos://...", printer="HP_LaserJet", copies=2, page_size="A3", orientation="landscape")`
- Then 檔案以指定參數送至指定印表機

#### Scenario: Office 文件自動轉 PDF 後列印
- Given 檔案為 `.docx`、`.xlsx` 或 `.pptx` 格式
- When 呼叫 `print_file(file_path="ctos://knowledge/attachments/report.docx")`
- Then 使用 LibreOffice headless 將檔案轉為 PDF 至暫存目錄
- And 將轉換後的 PDF 送至印表機列印
- And 列印完成後清除暫存 PDF

#### Scenario: 檔案路徑安全檢查
- Given 檔案路徑包含 `..` 或指向不允許的目錄
- When 呼叫 `print_file(file_path="/etc/passwd")`
- Then 回傳權限錯誤，拒絕列印

### Requirement: 查詢印表機工具
系統 SHALL 提供 MCP 工具 `list_printers`，可查詢系統中所有可用印表機及其狀態。

#### Scenario: 列出可用印表機
- When 呼叫 `list_printers()`
- Then 回傳所有印表機名稱、狀態、是否為預設印表機

#### Scenario: 無印表機可用
- Given 系統未設定任何印表機
- When 呼叫 `list_printers()`
- Then 回傳提示訊息說明無可用印表機

### Requirement: 列印功能權限控管
列印工具 MUST 受應用權限控管，使用者需有「列印」權限才能使用。

#### Scenario: 無權限使用者嘗試列印
- Given 使用者未被授予「列印」應用權限
- When 呼叫 `print_file(...)`
- Then 回傳權限不足的錯誤訊息

### Requirement: 支援的檔案格式
系統 SHALL 支援以下檔案格式列印：
- 直接列印：PDF、純文字（.txt, .log, .csv）、圖片（PNG, JPG, JPEG, GIF, BMP, TIFF, WebP）
- 自動轉 PDF 後列印：Office 文件（.docx, .xlsx, .pptx, .doc, .xls, .ppt, .odt, .ods, .odp）

#### Scenario: 列印 PDF 檔案
- Given NAS 上有 PDF 檔案
- When 呼叫 `print_file` 指定該檔案
- Then 檔案直接送至印表機

#### Scenario: 列印圖片檔案
- Given Line Bot 收到使用者上傳的 JPG 圖片
- When AI Agent 呼叫 `print_file` 指定該圖片路徑
- Then 圖片送至印表機列印

#### Scenario: 列印 Word 文件
- Given 知識庫有一份 .docx 檔案
- When 呼叫 `print_file` 指定該檔案
- Then LibreOffice headless 轉為 PDF
- And PDF 送至印表機列印

#### Scenario: 不支援的檔案格式
- Given 檔案為不支援的格式（如 .zip）
- When 呼叫 `print_file`
- Then 回傳錯誤訊息說明不支援的格式

### Requirement: MCP 工具清單
系統 SHALL 在 MCP 工具清單中新增 `print_file` 和 `list_printers` 工具。

#### Scenario: AI Agent 可使用列印工具
- Given AI Agent 的 allowed_tools 包含 print_file
- When 使用者要求列印檔案
- Then AI Agent 呼叫 `print_file` 完成列印
