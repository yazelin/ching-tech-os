---
name: base
description: 基礎工具（對話附件、分享連結，script-first）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    mcp_servers: ching-tech-os
    requires_app: null
    script_mcp_fallback:
      get_message_attachments: get_message_attachments
      summarize_chat: summarize_chat
      create_share_link: create_share_link
---

【基礎工具（script-first）】
- 優先使用 `run_skill_script` 呼叫下列 scripts：
  - `get_message_attachments`
  - `summarize_chat`
  - `create_share_link`
- `input` 必須是 JSON 物件字串。

【用法範例】
- `run_skill_script(skill="base", script="get_message_attachments", input="{\"days\":3}")`
- `run_skill_script(skill="base", script="summarize_chat", input="{\"hours\":24}")`
- `run_skill_script(skill="base", script="create_share_link", input="{\"resource_type\":\"knowledge\",\"resource_id\":\"kb-001\"}")`
