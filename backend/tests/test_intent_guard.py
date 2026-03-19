"""Intent Guard 單元測試"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ching_tech_os.services.bot.intent_guard import (
    IntentGuardResult,
    check_intent,
    _quick_keyword_match,
    _build_guard_prompt,
    _parse_guard_response,
)


# ============================================================
# 測試用工廠
# ============================================================


def _make_agent(intent_guard: dict | None = None, name: str = "test-agent") -> dict:
    """建立測試用 Agent 字典"""
    settings = {}
    if intent_guard is not None:
        settings["intent_guard"] = intent_guard
    return {"name": name, "settings": settings}


def _default_rules(**overrides) -> dict:
    """建立預設 intent_guard 規則"""
    rules = {
        "enabled": True,
        "description": "皮膚科衛教 AI",
        "allowed_topics": ["皮膚科疾病諮詢", "保養與防曬"],
        "blocked_topics": ["政治宗教", "程式開發"],
        "allow_keywords": ["皮膚", "痘痘"],
        "block_keywords": ["寫程式"],
        "examples": [
            {"message": "痘痘怎麼辦", "action": "allow"},
            {"message": "幫我寫 Python", "action": "reject", "reason": "非皮膚科"},
        ],
        "reject_message": "抱歉，我是皮膚科衛教 AI，僅能回答皮膚科相關問題。",
        "min_check_length": 2,
        "timeout": 5,
    }
    rules.update(overrides)
    return rules


def _mock_sdk_client(response_text: str):
    """建立模擬 Anthropic SDK client"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


def _mock_sdk_client_error(error: Exception):
    """建立會拋錯的模擬 SDK client"""
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=error)
    return mock_client


# ============================================================
# TestQuickKeywordMatch
# ============================================================


class TestQuickKeywordMatch:
    """關鍵字快速匹配測試"""

    def test_allow_keyword_hit(self):
        """allow_keywords 命中 → allow"""
        rules = _default_rules()
        result = _quick_keyword_match("我的皮膚很乾", rules)
        assert result is not None
        assert result.action == "allow"
        assert "allow_keyword" in result.reason

    def test_block_keyword_hit(self):
        """block_keywords 命中 → reject"""
        rules = _default_rules()
        result = _quick_keyword_match("幫我寫程式", rules)
        assert result is not None
        assert result.action == "reject"
        assert result.reject_message == rules["reject_message"]

    def test_no_match_returns_none(self):
        """無命中 → None（需 AI 判斷）"""
        rules = _default_rules()
        result = _quick_keyword_match("今天天氣如何", rules)
        assert result is None

    def test_case_insensitive(self):
        """大小寫不敏感"""
        rules = {"allow_keywords": ["Hello"], "block_keywords": []}
        result = _quick_keyword_match("HELLO world", rules)
        assert result is not None
        assert result.action == "allow"

    def test_allow_keyword_priority_over_block(self):
        """allow_keywords 優先於 block_keywords"""
        rules = {
            "allow_keywords": ["皮膚"],
            "block_keywords": ["皮膚"],
            "reject_message": "拒絕",
        }
        result = _quick_keyword_match("皮膚問題", rules)
        assert result is not None
        assert result.action == "allow"

    def test_empty_keywords(self):
        """空關鍵字列表 → None"""
        rules = {"allow_keywords": [], "block_keywords": []}
        result = _quick_keyword_match("任何訊息", rules)
        assert result is None

    def test_block_keyword_default_reject_message(self):
        """block_keywords 命中但無自訂拒絕訊息 → 使用預設"""
        rules = {"allow_keywords": [], "block_keywords": ["政治"]}
        result = _quick_keyword_match("談談政治", rules)
        assert result is not None
        assert result.action == "reject"
        assert result.reject_message == "抱歉，我無法回答這個問題。"


# ============================================================
# TestParseGuardResponse
# ============================================================


class TestParseGuardResponse:
    """JSON 解析測試"""

    def test_clean_json(self):
        result = _parse_guard_response('{"action": "allow"}')
        assert result == {"action": "allow"}

    def test_noisy_json(self):
        result = _parse_guard_response('Here: {"action": "reject", "reason": "x"}')
        assert result["action"] == "reject"

    def test_invalid(self):
        result = _parse_guard_response("no json here at all")
        assert result is None


# ============================================================
# TestDirect - direct action 測試
# ============================================================


