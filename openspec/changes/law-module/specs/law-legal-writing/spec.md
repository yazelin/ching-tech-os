## ADDED Requirements

### Requirement: 法律文書撰寫工具
系統 SHALL 提供 `draft_legal_document` MCP 工具，AI 可依指定的文書類型載入對應 Markdown 結構模板，結合案件資料撰寫文書草稿。

#### Scenario: 撰寫民事起訴狀
- **WHEN** AI 呼叫 `draft_legal_document(case_id=1, document_type="civil_complaint")`
- **THEN** 系統載入 `templates/civil_complaint.md` 模板，結合案件資料（當事人、法院、案由等），回傳填入案件資訊的模板結構供 AI 撰寫，AI 產出的草稿存入 `80_AI產出/`

#### Scenario: 附加撰寫指示
- **WHEN** AI 呼叫 `draft_legal_document(case_id=1, document_type="civil_defense", additional_instructions="重點主張時效抗辯")`
- **THEN** 系統將模板結構和附加指示一併提供給 AI 作為撰寫依據

#### Scenario: 無效的文書類型
- **WHEN** `document_type` 不在支援的 10 種類型中
- **THEN** 系統回傳錯誤訊息並列出所有支援的文書類型

### Requirement: 支援 10 種文書類型
系統 SHALL 提供以下 10 種法律文書的 Markdown 結構模板，每種模板 MUST 包含該文書類型在台灣法院要求的標準結構。

#### Scenario: 民事類文書模板結構
- **WHEN** 查看 `civil_complaint.md`（民事起訴狀）模板
- **THEN** 模板包含：案號欄位、當事人欄位（原告/被告/訴訟代理人）、訴之聲明、事實及理由、證據、附件清單

#### Scenario: 刑事類文書模板結構
- **WHEN** 查看 `criminal_complaint.md`（刑事告訴狀）模板
- **THEN** 模板包含：告訴人/被告欄位、告訴事實、所犯法條、證據

#### Scenario: 存證信函模板結構
- **WHEN** 查看 `certified_letter.md`（存證信函）模板
- **THEN** 模板包含：收件人、寄件人、主旨、正文、存證日期

#### Scenario: 法律意見書模板結構
- **WHEN** 查看 `legal_opinion.md`（法律意見書）模板
- **THEN** 模板包含：委託人、案件概述、法律分析、結論與建議

### Requirement: 文書類型清單
系統 SHALL 支援以下文書類型識別碼：`civil_complaint`（民事起訴狀）、`civil_defense`（民事答辯狀）、`preparatory_brief`（準備書狀）、`appeal`（上訴狀）、`petition`（聲請狀）、`criminal_complaint`（刑事告訴狀）、`criminal_defense`（刑事答辯狀）、`certified_letter`（存證信函）、`lawyer_letter`（律師函）、`legal_opinion`（法律意見書）。

#### Scenario: 列出所有支援的文書類型
- **WHEN** AI 呼叫 `draft_legal_document` 且未指定 `document_type`
- **THEN** 系統回傳所有 10 種文書類型的識別碼和中文名稱

### Requirement: 文書輸出 Word
系統 SHALL 支援將 AI 撰寫的 Markdown 文書草稿透過現有的 `md2doc` 工具轉換為 Word 檔案。

#### Scenario: 草稿轉 Word
- **WHEN** AI 撰寫完成草稿後呼叫 `generate_md2doc` 將 `80_AI產出/民事起訴狀草稿.md` 轉為 Word
- **THEN** 產出的 `.docx` 檔案保留文書結構（標題層級、表格、項目符號），存入 `10_書狀/`
