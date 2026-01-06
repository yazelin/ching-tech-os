# Proposal: add-attachment-management-mcp

## Summary
新增知識庫附件管理 MCP 工具，讓 AI 能夠查看和管理知識庫的附件，特別是能夠更新附件的描述（description）來標記「圖1」「圖2」等。

## Problem Statement
目前知識庫附件的檔名是自動產生的（如 `kb-002-595304079333786282.jpg`），AI 和使用者無法從檔名判斷哪個是「圖1」「圖2」。雖然附件的 YAML metadata 有 `description` 欄位，但：
1. `get_knowledge_item` MCP 工具不返回附件資訊
2. 沒有 MCP 工具可以更新附件的 description

## Proposed Solution

### 1. 擴展 `get_knowledge_item` 顯示附件列表
在返回內容時加入附件資訊，讓 AI 能看到有哪些附件及其描述。

### 2. 新增 `get_knowledge_attachments` MCP 工具
獨立工具專門查詢附件列表，返回格式化的附件資訊（索引、類型、檔名、描述）。

### 3. 新增 `update_knowledge_attachment` MCP 工具
讓 AI 能更新附件的 description，例如：
- 根據知識內容的【圖1】【圖2】描述，為附件加上對應的說明
- 使用者可以要求 AI：「把剛才的附件標記為圖1水切爐」

## Scope
- 修改：`mcp_server.py` 中的 `get_knowledge_item`
- 新增：`get_knowledge_attachments` MCP 工具
- 新增：`update_knowledge_attachment` MCP 工具
- 修改：`linebot_agents.py` 和 migration 中的 prompt

## Out of Scope
- 讓 AI 直接讀取 NAS 上的圖片內容（需要另外的設計）
- 附件重新命名（只更新 description，不改檔名）
