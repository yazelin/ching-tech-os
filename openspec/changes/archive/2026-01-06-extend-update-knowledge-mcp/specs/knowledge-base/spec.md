## MODIFIED Requirements

### Requirement: MCP 工具更新知識標籤
知識庫 MCP 服務 SHALL 提供 `update_knowledge_item` 工具支援完整的知識標籤更新。

#### Scenario: 更新知識的專案關聯
- **WHEN** AI 呼叫 `update_knowledge_item` 工具
- **AND** 提供 `projects` 參數（專案名稱列表）
- **THEN** 系統更新該知識的 tags.projects 欄位
- **AND** 知識關聯到指定的專案

#### Scenario: 更新知識的適用角色
- **WHEN** AI 呼叫 `update_knowledge_item` 工具
- **AND** 提供 `roles` 參數（角色名稱列表）
- **THEN** 系統更新該知識的 tags.roles 欄位

#### Scenario: 更新知識的難度層級
- **WHEN** AI 呼叫 `update_knowledge_item` 工具
- **AND** 提供 `level` 參數（如 beginner、intermediate、advanced）
- **THEN** 系統更新該知識的 tags.level 欄位

#### Scenario: 更新知識的類型
- **WHEN** AI 呼叫 `update_knowledge_item` 工具
- **AND** 提供 `type` 參數（如 note、spec、guide）
- **THEN** 系統更新該知識的 type 欄位

#### Scenario: 同時更新多個標籤欄位
- **WHEN** AI 呼叫 `update_knowledge_item` 工具
- **AND** 同時提供 `projects`、`roles`、`level`、`topics` 參數
- **THEN** 系統一次更新所有指定的標籤欄位
- **AND** 未提供的欄位保持原值

---
