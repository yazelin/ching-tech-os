## ADDED Requirements

### Requirement: 記憶管理 MCP 工具
MCP Server SHALL 提供記憶管理工具，讓 AI 可以在對話中管理記憶。

#### Scenario: add_memory 新增記憶
- **WHEN** AI 呼叫 `add_memory` 工具
- **AND** 提供 content 參數
- **AND** 提供 line_group_id（群組對話）或 line_user_id（個人對話）
- **THEN** 系統建立新的記憶
- **AND** 若未提供 title，系統自動產生合適的標題（取 content 前 20 字或由 AI 判斷）
- **AND** 回傳成功訊息和記憶 ID

#### Scenario: get_memories 查詢記憶
- **WHEN** AI 呼叫 `get_memories` 工具
- **AND** 提供 line_group_id 或 line_user_id
- **THEN** 系統回傳該群組或用戶的所有記憶列表
- **AND** 每筆記憶包含 id、title、content、is_active

#### Scenario: update_memory 更新記憶
- **WHEN** AI 呼叫 `update_memory` 工具
- **AND** 提供 memory_id 參數
- **AND** 提供要更新的欄位（title、content、is_active）
- **THEN** 系統更新該記憶
- **AND** 回傳成功訊息

#### Scenario: delete_memory 刪除記憶
- **WHEN** AI 呼叫 `delete_memory` 工具
- **AND** 提供 memory_id 參數
- **THEN** 系統刪除該記憶
- **AND** 回傳成功訊息

#### Scenario: 記憶不存在
- **WHEN** AI 呼叫 update_memory 或 delete_memory
- **AND** 指定的 memory_id 不存在
- **THEN** 系統回傳錯誤訊息「找不到指定的記憶」

---

### Requirement: 記憶管理 Prompt 說明
Line Bot Agent Prompt SHALL 包含記憶管理工具的使用說明。

#### Scenario: linebot-personal prompt 記憶說明
- **WHEN** 系統組合 linebot-personal Agent 的 prompt
- **THEN** prompt 包含記憶管理工具說明
- **AND** 說明 AI 應如何判斷新增、修改或刪除記憶
- **AND** 說明 AI 應自動產生合適的標題

#### Scenario: linebot-group prompt 記憶說明
- **WHEN** 系統組合 linebot-group Agent 的 prompt
- **THEN** prompt 包含記憶管理工具說明
- **AND** 說明群組記憶適用於該群組的所有對話

#### Scenario: 用戶要求記住某事
- **WHEN** 用戶說「記住 XXX」或「以後 XXX」
- **THEN** AI 應呼叫 add_memory 工具
- **AND** AI 自動產生合適的標題

#### Scenario: 用戶要求修改記憶
- **WHEN** 用戶說「修改記憶 XXX」或「把 XXX 改成 YYY」
- **THEN** AI 應先呼叫 get_memories 查詢現有記憶
- **AND** 找到相關記憶後呼叫 update_memory 更新

#### Scenario: 用戶要求刪除記憶
- **WHEN** 用戶說「忘記 XXX」或「不要再 XXX」
- **THEN** AI 應判斷是否要刪除相關記憶
- **AND** 若需要刪除，先用 get_memories 查詢再呼叫 delete_memory

#### Scenario: 用戶要求列出記憶
- **WHEN** 用戶說「列出記憶」或「我設定了什麼」
- **THEN** AI 應呼叫 get_memories 查詢並列出結果
