## MODIFIED Requirements

### Requirement: MCP 工具查詢知識庫附件
知識庫 MCP 服務 SHALL 在 `get_knowledge_item` 中顯示附件資訊。

#### Scenario: 查詢知識時顯示附件列表
- **WHEN** AI 呼叫 `get_knowledge_item` 工具
- **AND** 該知識包含附件
- **THEN** 返回內容包含附件列表
- **AND** 每個附件顯示索引、類型、檔名、描述

#### Scenario: 無附件時不顯示附件區塊
- **WHEN** AI 呼叫 `get_knowledge_item` 工具
- **AND** 該知識沒有附件
- **THEN** 返回內容不包含附件區塊

---

## ADDED Requirements

### Requirement: MCP 工具取得附件列表
知識庫 MCP 服務 SHALL 提供 `get_knowledge_attachments` 工具，專門查詢附件。

#### Scenario: 取得附件列表
- **WHEN** AI 呼叫 `get_knowledge_attachments` 工具
- **AND** 提供 `kb_id` 參數
- **THEN** 返回該知識的所有附件資訊
- **AND** 包含索引（從 0 開始）、類型、檔名、大小、描述

#### Scenario: 知識不存在
- **WHEN** AI 呼叫 `get_knowledge_attachments` 工具
- **AND** 提供的 `kb_id` 不存在
- **THEN** 返回錯誤訊息「找不到知識 {kb_id}」

#### Scenario: 無附件
- **WHEN** AI 呼叫 `get_knowledge_attachments` 工具
- **AND** 該知識沒有附件
- **THEN** 返回訊息「該知識沒有附件」

---

### Requirement: MCP 工具更新附件描述
知識庫 MCP 服務 SHALL 提供 `update_knowledge_attachment` 工具，更新附件的描述。

#### Scenario: 更新附件描述
- **WHEN** AI 呼叫 `update_knowledge_attachment` 工具
- **AND** 提供 `kb_id`、`attachment_index`、`description` 參數
- **THEN** 系統更新該附件的 description 欄位
- **AND** 返回成功訊息與更新後的附件資訊

#### Scenario: 附件索引超出範圍
- **WHEN** AI 呼叫 `update_knowledge_attachment` 工具
- **AND** 提供的 `attachment_index` 超出附件數量
- **THEN** 返回錯誤訊息「附件索引超出範圍」

#### Scenario: 批次標記附件描述
- **WHEN** 使用者要求 AI 根據知識內容標記附件
- **THEN** AI 可以：
  1. 用 `get_knowledge_item` 取得知識內容和附件列表
  2. 分析內容中的【圖1】【圖2】等描述
  3. 用 `update_knowledge_attachment` 為每個附件設定對應的描述

---
