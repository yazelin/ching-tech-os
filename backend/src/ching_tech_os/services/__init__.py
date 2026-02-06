"""服務層"""

from ching_tech_os.services.ai_chat import (
    get_available_agents,
    get_agent_system_prompt,
    get_agent_config,
)

from ching_tech_os.services.ai_manager import (
    # Prompt CRUD
    get_prompts,
    get_prompt,
    get_prompt_by_name,
    create_prompt,
    update_prompt,
    delete_prompt,
    get_prompt_referencing_agents,
    # Agent CRUD
    get_agents,
    get_agent,
    get_agent_by_name,
    create_agent,
    update_agent,
    delete_agent,
    # Log CRUD
    create_log,
    get_logs,
    get_log,
    get_log_stats,
    # AI 調用
    call_agent,
    test_agent,
    ensure_log_partitions,
)

from ching_tech_os.services.knowledge import (
    create_knowledge,
    delete_knowledge,
    get_all_tags,
    get_history,
    get_knowledge,
    get_nas_attachment,
    get_version,
    rebuild_index,
    search_knowledge,
    update_knowledge,
    upload_attachment,
    KnowledgeError,
    KnowledgeNotFoundError,
)

from ching_tech_os.services.mcp import (
    get_mcp_tools,
    get_mcp_tool_names,
    execute_tool,
    mcp,  # FastMCP 實例
)

from ching_tech_os.services.bot_line import (
    # Webhook
    verify_signature,
    get_webhook_parser,
    # 用戶/群組
    get_or_create_user,
    get_or_create_group,
    get_user_profile,
    get_group_profile,
    # 訊息
    save_message,
    mark_message_ai_processed,
    # 群組事件
    handle_join_event,
    handle_leave_event,
    # 回覆
    reply_text,
    # AI 觸發
    should_trigger_ai,
    # 查詢
    list_groups,
    list_messages,
    list_users,
    get_group_by_id,
    get_user_by_id,
    # 專案綁定
    bind_group_to_project,
    unbind_group_from_project,
)

from ching_tech_os.services.linebot_ai import (
    process_message_with_ai,
    handle_text_message,
)

__all__ = [
    # AI Chat - Agent 查詢
    "get_available_agents",
    "get_agent_system_prompt",
    "get_agent_config",
    # AI Manager - Prompt
    "get_prompts",
    "get_prompt",
    "get_prompt_by_name",
    "create_prompt",
    "update_prompt",
    "delete_prompt",
    "get_prompt_referencing_agents",
    # AI Manager - Agent
    "get_agents",
    "get_agent",
    "get_agent_by_name",
    "create_agent",
    "update_agent",
    "delete_agent",
    # AI Manager - Log
    "create_log",
    "get_logs",
    "get_log",
    "get_log_stats",
    # AI Manager - 調用
    "call_agent",
    "test_agent",
    "ensure_log_partitions",
    # Knowledge
    "create_knowledge",
    "delete_knowledge",
    "get_all_tags",
    "get_history",
    "get_knowledge",
    "get_nas_attachment",
    "get_version",
    "rebuild_index",
    "search_knowledge",
    "update_knowledge",
    "upload_attachment",
    "KnowledgeError",
    "KnowledgeNotFoundError",
    # MCP Server
    "get_mcp_tools",
    "get_mcp_tool_names",
    "execute_tool",
    "mcp",
    # Line Bot
    "verify_signature",
    "get_webhook_parser",
    "get_or_create_user",
    "get_or_create_group",
    "get_user_profile",
    "get_group_profile",
    "save_message",
    "mark_message_ai_processed",
    "handle_join_event",
    "handle_leave_event",
    "reply_text",
    "should_trigger_ai",
    "list_groups",
    "list_messages",
    "list_users",
    "get_group_by_id",
    "get_user_by_id",
    "bind_group_to_project",
    "unbind_group_from_project",
    # Line Bot AI
    "process_message_with_ai",
    "handle_text_message",
]
