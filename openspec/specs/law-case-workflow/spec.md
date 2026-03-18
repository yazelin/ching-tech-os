## ADDED Requirements

### Requirement: 五階段工作流 Skill
系統 SHALL 提供 `case-workflow` Skill，定義從案件建立到文書交付的五階段工作流 SOP，每個階段 MUST 在完成後設置人類確認門。

#### Scenario: 啟動工作流
- **WHEN** 使用者對 AI 說「幫我處理王小明損害賠償案」或觸發 `case-workflow` Skill
- **THEN** AI 進入階段 1（案件總覽與事實整理），呼叫 `create_case` 建立案件，提示使用者將證據檔案放入 `20_證據/` 資料夾

### Requirement: 階段 1 — 案件總覽與事實整理
AI SHALL 讀取案件資料夾中的所有文件，呼叫 `generate_evidence_index` 建立證據目錄，產出事實摘要和爭點清單，存入 `00_案件總覽/`。

#### Scenario: 完成事實整理
- **WHEN** AI 完成證據掃描和事實整理
- **THEN** 在 `00_案件總覽/` 產出「事實摘要.md」、「爭點清單.md」、「證據目錄.md」，並向使用者確認事實是否正確

#### Scenario: 人類確認門
- **WHEN** AI 產出事實摘要後
- **THEN** AI MUST 暫停並詢問使用者：(1) 事實摘要是否正確、(2) 指定後續工作方向（撰寫哪種文書）

### Requirement: 階段 2 — 策略分析
AI SHALL 使用 extended thinking 模式分析案件爭點和攻防策略，呼叫 `search_judgments` 搜尋相關判決作為參考。

#### Scenario: 完成策略分析
- **WHEN** AI 完成策略分析
- **THEN** 在 `80_AI產出/` 產出「策略分析報告.md」，包含：爭點分析、攻防策略建議、相關判決引用、風險評估

#### Scenario: 人類確認門
- **WHEN** AI 產出策略分析後
- **THEN** AI MUST 暫停並詢問使用者：選擇哪個策略方向、是否需要調整論點架構

### Requirement: 階段 3 — 文書撰寫
AI SHALL 呼叫 `draft_legal_document` 依選定的模板撰寫法律文書草稿。

#### Scenario: 完成文書撰寫
- **WHEN** AI 完成文書撰寫
- **THEN** 在 `80_AI產出/` 產出文書草稿（Markdown 格式），文書結構符合模板定義

#### Scenario: 人類確認門
- **WHEN** AI 產出文書草稿後
- **THEN** AI MUST 暫停並請使用者審閱草稿，等待修改指示

### Requirement: 階段 4 — 事實核查
AI SHALL 呼叫 `verify_citations` 核查文書中所有引用的判決字號和法條，交叉比對文書內容與原始證據。

#### Scenario: 完成事實核查
- **WHEN** AI 完成核查
- **THEN** 在 `80_AI產出/` 產出「核查報告.md」，列出：(1) 每個引用的驗證結果、(2) 發現的幻覺引用、(3) 與證據不符的陳述

#### Scenario: 發現問題
- **WHEN** 核查發現幻覺引用或事實錯誤
- **THEN** AI SHALL 自動修正文書草稿中的問題，並在核查報告中標記已修正項目

### Requirement: 階段 5 — 組裝與交付
AI SHALL 將最終審定的文書透過 `md2doc` 轉換為 Word 檔案，存入案件的 `10_書狀/` 資料夾。

#### Scenario: 完成交付
- **WHEN** AI 完成 Word 輸出
- **THEN** 最終文件存入 `10_書狀/`，AI 向使用者報告完成並提供檔案路徑

#### Scenario: 人類確認門
- **WHEN** AI 交付最終文件後
- **THEN** AI MUST 提示使用者進行最終審閱，強調「AI 產出的法律文書僅供參考，MUST 由執業律師審閱確認後方可使用」

### Requirement: 工作流可中斷恢復
工作流的每個階段產出 SHALL 以檔案形式存入案件資料夾，使工作流在中斷後可從最近完成的階段繼續。

#### Scenario: 中斷後恢復
- **WHEN** 工作流在階段 2 完成後中斷，使用者在新對話中要求繼續
- **THEN** AI 檢查案件資料夾中已存在的產出檔案（事實摘要、策略分析報告），判斷可從階段 3 繼續

#### Scenario: 判斷工作流進度
- **WHEN** AI 需要判斷目前進度
- **THEN** 依據 `00_案件總覽/`、`80_AI產出/` 中已存在的檔案推斷已完成的階段