class TestDirect:
    """direct action（直接回覆）測試"""

    @pytest.mark.asyncio
    async def test_haiku_direct(self):
        """Haiku 回 direct → 直接回覆，不進主 Agent"""
        agent = _make_agent(intent_guard=_default_rules(
            allow_keywords=[], block_keywords=[],
            direct_rules=["簡單問候可直接回覆"],
        ))

        with patch(
            "ching_tech_os.services.bot.intent_guard.settings"
        ) as mock_settings:
            mock_settings.intent_guard_enabled = True

            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
                return_value=_mock_sdk_client(
                    '{"action": "direct", "response": "你好！有什麼皮膚問題想問的嗎？"}'
                ),
            ):
                result = await check_intent("你好", agent)
                assert result.action == "direct"
                assert result.direct_response == "你好！有什麼皮膚問題想問的嗎？"

    @pytest.mark.asyncio
    async def test_direct_no_response_fallback_allow(self):
        """direct 但無 response → fallback 到 allow"""
        agent = _make_agent(intent_guard=_default_rules(
            allow_keywords=[], block_keywords=[],
            direct_rules=["簡單問候"],
        ))

        with patch(
            "ching_tech_os.services.bot.intent_guard.settings"
        ) as mock_settings:
            mock_settings.intent_guard_enabled = True

            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
                return_value=_mock_sdk_client('{"action": "direct"}'),
            ):
                result = await check_intent("你好", agent)
                assert result.action == "allow"

    def test_build_prompt_includes_direct_rules(self):
        """prompt 包含 direct_rules"""
        rules = _default_rules(direct_rules=["簡單問候可直接回覆", "營業時間查詢"])
        system, _ = _build_guard_prompt(rules, "你好")
        assert "簡單問候可直接回覆" in system
        assert "營業時間查詢" in system
        assert "direct" in system


# ============================================================
# TestBuildGuardPrompt
# ============================================================


class TestBuildGuardPrompt:
    """Prompt 組裝測試"""

    def test_basic_prompt(self):
        rules = _default_rules()
        system, user = _build_guard_prompt(rules, "痘痘怎麼辦")
        assert "皮膚科衛教 AI" in system
        assert "allow" in system
        assert "reject" in system
        assert "痘痘怎麼辦" in user

    def test_includes_topics(self):
        rules = _default_rules()
        system, _ = _build_guard_prompt(rules, "test")
        assert "皮膚科疾病諮詢" in system
        assert "政治宗教" in system

    def test_includes_examples(self):
        rules = _default_rules()
        system, _ = _build_guard_prompt(rules, "test")
        assert "痘痘怎麼辦" in system
        assert "非皮膚科" in system

    def test_empty_topics(self):
        rules = _default_rules(allowed_topics=[], blocked_topics=[], examples=[])
        system, _ = _build_guard_prompt(rules, "test")
        assert "意圖分類器" in system


# ============================================================
# TestCheckIntent - SDK 路徑
# ============================================================


class TestCheckIntent:
    """check_intent 主函式測試（SDK 路徑）"""

    @pytest.mark.asyncio
    async def test_no_intent_guard_settings(self):
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            result = await check_intent("任何訊息", _make_agent(intent_guard=None))
            assert result.action == "allow"
            assert result.reason == "no_rules"

    @pytest.mark.asyncio
    async def test_enabled_false(self):
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            agent = _make_agent(intent_guard=_default_rules(enabled=False))
            result = await check_intent("任何訊息", agent)
            assert result.action == "allow"
            assert result.reason == "agent_disabled"

    @pytest.mark.asyncio
    async def test_no_agent(self):
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            result = await check_intent("任何訊息", None)
            assert result.action == "allow"
            assert result.reason == "no_agent"

    @pytest.mark.asyncio
    async def test_short_message(self):
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            agent = _make_agent(intent_guard=_default_rules(min_check_length=5))
            result = await check_intent("嗨", agent)
            assert result.action == "allow"
            assert result.reason == "too_short"

    @pytest.mark.asyncio
    async def test_global_disabled(self):
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = False
            result = await check_intent("任何訊息", _make_agent())
            assert result.action == "allow"
            assert result.reason == "global_disabled"

    @pytest.mark.asyncio
    async def test_keyword_allow_skips_ai(self):
        """關鍵字匹配放行 → 不呼叫 AI"""
        agent = _make_agent(intent_guard=_default_rules())
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
            ) as mock_gc:
                result = await check_intent("我的皮膚很癢", agent)
                assert result.action == "allow"
                mock_gc.assert_not_called()

    @pytest.mark.asyncio
    async def test_haiku_allow(self):
        agent = _make_agent(intent_guard=_default_rules(
            allow_keywords=[], block_keywords=[],
        ))
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
                return_value=_mock_sdk_client('{"action": "allow"}'),
            ):
                result = await check_intent("今天天氣好嗎", agent)
                assert result.action == "allow"

    @pytest.mark.asyncio
    async def test_haiku_reject(self):
        custom_msg = "抱歉，我只回答皮膚科問題。"
        agent = _make_agent(intent_guard=_default_rules(
            allow_keywords=[], block_keywords=[], reject_message=custom_msg,
        ))
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
                return_value=_mock_sdk_client(
                    '{"action": "reject", "reason": "程式開發問題"}'
                ),
            ):
                result = await check_intent("幫我寫一個 Python 程式", agent)
                assert result.action == "reject"
                assert result.reason == "程式開發問題"
                assert result.reject_message == custom_msg

    @pytest.mark.asyncio
    async def test_api_timeout_failopen(self):
        agent = _make_agent(intent_guard=_default_rules(
            allow_keywords=[], block_keywords=[],
        ))
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
                return_value=_mock_sdk_client_error(TimeoutError("timeout")),
            ):
                result = await check_intent("任何訊息", agent)
                assert result.action == "allow"
                assert result.reason == "timeout"

    @pytest.mark.asyncio
    async def test_api_error_failopen(self):
        agent = _make_agent(intent_guard=_default_rules(
            allow_keywords=[], block_keywords=[],
        ))
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
                return_value=_mock_sdk_client_error(RuntimeError("err")),
            ):
                result = await check_intent("任何訊息", agent)
                assert result.action == "allow"
                assert result.reason == "error"

    @pytest.mark.asyncio
    async def test_invalid_json_failopen(self):
        agent = _make_agent(intent_guard=_default_rules(
            allow_keywords=[], block_keywords=[],
        ))
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
                return_value=_mock_sdk_client("no json here at all"),
            ):
                result = await check_intent("任何訊息", agent)
                assert result.action == "allow"
                assert result.reason == "invalid_json"

    @pytest.mark.asyncio
    async def test_json_in_noisy_response(self):
        agent = _make_agent(intent_guard=_default_rules(
            allow_keywords=[], block_keywords=[],
        ))
        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
                return_value=_mock_sdk_client(
                    'Here: {"action": "reject", "reason": "off-topic"}'
                ),
            ):
                result = await check_intent("幫我算命", agent)
                assert result.action == "reject"


