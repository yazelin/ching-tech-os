"""內建指令 handler

註冊所有內建的斜線指令到 CommandRouter。
"""

from __future__ import annotations

import logging
import re
import time

from .commands import CommandContext, SlashCommand, router
from ..bot_line.trigger import reset_conversation

logger = logging.getLogger(__name__)


DEFAULT_WELCOME_MESSAGE = (
    "歡迎使用 CTOS Bot！\n\n"
    "我是 Ching Tech OS 的 AI 助手，可以幫你：\n"
    "• 回答問題和對話\n"
    "• 管理專案和筆記\n"
    "• 生成和編輯圖片\n\n"
    "首次使用請先綁定帳號：\n"
    "1. 登入 CTOS 系統\n"
    "2. 進入 Bot 管理頁面\n"
    "3. 點擊「綁定帳號」產生驗證碼\n"
    "4. 將 6 位數驗證碼發送給我\n\n"
    "輸入 /help 查看更多功能"
)


async def get_welcome_message() -> str:
    """回傳歡迎訊息文字（/start 和 LINE FollowEvent 共用）

    優先從 bot-restricted Agent 的 settings.welcome_message 讀取，
    未設定時 fallback 到預設歡迎訊息。
    """
    try:
        from .. import ai_manager

        agent = await ai_manager.get_agent_by_name("bot-restricted")
        if agent:
            agent_settings = agent.get("settings") or {}
            custom = agent_settings.get("welcome_message")
            if custom:
                return custom
    except Exception:
        logger.debug("讀取 agent settings 失敗，使用預設歡迎訊息", exc_info=True)

    return DEFAULT_WELCOME_MESSAGE


async def _handle_start(ctx: CommandContext) -> str | None:
    """歡迎訊息"""
    return await get_welcome_message()


async def _handle_help(ctx: CommandContext) -> str | None:
    """動態列出所有已註冊的指令"""
    # 收集不重複的指令（alias 會指向同一個 SlashCommand）
    seen_ids: set[int] = set()
    commands: list[SlashCommand] = []
    for cmd in router._commands.values():
        cmd_id = id(cmd)
        if cmd_id in seen_ids:
            continue
        seen_ids.add(cmd_id)
        # 過濾：未啟用、不支援當前平台
        if not cmd.enabled or ctx.platform_type not in cmd.platforms:
            continue
        # 非管理員看不到管理員指令
        if cmd.require_admin and not ctx.is_admin:
            continue
        commands.append(cmd)

    lines = [
        "CTOS Bot 使用說明\n",
        "直接傳送文字即可與 AI 對話",
        "在群組中 @Bot 或回覆 Bot 訊息即可觸發\n",
        "指令列表",
    ]

    for cmd in commands:
        desc = cmd.description or cmd.name
        # 顯示主要別名（最多 1 個）
        alias_hint = ""
        if cmd.aliases:
            alias_hint = f"（/{cmd.aliases[0]}）"
        # 標註管理員指令
        admin_tag = "（管理員）" if cmd.require_admin else ""
        lines.append(f"/{cmd.name} — {desc}{alias_hint}{admin_tag}")

    lines.append("")
    lines.append("帳號綁定")
    lines.append("發送 6 位數驗證碼完成綁定")

    return "\n".join(lines)


async def _handle_reset(ctx: CommandContext) -> str | None:
    """重置對話歷史"""
    # 群組檢查已由 CommandRouter.dispatch() 的 private_only 處理
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
    logger.info(f"/debug ctos_user_id={ctx.ctos_user_id}, is_admin={ctx.is_admin}, bot_user_id={ctx.bot_user_id}")
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

    # 記錄 AI Log
    try:
        from ..linebot_ai import log_linebot_ai_call

        await log_linebot_ai_call(
            message_uuid=None,
            line_group_id=None,
            is_group=False,
            input_prompt=prompt,
            history=None,
            system_prompt=system_prompt,
            allowed_tools=agent_tools,
            model=model,
            response=response,
            duration_ms=duration_ms,
            context_type_override="bot-debug",
        )
    except Exception:
        logger.warning("記錄 /debug AI Log 失敗", exc_info=True)

    # 解析回應
    reply_text, _files = parse_ai_response(response.message)

    if not reply_text:
        return "診斷完成，但未產生回報內容。"

    # 過濾 FILE_MESSAGE（debug 不需要檔案傳送）
    reply_text = re.sub(r"\[FILE_MESSAGE:[^\]]+\]", "", reply_text).strip()

    return reply_text or "診斷完成，但未產生回報內容。"


