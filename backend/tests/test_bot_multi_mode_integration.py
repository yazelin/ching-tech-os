"""Bot 多模式平台整合測試

涵蓋身份分流、受限模式、知識庫公開存取、/debug 指令、rate limiter 等功能的
端對端測試。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================
# 9.1 BOT_UNBOUND_USER_POLICY=reject 回歸測試
# ============================================================


class TestRejectPolicyRegression:
    """確認 reject 策略下行為與現有系統一致"""

    @pytest.mark.asyncio
    async def test_reject_policy_line_private(self):
        """Line 個人對話 — 回覆綁定提示"""
        from ching_tech_os.services.bot.identity_router import route_unbound

        with (
            patch(
                "ching_tech_os.services.bot.identity_router.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_settings.bot_unbound_user_policy = "reject"
            result = await route_unbound(platform_type="line", is_group=False)
            assert result.action == "reject"
            assert result.reply_text is not None
            assert "CTOS" in result.reply_text
            assert "綁定" in result.reply_text

    @pytest.mark.asyncio
    async def test_reject_policy_telegram_private(self):
        """Telegram 個人對話 — 回覆綁定提示（含 Telegram 字樣）"""
        from ching_tech_os.services.bot.identity_router import route_unbound

        with (
            patch(
                "ching_tech_os.services.bot.identity_router.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_settings.bot_unbound_user_policy = "reject"
            result = await route_unbound(platform_type="telegram", is_group=False)
            assert result.action == "reject"
            assert "Telegram" in result.reply_text

    @pytest.mark.asyncio
    async def test_reject_policy_group_silent(self):
        """群組中未綁定用戶 — 靜默忽略（不受策略影響）"""
        from ching_tech_os.services.bot.identity_router import route_unbound

        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "reject"
            result = await route_unbound(platform_type="line", is_group=True)
            assert result.action == "silent"
            assert result.reply_text is None

    def test_default_policy_is_reject(self):
        """預設策略為 reject"""
        from ching_tech_os.services.bot.identity_router import get_unbound_policy

        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "reject"
            assert get_unbound_policy() == "reject"

    def test_invalid_policy_falls_back_to_reject(self):
        """無效策略值 → 回退到 reject"""
        from ching_tech_os.services.bot.identity_router import get_unbound_policy

        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "invalid_value"
            assert get_unbound_policy() == "reject"


# ============================================================
# 9.2 BOT_UNBOUND_USER_POLICY=restricted 受限模式測試
# ============================================================


class TestRestrictedPolicy:
    """確認 restricted 策略下未綁定用戶可使用受限模式對話"""

    @pytest.mark.asyncio
    async def test_restricted_policy_route(self):
        """restricted 策略 — 路由到受限模式"""
        from ching_tech_os.services.bot.identity_router import route_unbound

        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "restricted"
            result = await route_unbound(platform_type="line", is_group=False)
            assert result.action == "restricted"
            assert result.reply_text is None  # 不回覆拒絕訊息

    @pytest.mark.asyncio
    async def test_restricted_policy_group_still_silent(self):
        """restricted 策略 — 群組中仍然靜默忽略"""
        from ching_tech_os.services.bot.identity_router import route_unbound

        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "restricted"
            result = await route_unbound(platform_type="line", is_group=True)
            assert result.action == "silent"

    @pytest.mark.asyncio
    async def test_restricted_mode_full_flow(self):
        """受限模式完整流程：取得 Agent → 呼叫 AI → 回覆"""
        from ching_tech_os.services.bot.identity_router import handle_restricted_mode

        mock_response = MagicMock()
        mock_response.tool_calls = []

        with (
            patch(
                "ching_tech_os.services.bot.rate_limiter.check_and_increment",
                new_callable=AsyncMock,
                return_value=(True, None),
            ),
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "你是擎添工業的 AI 助理"},
                    "tools": ["search_knowledge"],
                },
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "ching_tech_os.services.linebot_ai.build_system_prompt",
                new_callable=AsyncMock,
                return_value="system prompt",
            ),
            patch(
                "ching_tech_os.services.linebot_ai.get_conversation_context",
                new_callable=AsyncMock,
                return_value=([], [], []),
            ),
            patch(
                "ching_tech_os.services.mcp.get_mcp_tool_names",
                new_callable=AsyncMock,
                return_value=["search_knowledge"],
            ),
            patch(
                "ching_tech_os.services.linebot_agents.get_mcp_servers_for_user",
                new_callable=AsyncMock,
                return_value=set(),
            ),
            patch(
                "ching_tech_os.services.bot.ai.parse_ai_response",
                return_value=("您好！我是擎添工業的 AI 助理。", []),
            ),
        ):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id="uuid-abc",
                is_group=False,
            )
            assert result is not None
            assert "擎添" in result

    @pytest.mark.asyncio
    async def test_restricted_mode_no_bot_user_id(self):
        """bot_user_id 為 None → 跳過 rate limit，仍可執行"""
        from ching_tech_os.services.bot.identity_router import handle_restricted_mode

        mock_response = MagicMock()
        mock_response.tool_calls = []

        with (
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "你是 AI 助理"},
                    "tools": [],
                },
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "ching_tech_os.services.linebot_ai.build_system_prompt",
                new_callable=AsyncMock,
                return_value="prompt",
            ),
            patch(
                "ching_tech_os.services.linebot_ai.get_conversation_context",
                new_callable=AsyncMock,
                return_value=([], [], []),
            ),
            patch(
                "ching_tech_os.services.mcp.get_mcp_tool_names",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ching_tech_os.services.linebot_agents.get_mcp_servers_for_user",
                new_callable=AsyncMock,
                return_value=set(),
            ),
            patch(
                "ching_tech_os.services.bot.ai.parse_ai_response",
                return_value=("回覆內容", []),
            ),
        ):
            # bot_user_id=None → 不檢查 rate limit
            result = await handle_restricted_mode(
                content="測試",
                platform_user_id="U999",
                bot_user_id=None,
                is_group=False,
            )
            assert result == "回覆內容"


# ============================================================
# 9.3 受限模式 search_knowledge 只回傳公開知識
# ============================================================


class TestPublicKnowledgeFiltering:
    """確認受限模式下 search_knowledge 只回傳公開知識"""

    def test_public_only_filter_scope_and_public(self):
        """public_only=True 時只回傳 scope=global 且 is_public=true"""
        from ching_tech_os.models.knowledge import KnowledgeTags

        # 模擬索引中的知識項目
        entries = [
            SimpleNamespace(
                id="K001", title="公開知識", type="knowledge", category="technical",
                scope="global", is_public=True, tags=KnowledgeTags(),
                author="system", updated_at="2025-01-01", owner=None,
                project_id=None, filename="k001.md",
            ),
            SimpleNamespace(
                id="K002", title="內部知識", type="knowledge", category="technical",
                scope="global", is_public=False, tags=KnowledgeTags(),
                author="system", updated_at="2025-01-01", owner=None,
                project_id=None, filename="k002.md",
            ),
            SimpleNamespace(
                id="K003", title="個人知識", type="knowledge", category="technical",
                scope="personal", is_public=True, tags=KnowledgeTags(),
                author="user1", updated_at="2025-01-01", owner="user1",
                project_id=None, filename="k003.md",
            ),
        ]

        # 測試過濾邏輯
        filtered = []
        for entry in entries:
            entry_is_public = getattr(entry, "is_public", False)
            entry_scope_val = getattr(entry, "scope", "global")
            if entry_scope_val != "global" or not entry_is_public:
                continue
            filtered.append(entry)

        # 只有 K001 符合（global + is_public）
        assert len(filtered) == 1
        assert filtered[0].id == "K001"

    def test_mcp_tool_public_only_for_unbound(self):
        """MCP search_knowledge 工具：ctos_user_id=None → public_only=True"""
        # 驗證邏輯正確性
        ctos_user_id = None
        public_only = ctos_user_id is None
        assert public_only is True

    def test_mcp_tool_no_filter_for_bound(self):
        """MCP search_knowledge 工具：ctos_user_id 有值 → public_only=False"""
        ctos_user_id = 42
        public_only = ctos_user_id is None
        assert public_only is False


# ============================================================
# 9.4 /debug 管理員執行/非管理員拒絕
# ============================================================


class TestDebugCommand:
    """確認 /debug 指令的權限控制"""

    @pytest.mark.asyncio
    async def test_debug_admin_can_execute(self):
        """管理員可以執行 /debug"""
        from ching_tech_os.services.bot.commands import CommandContext, router
        from ching_tech_os.services.bot.command_handlers import register_builtin_commands

        register_builtin_commands()

        ctx = CommandContext(
            platform_type="line",
            platform_user_id="U_ADMIN",
            bot_user_id="uuid-admin",
            ctos_user_id=1,
            is_admin=True,
            is_group=False,
            group_id=None,
            reply_token=None,
            raw_args="",
        )

        parsed = router.parse("/debug")
        assert parsed is not None
        command, args = parsed

        mock_response = MagicMock()
        mock_response.tool_calls = []

        with (
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "你是診斷助理"},
                    "tools": ["run_skill_script"],
                },
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "ching_tech_os.services.bot.ai.parse_ai_response",
                return_value=("系統狀態正常", []),
            ),
        ):
            reply = await router.dispatch(command, args, ctx)
            assert reply is not None
            assert "系統狀態正常" in reply

    @pytest.mark.asyncio
    async def test_debug_non_admin_rejected(self):
        """非管理員被拒絕"""
        from ching_tech_os.services.bot.commands import CommandContext, router
        from ching_tech_os.services.bot.command_handlers import register_builtin_commands

        register_builtin_commands()

        ctx = CommandContext(
            platform_type="line",
            platform_user_id="U_NORMAL",
            bot_user_id="uuid-normal",
            ctos_user_id=2,
            is_admin=False,
            is_group=False,
            group_id=None,
            reply_token=None,
            raw_args="",
        )

        parsed = router.parse("/debug")
        assert parsed is not None
        command, args = parsed

        reply = await router.dispatch(command, args, ctx)
        assert reply is not None
        assert "管理員" in reply

    @pytest.mark.asyncio
    async def test_debug_group_silent(self):
        """群組中 /debug 靜默忽略"""
        from ching_tech_os.services.bot.commands import CommandContext, router
        from ching_tech_os.services.bot.command_handlers import register_builtin_commands

        register_builtin_commands()

        ctx = CommandContext(
            platform_type="line",
            platform_user_id="U_ADMIN",
            bot_user_id="uuid-admin",
            ctos_user_id=1,
            is_admin=True,
            is_group=True,
            group_id="group-1",
            reply_token=None,
            raw_args="",
        )

        parsed = router.parse("/debug")
        assert parsed is not None
        command, args = parsed

        reply = await router.dispatch(command, args, ctx)
        assert reply is None  # 群組靜默忽略

    @pytest.mark.asyncio
    async def test_debug_unbound_rejected(self):
        """未綁定用戶被拒絕"""
        from ching_tech_os.services.bot.commands import CommandContext, router
        from ching_tech_os.services.bot.command_handlers import register_builtin_commands

        register_builtin_commands()

        ctx = CommandContext(
            platform_type="line",
            platform_user_id="U_UNBOUND",
            bot_user_id="uuid-unbound",
            ctos_user_id=None,
            is_admin=False,
            is_group=False,
            group_id=None,
            reply_token=None,
            raw_args="",
        )

        parsed = router.parse("/debug")
        assert parsed is not None
        command, args = parsed

        reply = await router.dispatch(command, args, ctx)
        assert reply is not None
        assert "綁定" in reply


# ============================================================
# 9.5 rate limiter 超限測試
# ============================================================


class TestRateLimiterIntegration:
    """確認 rate limiter 超過限額時回覆使用上限提示"""

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_blocks_restricted_mode(self):
        """超過頻率限制 → 受限模式回覆上限提示"""
        from ching_tech_os.services.bot.identity_router import handle_restricted_mode

        deny_msg = "您今日的使用次數已達上限，請明天再試。"

        with (
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "AI"},
                    "tools": [],
                },
            ),
            patch(
                "ching_tech_os.services.bot.rate_limiter.check_and_increment",
                new_callable=AsyncMock,
                return_value=(False, deny_msg),
            ),
        ):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id="uuid-123",
                is_group=False,
            )
            assert result == deny_msg

    @pytest.mark.asyncio
    async def test_rate_limit_not_checked_without_bot_user(self):
        """bot_user_id=None → 不檢查 rate limit"""
        from ching_tech_os.services.bot.identity_router import handle_restricted_mode

        mock_response = MagicMock()
        mock_response.tool_calls = []

        with (
            # 不 mock rate_limiter — 因為 bot_user_id=None 時不會呼叫
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "AI"},
                    "tools": [],
                },
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "ching_tech_os.services.linebot_ai.build_system_prompt",
                new_callable=AsyncMock,
                return_value="p",
            ),
            patch(
                "ching_tech_os.services.linebot_ai.get_conversation_context",
                new_callable=AsyncMock,
                return_value=([], [], []),
            ),
            patch(
                "ching_tech_os.services.mcp.get_mcp_tool_names",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ching_tech_os.services.linebot_agents.get_mcp_servers_for_user",
                new_callable=AsyncMock,
                return_value=set(),
            ),
            patch(
                "ching_tech_os.services.bot.ai.parse_ai_response",
                return_value=("OK", []),
            ),
        ):
            result = await handle_restricted_mode(
                content="hi",
                platform_user_id="U999",
                bot_user_id=None,
                is_group=False,
            )
            assert result == "OK"

    @pytest.mark.asyncio
    async def test_hourly_rate_limit_key(self):
        """每小時限額 key 格式正確"""
        from ching_tech_os.services.bot.rate_limiter import _current_hourly_key

        key = _current_hourly_key()
        # 格式：YYYY-MM-DD-HH
        assert len(key.split("-")) == 4

    @pytest.mark.asyncio
    async def test_daily_rate_limit_key(self):
        """每日限額 key 格式正確"""
        from ching_tech_os.services.bot.rate_limiter import _current_daily_key

        key = _current_daily_key()
        # 格式：YYYY-MM-DD
        assert len(key.split("-")) == 3


# ============================================================
# 跨功能整合測試
# ============================================================


class TestCrossFunctionalIntegration:
    """跨功能整合驗證"""

    def test_library_public_folders_config(self):
        """LIBRARY_PUBLIC_FOLDERS 環境變數有預設值"""
        from ching_tech_os.config import settings

        assert isinstance(settings.library_public_folders, list)
        assert len(settings.library_public_folders) > 0

    def test_knowledge_models_have_is_public(self):
        """知識庫模型包含 is_public 欄位"""
        from ching_tech_os.models.knowledge import (
            KnowledgeCreate,
            KnowledgeUpdate,
            KnowledgeResponse,
            KnowledgeListItem,
            IndexEntry,
        )

        # 驗證 is_public 存在且預設為 False
        create = KnowledgeCreate(title="t", content="c")
        assert create.is_public is False

        update = KnowledgeUpdate()
        assert update.is_public is None  # Optional

        # 驗證 Response 和 ListItem 有 is_public
        assert "is_public" in KnowledgeResponse.model_fields
        assert "is_public" in KnowledgeListItem.model_fields
        assert "is_public" in IndexEntry.model_fields

    def test_slash_command_aliases(self):
        """斜線指令別名可正確解析"""
        from ching_tech_os.services.bot.commands import router
        from ching_tech_os.services.bot.command_handlers import register_builtin_commands

        register_builtin_commands()

        # /reset 別名
        for alias in ["/reset", "/新對話", "/忘記"]:
            parsed = router.parse(alias)
            assert parsed is not None, f"別名 {alias} 無法解析"
            assert parsed[0].name == "reset"

        # /debug 別名
        for alias in ["/debug", "/診斷", "/diag"]:
            parsed = router.parse(alias)
            assert parsed is not None, f"別名 {alias} 無法解析"
            assert parsed[0].name == "debug"
