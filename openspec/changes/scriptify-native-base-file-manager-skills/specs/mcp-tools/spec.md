## MODIFIED Requirements

### Requirement: Skills SKILL.md 完整工具定義
每個 skill 的 `SKILL.md` frontmatter `allowed-tools` SHALL 包含該 skill 所需的全部工具名稱，作為工具白名單來源。

#### Scenario: inventory skill 包含完整 ERPNext 工具
- **WHEN** 載入 inventory skill
- **THEN** tools 列表 SHALL 包含所有庫存相關的 ERPNext 工具
- **AND** 包含 `mcp__erpnext__get_item_price`、`mcp__erpnext__make_mapped_doc`、`mcp__erpnext__get_party_balance` 等庫存相關工具

#### Scenario: project skill 包含完整 ERPNext 工具
- **WHEN** 載入 project skill
- **THEN** tools 列表 SHALL 包含所有專案管理相關的 ERPNext 工具
- **AND** 包含 `mcp__erpnext__delete_document`、`mcp__erpnext__submit_document`、`mcp__erpnext__cancel_document`、`mcp__erpnext__run_report` 等完整操作工具

#### Scenario: printer skill 包含 print_test_page
- **WHEN** 載入 printer skill
- **THEN** tools 列表 SHALL 包含 `mcp__printer__print_test_page`

#### Scenario: base skill 改為 script 入口
- **WHEN** 載入 base skill
- **THEN** tools 列表 SHALL 包含 `mcp__ching-tech-os__run_skill_script`
- **AND** base 主要能力 SHALL 透過 skill scripts 執行

#### Scenario: file-manager skill 改為 script 入口
- **WHEN** 載入 file-manager skill
- **THEN** tools 列表 SHALL 包含 `mcp__ching-tech-os__run_skill_script`
- **AND** 檔案搜尋/資訊/訊息準備等能力 SHALL 透過 skill scripts 執行

#### Scenario: ai_assistant skill 包含 restore_image
- **WHEN** 載入 ai_assistant skill
- **THEN** tools 列表 SHALL 包含 `mcp__nanobanana__restore_image`（圖片修復功能）