async def _handle_agent(ctx: CommandContext) -> str | None:
    """切換對話使用的 AI Agent

    用法：
    /agent          — 顯示目前使用的 Agent 和可切換清單
    /agent <name>   — 用名稱切換
    /agent <number> — 用編號切換
    /agent reset    — 恢復預設
    """
    from .. import ai_manager
    from ..linebot_agents import (
        get_group_active_agent_id,
        get_user_active_agent_id,
        set_group_active_agent,
        set_user_active_agent,
    )

    args = ctx.raw_args.strip()

    # 取得可切換的 Agent 清單（按 name 排序）
    selectable = await ai_manager.get_selectable_agents()

    async def _apply_preference(agent_id: str | None) -> None:
        """將 Agent 偏好寫入群組或個人"""
        if ctx.is_group and ctx.group_id:
            await set_group_active_agent(ctx.group_id, agent_id)
        elif ctx.bot_user_id:
            await set_user_active_agent(ctx.bot_user_id, agent_id)

    # === /agent reset ===
    if args.lower() == "reset":
        await _apply_preference(None)
        return "已恢復預設 Agent"

    # === 查詢目前 Agent ===
    current_agent_id = None
    if ctx.is_group and ctx.group_id:
        current_agent_id = await get_group_active_agent_id(ctx.group_id)
    elif ctx.bot_user_id:
        current_agent_id = await get_user_active_agent_id(ctx.bot_user_id)

    # 取得目前 Agent 的顯示資訊
    current_label = "預設"
    if current_agent_id:
        from uuid import UUID
        current_agent = await ai_manager.get_agent(UUID(current_agent_id))
        if current_agent:
            current_label = f"{current_agent['name']}（{current_agent.get('display_name', '')}）"
        else:
            current_label = "預設（偏好 Agent 已不存在）"

    # === /agent（無參數）— 顯示狀態和清單 ===
    if not args:
        lines = [f"目前 Agent：{current_label}"]
        if selectable:
            lines.append("")
            lines.append("可切換的 Agent：")
            for i, agent in enumerate(selectable, 1):
                display = agent.get("display_name") or agent["name"]
                lines.append(f"{i}. {agent['name']} — {display}")
            lines.append("")
            lines.append("用法：/agent <名稱或編號>")
            lines.append("恢復預設：/agent reset")
        else:
            lines.append("目前沒有可切換的 Agent")
            lines.append("請在 AI 管理介面將 Agent 的 settings.user_selectable 設為 true")
        return "\n".join(lines)

    # === /agent <number> — 編號切換 ===
    if args.isdigit():
        idx = int(args)
        if idx < 1 or idx > len(selectable):
            return f"編號 {idx} 超出範圍（1-{len(selectable)}），請用 /agent 查看可用清單"
        target = selectable[idx - 1]
    else:
        # === /agent <name> — 名稱切換 ===
        target = next((a for a in selectable if a["name"] == args), None)
        if not target:
            # 檢查 Agent 是否存在但不可選
            existing = await ai_manager.get_agent_by_name(args)
            if existing:
                return f"Agent {args} 不可切換，請用 /agent 查看可用清單"
            return f"找不到 Agent: {args}，請用 /agent 查看可用清單"

    await _apply_preference(str(target["id"]))
    display = target.get("display_name") or target["name"]
    return f"已切換到 {display}"


_registered = False


def register_builtin_commands() -> None:
    """註冊所有內建指令（冪等，重複呼叫不會重複註冊）"""
    global _registered
    if _registered:
        return
    _registered = True

    from ...config import settings

    disabled = set(settings.bot_cmd_disabled)

    all_commands = [
        SlashCommand(
            name="start",
            handler=_handle_start,
            description="歡迎訊息",
            require_bound=False,
            require_admin=False,
            private_only=True,
        ),
        SlashCommand(
            name="help",
            aliases=["說明"],
            handler=_handle_help,
            description="查看指令說明",
            require_bound=False,
            require_admin=False,
            private_only=True,
        ),
        SlashCommand(
            name="reset",
            aliases=["新對話", "新对话", "清除對話", "清除对话", "忘記", "忘记"],
            handler=_handle_reset,
            description="重置對話歷史",
            require_bound=False,
            require_admin=False,
            private_only=True,
        ),
        SlashCommand(
            name="debug",
            aliases=["診斷", "diag"],
            handler=_handle_debug,
            description="系統診斷",
            require_bound=True,
            require_admin=True,
            private_only=True,
        ),
        SlashCommand(
            name="agent",
            aliases=["切換助理"],
            handler=_handle_agent,
            description="切換 AI Agent",
            require_bound=True,
            require_admin=True,
            private_only=False,
        ),
    ]

    for cmd in all_commands:
        if cmd.name in disabled:
            cmd.enabled = False
        router.register(cmd)

    enabled_count = sum(1 for cmd in all_commands if cmd.enabled)
    logger.info(f"已註冊 {len(all_commands)} 個內建指令（{enabled_count} 個啟用）")