# ============================================================
# TestCliFallback - 無 API Key 時走 call_claude
# ============================================================


class TestCliFallback:
    """無 ANTHROPIC_API_KEY 時 fallback 到 call_claude"""

    @pytest.mark.asyncio
    async def test_fallback_to_cli_reject(self):
        """無 API Key → 用 call_claude，reject 正常運作"""
        agent = _make_agent(intent_guard=_default_rules(
            allow_keywords=[], block_keywords=[],
        ))

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.message = '{"action": "reject", "reason": "off-topic"}'

        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
                return_value=None,  # 無 API Key
            ):
                with patch(
                    "ching_tech_os.services.claude_agent.call_claude",
                    new_callable=AsyncMock,
                    return_value=mock_response,
                ):
                    result = await check_intent("幫我算命", agent)
                    assert result.action == "reject"

    @pytest.mark.asyncio
    async def test_fallback_cli_failure_failopen(self):
        """call_claude 失敗 → fail-open"""
        agent = _make_agent(intent_guard=_default_rules(
            allow_keywords=[], block_keywords=[],
        ))

        mock_response = MagicMock()
        mock_response.success = False
        mock_response.message = "timeout"

        with patch("ching_tech_os.services.bot.intent_guard.settings") as ms:
            ms.intent_guard_enabled = True
            with patch(
                "ching_tech_os.services.bot.intent_guard._get_client",
                return_value=None,
            ):
                with patch(
                    "ching_tech_os.services.claude_agent.call_claude",
                    new_callable=AsyncMock,
                    return_value=mock_response,
                ):
                    result = await check_intent("任何訊息", agent)
                    assert result.action == "allow"
                    assert result.reason == "error"


# ============================================================
# TestIntegration - identity_router 整合
# ============================================================


class TestIntegration:
    """Intent Guard 與 identity_router 整合測試"""

    @pytest.mark.asyncio
    async def test_reject_skips_call_claude(self):
        """reject 時不呼叫 call_claude"""
        agent = _make_agent(
            intent_guard=_default_rules(), name="jfmskin-edu",
        )
        agent["model"] = "haiku"
        agent["system_prompt"] = {"content": "你是衛教 AI"}
        agent["tools"] = []
        agent["id"] = "test-id"

        with (
            patch("ching_tech_os.services.bot.identity_router.settings") as mock_s,
            patch("ching_tech_os.services.bot.intent_guard.settings") as mock_gs,
            patch(
                "ching_tech_os.services.bot.intent_guard.check_intent",
                new_callable=AsyncMock,
            ) as mock_check,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock, return_value=agent,
            ),
            patch(
                "ching_tech_os.services.linebot_agents.get_restricted_agent",
                new_callable=AsyncMock, return_value=agent,
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
            ) as mock_call,
            patch(
                "ching_tech_os.services.bot.rate_limiter.check_and_increment",
                new_callable=AsyncMock, return_value=(True, None),
            ),
        ):
            mock_s.bot_unbound_user_policy = "restricted"
            mock_s.bot_restricted_model = "haiku"
            mock_s.bot_rate_limit_enabled = True
            mock_s.intent_guard_enabled = True
            mock_gs.intent_guard_enabled = True

            mock_check.return_value = IntentGuardResult(
                action="reject", reason="off-topic",
                reject_message="抱歉，我無法回答。", duration_ms=50,
            )

            from ching_tech_os.services.bot.identity_router import handle_restricted_mode
            result = await handle_restricted_mode(
                content="幫我寫程式", platform_user_id="U123",
                bot_user_id="bot-user-1", is_group=False,
            )

            assert result == "抱歉，我無法回答。"
            mock_call.assert_not_called()
