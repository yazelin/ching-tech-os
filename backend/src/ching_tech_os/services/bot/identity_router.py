"""Bot 身份分流路由器

根據 BOT_UNBOUND_USER_POLICY 設定，決定未綁定用戶的處理路徑：
- reject（預設）：回覆綁定提示，不進行 AI 處理
- restricted：路由到受限模式 AI 流程
"""

from __future__ import annotations

import logging
import time
from uuid import UUID

from ...config import settings

logger = logging.getLogger(__name__)

# 各平台的綁定提示訊息
BINDING_PROMPT_LINE = (
    "請先在 CTOS 系統綁定您的 Line 帳號才能使用此服務。\n\n"
    "步驟：\n"
    "1. 登入 CTOS 系統\n"
    "2. 進入 Line Bot 管理頁面\n"
    "3. 點擊「綁定 Line 帳號」產生驗證碼\n"
    "4. 將驗證碼發送給我完成綁定"
)

BINDING_PROMPT_TELEGRAM = (
    "請先在 CTOS 系統綁定您的 Telegram 帳號才能使用此服務。\n\n"
    "步驟：\n"
    "1. 登入 CTOS 系統\n"
    "2. 進入 Bot 管理頁面\n"
    "3. 點擊「綁定帳號」產生驗證碼\n"
    "4. 將 6 位數驗證碼發送給我完成綁定"
)


def get_unbound_policy() -> str:
    """取得未綁定用戶策略

    Returns:
        "reject" 或 "restricted"
    """
    policy = settings.bot_unbound_user_policy.lower().strip()
    if policy not in ("reject", "restricted"):
        logger.warning(
            "BOT_UNBOUND_USER_POLICY 值無效: %r，使用預設 'reject'", policy
        )
        return "reject"
    return policy


class UnboundRouteResult:
    """身份分流結果"""

    __slots__ = ("action", "reply_text")

    def __init__(self, action: str, reply_text: str | None = None):
        """
        Args:
            action: "reject"（拒絕並回覆提示）| "restricted"（進入受限模式）| "silent"（靜默忽略）
            reply_text: 拒絕時的回覆文字（action="reject" 時有值）
        """
        self.action = action
        self.reply_text = reply_text


def route_unbound(
    *,
    platform_type: str,
    is_group: bool,
) -> UnboundRouteResult:
    """根據策略決定未綁定用戶的處理路徑

    Args:
        platform_type: "line" | "telegram"
        is_group: 是否為群組對話

    Returns:
        UnboundRouteResult 指示應採取的動作
    """
    # 群組中的未綁定用戶一律靜默忽略（不受策略影響）
    if is_group:
        return UnboundRouteResult(action="silent")

    policy = get_unbound_policy()

    if policy == "restricted":
        return UnboundRouteResult(action="restricted")

    # reject 策略：回覆綁定提示
    if platform_type == "telegram":
        return UnboundRouteResult(action="reject", reply_text=BINDING_PROMPT_TELEGRAM)
    return UnboundRouteResult(action="reject", reply_text=BINDING_PROMPT_LINE)


