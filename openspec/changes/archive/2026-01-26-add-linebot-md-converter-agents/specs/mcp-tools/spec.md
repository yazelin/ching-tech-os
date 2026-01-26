# mcp-tools spec delta

## ADDED Requirements

### Requirement: Generate Presentation Tool
系統 SHALL 提供 MCP Tool 讓 AI Agent 產生 MD2PPT 格式的簡報內容。

#### Scenario: 產生簡報
- **GIVEN** LineBot AI 判斷用戶需要產生簡報
- **WHEN** 呼叫 `generate_presentation` tool 並傳入用戶提供的內容
- **THEN** 使用專門的 MD2PPT Agent prompt 產生符合格式的內容
- **AND** 自動建立帶密碼的分享連結
- **AND** 回傳分享連結 URL 和存取密碼

#### Scenario: 格式驗證
- **GIVEN** AI 產生了簡報內容
- **WHEN** 內容不符合 MD2PPT 格式規範
- **THEN** 嘗試自動修正或重新產生

### Requirement: Generate Document Tool
系統 SHALL 提供 MCP Tool 讓 AI Agent 產生 MD2DOC 格式的文件內容。

#### Scenario: 產生文件
- **GIVEN** LineBot AI 判斷用戶需要產生文件
- **WHEN** 呼叫 `generate_document` tool 並傳入用戶提供的內容
- **THEN** 使用專門的 MD2DOC Agent prompt 產生符合格式的內容
- **AND** 自動建立帶密碼的分享連結
- **AND** 回傳分享連結 URL 和存取密碼

#### Scenario: 格式驗證
- **GIVEN** AI 產生了文件內容
- **WHEN** 內容不符合 MD2DOC 格式規範
- **THEN** 嘗試自動修正或重新產生

### Requirement: MD2PPT Agent Prompt
系統 SHALL 包含專門的 MD2PPT Agent system prompt，確保產生的內容符合格式規範。

#### Scenario: Prompt 內容
- **GIVEN** 需要產生 MD2PPT 內容
- **WHEN** 呼叫 generate_presentation tool
- **THEN** 使用的 prompt 包含：
  - 全域設定規範 (theme, transition, title, author)
  - 分頁符號規範 (`===` 前後空行)
  - 頁面配置規範 (layout 選項)
  - Mesh 背景使用規則
  - 圖表語法規範
  - 雙欄語法規範
  - 嚴選配色盤
  - 自我檢核表

### Requirement: MD2DOC Agent Prompt
系統 SHALL 包含專門的 MD2DOC Agent system prompt，確保產生的內容符合格式規範。

#### Scenario: Prompt 內容
- **GIVEN** 需要產生 MD2DOC 內容
- **WHEN** 呼叫 generate_document tool
- **THEN** 使用的 prompt 包含：
  - Frontmatter 規範 (title, author, header, footer)
  - 標題層級限制 (只支援 H1-H3)
  - TOC 位置規範
  - Callout 語法規範 (TIP, NOTE, WARNING)
  - 對話語法規範
  - 行內樣式轉換表
  - 負面約束清單
