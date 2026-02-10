## MODIFIED Requirements

### Requirement: Generate Presentation Tool
系統 SHALL 提供 `generate_md2ppt` MCP Tool，接收已格式化的 MD2PPT markdown 內容，執行格式修正後儲存並建立分享連結。

工具 SHALL NOT 在內部呼叫 Claude 或任何 AI 模型。格式化內容的產生責任由外層 AI Agent 承擔。

工具參數：
- `markdown_content`（str，必填）：已格式化的 MD2PPT markdown，MUST 以 `---` 開頭（frontmatter）
- `ctos_user_id`（int，選填）：CTOS 用戶 ID

工具 SHALL 移除原有的 `content` 和 `style` 參數。

#### Scenario: 接收合法的 MD2PPT markdown 並建立分享連結
- **WHEN** 外層 AI Agent 呼叫 `generate_md2ppt(markdown_content="---\ntitle: ...\n---\n...")` 並傳入以 `---` 開頭的格式化 markdown
- **THEN** 工具執行 `fix_md2ppt_format()` 自動修正格式問題
- **AND** 儲存檔案至 NAS `ai-generated/` 目錄
- **AND** 建立 24 小時有效的帶密碼分享連結
- **AND** 回傳分享連結 URL、存取密碼、檔案路徑

#### Scenario: 傳入未格式化的原始文字
- **WHEN** 外層 AI Agent 呼叫 `generate_md2ppt(markdown_content="公司產品介紹")`
- **AND** `markdown_content` 不以 `---` 開頭
- **THEN** 工具回傳錯誤訊息，說明必須傳入已格式化的 MD2PPT markdown
- **AND** 錯誤訊息 SHALL 包含格式提示，引導 AI Agent 重新產生

#### Scenario: 工具不呼叫內部 AI
- **WHEN** 工具執行過程中
- **THEN** SHALL NOT 呼叫 `call_claude()` 或其他 AI 模型
- **AND** SHALL NOT 產生巢狀 Claude CLI 行程

---

### Requirement: Generate Document Tool
系統 SHALL 提供 `generate_md2doc` MCP Tool，接收已格式化的 MD2DOC markdown 內容，執行格式修正後儲存並建立分享連結。

工具 SHALL NOT 在內部呼叫 Claude 或任何 AI 模型。格式化內容的產生責任由外層 AI Agent 承擔。

工具參數：
- `markdown_content`（str，必填）：已格式化的 MD2DOC markdown，MUST 以 `---` 開頭（frontmatter）
- `ctos_user_id`（int，選填）：CTOS 用戶 ID

工具 SHALL 移除原有的 `content` 參數。

#### Scenario: 接收合法的 MD2DOC markdown 並建立分享連結
- **WHEN** 外層 AI Agent 呼叫 `generate_md2doc(markdown_content="---\ntitle: ...\n---\n...")` 並傳入以 `---` 開頭的格式化 markdown
- **THEN** 工具執行 `fix_md2doc_format()` 自動修正格式問題
- **AND** 儲存檔案至 NAS `ai-generated/` 目錄
- **AND** 建立 24 小時有效的帶密碼分享連結
- **AND** 回傳分享連結 URL、存取密碼、檔案路徑

#### Scenario: 傳入未格式化的原始文字
- **WHEN** 外層 AI Agent 呼叫 `generate_md2doc(markdown_content="產品使用手冊")`
- **AND** `markdown_content` 不以 `---` 開頭
- **THEN** 工具回傳錯誤訊息，說明必須傳入已格式化的 MD2DOC markdown
- **AND** 錯誤訊息 SHALL 包含格式提示，引導 AI Agent 重新產生

#### Scenario: 工具不呼叫內部 AI
- **WHEN** 工具執行過程中
- **THEN** SHALL NOT 呼叫 `call_claude()` 或其他 AI 模型
- **AND** SHALL NOT 產生巢狀 Claude CLI 行程

---

## ADDED Requirements

### Requirement: AI Agent 格式規範載入
系統 SHALL 在 SKILL.md（`skills/ai-assistant/SKILL.md`）中提供精簡版 MD2PPT 和 MD2DOC 格式規範，讓外層 AI Agent 自行產生符合格式的 markdown 內容。

格式規範 SHALL 同步維護在 `agents.py` 的 `AI_DOCUMENT_TOOLS_PROMPT` 中作為 fallback。

#### Scenario: SKILL.md 載入格式規範
- **WHEN** 用戶具備 `ai-assistant` 權限
- **AND** SkillManager 載入 SKILL.md
- **THEN** 外層 AI Agent 獲得 MD2PPT 和 MD2DOC 格式規範
- **AND** Agent 能自行產生符合 `---` frontmatter 格式的 markdown 內容

#### Scenario: Fallback prompt 提供格式規範
- **WHEN** SKILL.md 未載入（無 SkillManager 或權限不足）
- **AND** 使用 `AI_DOCUMENT_TOOLS_PROMPT` fallback
- **THEN** fallback prompt SHALL 包含與 SKILL.md 相同的格式規範

#### Scenario: 格式規範精簡度
- **WHEN** 格式規範載入至外層 AI Agent
- **THEN** MD2PPT 格式規範 SHALL 控制在約 60 行以內
- **AND** MD2DOC 格式規範 SHALL 控制在約 40 行以內
- **AND** 規範 SHALL 包含：格式結構規則、配色建議、設計原則、一個緊湊範例

### Requirement: LineBot Prompt 工具描述更新
`linebot_agents.py` 中的 `LINEBOT_PERSONAL_PROMPT` 和 `LINEBOT_GROUP_PROMPT` SHALL 更新 `generate_md2ppt` 和 `generate_md2doc` 的工具描述，反映新的參數名稱和使用方式。

#### Scenario: Personal prompt 工具描述
- **WHEN** LineBot AI 載入個人對話 prompt
- **THEN** `generate_md2ppt` 工具描述 SHALL 說明需傳入 `markdown_content`（已格式化的 MD2PPT markdown）
- **AND** SHALL 說明需先產生格式化內容再呼叫工具

#### Scenario: Group prompt 工具描述
- **WHEN** LineBot AI 載入群組對話 prompt
- **THEN** `generate_md2ppt` 和 `generate_md2doc` 工具描述 SHALL 與 personal prompt 一致
