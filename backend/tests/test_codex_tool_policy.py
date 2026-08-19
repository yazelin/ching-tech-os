"""Per-context Codex 工具政策測試（add-codex-pipeline-parity 任務 2.x）。

預設唯讀 fail-closed 不變；只有明確列舉的 context+工具才額外放行。
"""

from __future__ import annotations

import pytest

from ching_tech_os import config
from ching_tech_os.services import ai_provider, ai_router
from ching_tech_os.services.ai_provider import AIResponse


# ── 設定解析 ─────────────────────────────────────────────────


def test_parse_context_tool_allowlist_valid() -> None:
    parsed = config._parse_context_tool_allowlist(
        "Linebot-Group:mcp__nanobanana__generate_image|mcp__ching-tech-os__add_note,"
        "scheduler:mcp__ching-tech-os__send_nas_file"
    )
    assert parsed == {
        "linebot-group": frozenset(
            {"mcp__nanobanana__generate_image", "mcp__ching-tech-os__add_note"}
        ),
        "scheduler": frozenset({"mcp__ching-tech-os__send_nas_file"}),
    }


def test_parse_context_tool_allowlist_empty() -> None:
    assert config._parse_context_tool_allowlist("") == {}
    assert config._parse_context_tool_allowlist("   ") == {}


@pytest.mark.parametrize(
    "value",
    [
        "missing-colon-entry",                       # 缺冒號
        "ctx:not_canonical_tool",                    # 工具非 mcp__ canonical 格式
        "ctx:mcp__broken",                           # 缺 tool 段
        ":mcp__a__b",                                # 缺 context
        "ctx:",                                      # 缺工具
        "good:mcp__a__b,bad-entry",                  # 一條壞 → 全部作廢（不部分套用）
    ],
)
def test_parse_context_tool_allowlist_invalid_falls_back_empty(
    value: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("ERROR", logger=config.__name__):
        assert config._parse_context_tool_allowlist(value) == {}
    assert "CODEX_CONTEXT_TOOL_ALLOWLIST" in caplog.text


# ── filter 擴充 ──────────────────────────────────────────────


def test_filter_with_extra_allowlist_adds_only_listed_tools() -> None:
    tools = [
        "mcp__ching-tech-os__search_knowledge",
        "mcp__nanobanana__generate_image",
        "mcp__ching-tech-os__add_note",
    ]
    # 無 extra：維持唯讀
    assert ai_router.filter_codex_readonly_tools(tools) == [
        "mcp__ching-tech-os__search_knowledge"
    ]
    # 有 extra：唯讀 + 明列工具，未列的仍過濾
    filtered = ai_router.filter_codex_readonly_tools(
        tools, extra_allowlist=frozenset({"mcp__nanobanana__generate_image"})
    )
    assert filtered == [
        "mcp__ching-tech-os__search_knowledge",
        "mcp__nanobanana__generate_image",
    ]


# ── router / call_ai 整合 ────────────────────────────────────


class RecordingProvider:
    def __init__(self, name: str, *, ready: bool = True) -> None:
        self.provider_name = name
        self.ready = ready
        self.kwargs: dict | None = None

    async def is_ready(self) -> bool:
        return self.ready

    async def call(self, **kwargs) -> AIResponse:
        self.kwargs = kwargs
        return AIResponse(success=True, message="ok", provider=self.provider_name)


@pytest.mark.asyncio
async def test_call_ai_applies_context_allowlist_to_codex_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claude = RecordingProvider("claude")
    codex = RecordingProvider("codex")
    monkeypatch.setattr(
        ai_router,
        "_provider_router",
        ai_router.ProviderRouter({"claude": claude, "codex": codex}),
    )
    monkeypatch.setattr(config.settings, "ai_provider_mode", "codex")
    monkeypatch.setattr(
        config.settings,
        "codex_context_tool_allowlist",
        {"linebot-group": frozenset({"mcp__nanobanana__generate_image"})},
    )
    tools = [
        "mcp__ching-tech-os__search_knowledge",
        "mcp__nanobanana__generate_image",
        "mcp__ching-tech-os__add_note",
    ]

    # 在 allowlist 的 context：唯讀 + 明列工具
    await ai_router.call_ai(
        prompt="hi",
        tools=list(tools),
        routing_context=ai_router.RoutingContext(context_type="linebot-group"),
    )
    assert codex.kwargs is not None
    assert codex.kwargs["tools"] == [
        "mcp__ching-tech-os__search_knowledge",
        "mcp__nanobanana__generate_image",
    ]

    # 不在 allowlist 的 context：維持純唯讀
    await ai_router.call_ai(
        prompt="hi",
        tools=list(tools),
        routing_context=ai_router.RoutingContext(context_type="telegram-group"),
    )
    assert codex.kwargs["tools"] == ["mcp__ching-tech-os__search_knowledge"]

    # 無 routing_context：維持純唯讀
    await ai_router.call_ai(prompt="hi", tools=list(tools))
    assert codex.kwargs["tools"] == ["mcp__ching-tech-os__search_knowledge"]


@pytest.mark.asyncio
async def test_pre_start_fallback_to_claude_keeps_full_tools_with_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claude = RecordingProvider("claude")
    codex_down = RecordingProvider("codex", ready=False)
    monkeypatch.setattr(
        ai_router,
        "_provider_router",
        ai_router.ProviderRouter({"claude": claude, "codex": codex_down}),
    )
    monkeypatch.setattr(config.settings, "ai_provider_mode", "codex")
    monkeypatch.setattr(
        config.settings,
        "codex_context_tool_allowlist",
        {"linebot-group": frozenset({"mcp__nanobanana__generate_image"})},
    )
    tools = [
        "mcp__ching-tech-os__search_knowledge",
        "mcp__ching-tech-os__add_note",
    ]
    await ai_router.call_ai(
        prompt="hi",
        tools=list(tools),
        routing_context=ai_router.RoutingContext(context_type="linebot-group"),
    )
    assert claude.kwargs is not None
    assert claude.kwargs["tools"] == tools


def test_extra_allowlist_appends_tools_hidden_by_caller() -> None:
    """真實流量:script-first 路由會把部分工具從清單隱藏(Claude 下改走 run_skill_script),
    Codex 下 run_skill_script 被擋 → allowlist 必須能把明確放行的工具補回來。"""
    tools = ["mcp__ching-tech-os__search_knowledge"]  # create_share_link 被上游隱藏
    filtered = ai_router.filter_codex_readonly_tools(
        tools,
        extra_allowlist=frozenset({"mcp__ching-tech-os__create_share_link"}),
    )
    assert filtered == [
        "mcp__ching-tech-os__search_knowledge",
        "mcp__ching-tech-os__create_share_link",
    ]
    # tools=None(無工具請求)不受 extra 影響
    assert ai_router.filter_codex_readonly_tools(
        None, extra_allowlist=frozenset({"mcp__ching-tech-os__create_share_link"})
    ) is None