async def handle_restricted_mode(
    *,
    content: str,
    platform_user_id: str,
    bot_user_id: str | None,
    is_group: bool,
    line_group_id: UUID | None = None,
    message_uuid: UUID | None = None,
    user_display_name: str | None = None,
) -> str | None:
    """執行受限模式 AI 流程

    使用 bot-restricted Agent、受限工具白名單、縮短的對話歷史。

    Args:
        content: 使用者訊息內容
        platform_user_id: 平台用戶 ID（Line user ID 或 Telegram user ID）
        bot_user_id: bot_users.id (UUID 字串)
        is_group: 是否為群組對話
        line_group_id: 群組 UUID（用於取得對話歷史）
        message_uuid: 訊息 UUID（用於 AI log）
        user_display_name: 使用者顯示名稱

    Returns:
        AI 回應文字，或 None
    """
    from .. import ai_manager
    from ..claude_agent import call_claude
    from ..linebot_ai import (
        build_system_prompt,
        get_conversation_context,
        log_linebot_ai_call,
    )
    from ..mcp import get_mcp_tool_names
    from ..linebot_agents import (
        get_mcp_servers_for_user,
        get_tools_for_user,
        get_tool_routing_for_user,
    )
    from ..bot.ai import parse_ai_response

    # 1. 取得 bot-restricted Agent
    agent = await ai_manager.get_agent_by_name("bot-restricted")
    if not agent:
        logger.error("bot-restricted Agent 不存在，無法進行受限模式 AI 處理")
        return "系統設定錯誤，請聯繫管理員。"

    # 2. 取得 model（優先使用環境變數設定）
    model = settings.bot_restricted_model

    # 3. 取得 system prompt
    system_prompt_data = agent.get("system_prompt")
    if isinstance(system_prompt_data, dict):
        base_prompt = system_prompt_data.get("content", "")
    else:
        base_prompt = ""

    if not base_prompt:
        logger.error("bot-restricted Agent 缺少 system_prompt")
        return "系統設定錯誤，請聯繫管理員。"

    # 加入對話識別（標記為未綁定用戶）
    base_prompt += (
        f"\n\n【對話識別】\n"
        f"平台用戶 ID: {platform_user_id}\n"
        f"用戶身份: 未綁定用戶（受限模式）\n"
        f"ctos_user_id: （未關聯）"
    )

    # 4. 取得 Agent 定義的工具白名單
    agent_tools = agent.get("tools") or []

    # 受限模式不使用使用者權限，使用空權限（僅 Agent 定義的工具）
    app_permissions: dict[str, bool] = {}

    # 組裝 system prompt（加入工具說明）
    system_prompt = await build_system_prompt(
        line_group_id,
        platform_user_id if not is_group else None,
        base_prompt,
        agent_tools,
        app_permissions,
    )

    # 5. 取得對話歷史（限制 10 條，較已綁定用戶的 20 條縮短）
    history, images, files = await get_conversation_context(
        line_group_id,
        platform_user_id if not is_group else None,
        limit=10,
        exclude_message_id=message_uuid,
    )

    # 6. 準備用戶訊息
    if user_display_name:
        user_message = f"user[{user_display_name}]: {content}"
    else:
        user_message = f"user: {content}"

    # 7. 組裝工具列表（僅 Agent 定義的工具 + 對應的 MCP 工具）
    # 受限模式的 MCP 工具也受 Agent 設定限制
    mcp_tools = await get_mcp_tool_names(exclude_group_only=not is_group)
    # 只保留 Agent 工具白名單中的 MCP 工具
    if agent_tools:
        mcp_tool_set = set(mcp_tools)
        allowed_mcp = [t for t in agent_tools if t in mcp_tool_set]
        # Agent 工具中不在 MCP 列表中的可能是外部 skill
        non_mcp_tools = [t for t in agent_tools if t not in mcp_tool_set]
        all_tools = list(dict.fromkeys(allowed_mcp + non_mcp_tools))
    else:
        all_tools = []

    # 取得需要的 MCP server（按需載入）
    required_mcp_servers = set()
    if all_tools:
        # 受限模式使用空權限取得 MCP servers
        required_mcp_servers = await get_mcp_servers_for_user(app_permissions)

    # 8. 呼叫 Claude CLI
    start_time = time.time()

    response = await call_claude(
        prompt=user_message,
        model=model,
        history=history,
        system_prompt=system_prompt,
        timeout=120,  # 受限模式超時較短（2 分鐘）
        tools=all_tools,
        required_mcp_servers=required_mcp_servers,
        ctos_user_id=None,  # 未綁定用戶
    )

    duration_ms = int((time.time() - start_time) * 1000)

    # 9. 記錄 AI Log
    if message_uuid:
        await log_linebot_ai_call(
            message_uuid=message_uuid,
            line_group_id=line_group_id,
            is_group=is_group,
            input_prompt=user_message,
            history=history,
            system_prompt=system_prompt,
            allowed_tools=all_tools,
            model=model,
            response=response,
            duration_ms=duration_ms,
        )

    # 10. 解析回應（受限模式僅支援文字，不處理 FILE_MESSAGE）
    result = parse_ai_response(response)
    reply_text = result.get("text", "")

    if not reply_text:
        return "抱歉，我目前無法回答您的問題。"

    # 過濾 FILE_MESSAGE 標記（受限模式不支援檔案發送）
    import re
    reply_text = re.sub(r"\[FILE_MESSAGE:[^\]]+\]", "", reply_text).strip()

    return reply_text or "抱歉，我目前無法回答您的問題。"
