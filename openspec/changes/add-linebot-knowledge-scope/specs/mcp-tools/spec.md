## MODIFIED Requirements

### Requirement: add_note MCP 工具

知識庫 MCP 工具 `add_note` SHALL 支援對話脈絡參數，自動判斷知識來源。

#### Scenario: 工具參數

- **WHEN** 呼叫 add_note 工具
- **THEN** 工具接受以下參數：
  - title（必填）：筆記標題
  - content（必填）：筆記內容
  - category：分類（預設 note）
  - topics：主題標籤列表
  - project：關聯專案名稱
  - line_group_id：Line 群組 UUID（從對話識別取得）
  - line_user_id：Line 用戶 ID（從對話識別取得）
  - ctos_user_id：CTOS 用戶 ID（從對話識別取得）

#### Scenario: 個人聊天來源

- **WHEN** 提供 line_user_id 和 ctos_user_id
- **AND** 未提供 line_group_id
- **THEN** 知識的 scope 設為 personal
- **AND** 知識的 owner 設為該 CTOS 帳號

#### Scenario: 群組聊天來源（有綁定專案）

- **WHEN** 提供 line_group_id
- **AND** 該群組有綁定專案
- **THEN** 知識的 scope 設為 project
- **AND** 知識的 project_id 設為群組綁定的專案 ID

#### Scenario: 群組聊天來源（無綁定專案）

- **WHEN** 提供 line_group_id
- **AND** 該群組未綁定專案
- **THEN** 知識的 scope 設為 global

#### Scenario: 無對話脈絡

- **WHEN** 未提供 line_group_id 和 line_user_id
- **THEN** 知識的 scope 設為 global（維持原有行為）

---

### Requirement: add_note_with_attachments MCP 工具

知識庫 MCP 工具 `add_note_with_attachments` SHALL 支援對話脈絡參數，自動判斷知識來源。

#### Scenario: 工具參數

- **WHEN** 呼叫 add_note_with_attachments 工具
- **THEN** 工具接受以下參數：
  - title（必填）：筆記標題
  - content（必填）：筆記內容
  - attachments（必填）：附件的 NAS 路徑列表
  - category：分類（預設 note）
  - topics：主題標籤列表
  - project：關聯專案名稱
  - line_group_id：Line 群組 UUID（從對話識別取得）
  - line_user_id：Line 用戶 ID（從對話識別取得）
  - ctos_user_id：CTOS 用戶 ID（從對話識別取得）

#### Scenario: 來源判斷邏輯

- **WHEN** 呼叫 add_note_with_attachments 工具
- **THEN** 使用與 add_note 相同的來源判斷邏輯
- **AND** 根據對話脈絡設定知識的 scope 和關聯
