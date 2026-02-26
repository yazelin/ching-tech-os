"""內建指令 handler

註冊所有內建的斜線指令到 CommandRouter。
"""

from __future__ import annotations

import logging
import time

from .commands import CommandContext, SlashCommand, router
from ..bot_line.trigger import reset_conversation

logger = logging.getLogger(__name__)


async def _handle_reset(ctx: CommandContext) -> str | None:
    """重置對話歷史"""
    if ctx.is_group:
        return None  # 群組靜默忽略

    await reset_conversation(ctx.platform_user_id)
    return "已清除對話歷史，開始新對話！有什麼可以幫你的嗎？"


async def _handle_debug(ctx: CommandContext) -> str | None:
    """管理員系統診斷指令

    使用 bot-debug Agent 和 debug-skill 腳本分析系統狀態。
    """
    from .. import ai_manager
    from ..claude_agent import call_claude
    from ..bot.ai import parse_ai_response
    from ...config import settings

    # 取得 bot-debug Agent
    agent = await ai_manager.get_agent_by_name("bot-debug")
    if not agent:
        return "⚠️ bot-debug Agent 不存在，請確認系統已正確初始化。"

    # 取得 system prompt
    system_prompt_data = agent.get("system_prompt")
    if isinstance(system_prompt_data, dict):
        system_prompt = system_prompt_data.get("content", "")
    else:
        system_prompt = ""

    if not system_prompt:
        return "⚠️ bot-debug Agent 缺少 system_prompt 設定。"

    # 取得 Agent 定義的工具
    agent_tools = agent.get("tools") or ["run_skill_script"]

    # 準備 prompt（使用者的問題描述，或預設「分析系統目前狀態」）
    user_problem = ctx.raw_args.strip() if ctx.raw_args else ""
    if user_problem:
        prompt = f"管理員問題：{user_problem}"
    else:
        prompt = "請執行系統綜合健康檢查（check-system-health），分析目前系統狀態並回報結果。"

    # 呼叫 Claude CLI
    model = settings.bot_debug_model
    start_time = time.time()

    try:
        response = await call_claude(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            timeout=180,  # 3 分鐘（診斷腳本可能需要時間）
            tools=agent_tools,
            ctos_user_id=ctx.ctos_user_id,
        )
    except Exception:
        logger.exception("Debug 指令 AI 呼叫失敗")
        return "⚠️ 診斷執行失敗，請查看系統日誌。"

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(f"/debug 診斷完成，耗時 {duration_ms}ms")

    # 解析回應
    reply_text, _files = parse_ai_response(response.message)

    if not reply_text:
        return "診斷完成，但未產生回報內容。"

    # 過濾 FILE_MESSAGE（debug 不需要檔案傳送）
    import re
    reply_text = re.sub(r"\[FILE_MESSAGE:[^\]]+\]", "", reply_text).strip()

    return reply_text or "診斷完成，但未產生回報內容。"


def register_builtin_commands() -> None:
    """註冊所有內建指令"""

    # /reset 指令（包含所有別名）
    router.register(
        SlashCommand(
            name="reset",
            aliases=["新對話", "新对话", "清除對話", "清除对话", "忘記", "忘记"],
            handler=_handle_reset,
            require_bound=False,  # 受限模式用戶也可以重置
            require_admin=False,
            private_only=True,
        )
    )

    # /debug 指令（管理員專用，僅限個人對話）
    router.register(
        SlashCommand(
            name="debug",
            aliases=["診斷", "diag"],
            handler=_handle_debug,
            require_bound=True,
            require_admin=True,
            private_only=True,
        )
    )

    logger.info(f"已註冊 {len({id(v) for v in router._commands.values()})} 個內建指令")
