"""Codex Provider 契約、安全邊界與資源治理測試。"""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from acp.schema import HttpMcpServer

from ching_tech_os.services import ai_provider, codex_agent
from ching_tech_os.config import settings


# 專案根目錄的 .mcp.json 被 .gitignore 擋著（見 .gitignore:56），CI 上不存在。
# provider 會把它合併後寫進 session 工作目錄再讀回來，所以少了它整條 MCP
# 清單就是空的——本檔測 MCP 過濾的案例會在開發機通過、在 CI 全滅。
# 這裡改讓測試自備一份設定，不依賴跑測試的機器上有什麼。
_MCP_FIXTURE = {
    "mcpServers": {
        "ching-tech-os": {
            "command": "bash",
            "args": ["-c", "true"],
        },
        "github": {
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {"Authorization": "Bearer test-token"},
        },
        # 留著讓「未被要求的 server 會被過濾掉」那條斷言真的有東西可過濾
        "nanobanana": {
            "type": "stdio",
            "command": "bash",
            "args": ["-c", "true"],
        },
    }
}


@pytest.fixture(autouse=True)
def _hermetic_mcp_config(tmp_path, monkeypatch):
    """讓 provider 讀到固定的 .mcp.json，與開發機上的實際設定脫鉤。"""
    (tmp_path / ".mcp.json").write_text(
        json.dumps(_MCP_FIXTURE, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(settings, "project_root", str(tmp_path))


class FakeCodexClient:
    def __init__(self, *, scenario: str = "success", **kwargs: Any) -> None:
        self.scenario = scenario
        self.kwargs = kwargs
        self.events: dict[str, Any] = {}
        self._text_buffer = ""
        self.input_tokens = 12
        self.output_tokens = 7
        self.model_name = "gpt-test"
        self.stderr_max_bytes = 0
        self.disconnected = False
        self.cancelled = False
        self.permission_results: list[str] = []
        self.model: str | None = None

    def _decorator(self, name: str):
        def register(func):
            self.events[name] = func
            return func
        return register

    @property
    def on_tool_start(self):
        return self._decorator("tool_start")

    @property
    def on_tool_end(self):
        return self._decorator("tool_end")

    @property
    def on_permission(self):
        return self._decorator("permission")

    @property
    def on_terminal_create(self):
        return self._decorator("terminal")

    @property
    def on_file_write(self):
        return self._decorator("file_write")

    async def connect(self) -> None:
        if self.scenario == "auth_error":
            raise RuntimeError("authentication token secret-value expired")
        if self.scenario == "protocol_error":
            raise RuntimeError("protocol initialize invalid secret-value")

    async def set_model(self, model: str) -> None:
        self.model = model

    async def new_session(self) -> str:
        if self.scenario == "mcp_error":
            raise RuntimeError("MCP startup connection failed secret-value")
        return "session-1"

    async def prompt(self, text: str) -> str:
        self.prompt_text = text
        if self.scenario == "timeout":
            self._text_buffer = "部分結果"
            await asyncio.Future()
        if self.scenario == "overload":
            raise RuntimeError("429 rate limit secret-value")
        if self.scenario == "native":
            await self.events["tool_start"]("native-1", "Image generation", {})
            await self.events["tool_end"]("native-1", "completed", "image")
        if self.scenario.startswith("tool"):
            await self._emit_tools()
        self._text_buffer = "完成"
        return "完成"

    async def _emit_tools(self) -> None:
        if self.scenario == "tool_short":
            title = "search_knowledge"
            raw = {"tool": "search_knowledge"}
        elif self.scenario == "tool_mismatch":
            title = "mcp.other.search_knowledge"
            raw = {"server": "ching-tech-os", "tool": "search_knowledge"}
        else:
            title = "mcp.ching-tech-os.search_knowledge"
            raw = {
                "server": "ching-tech-os",
                "tool": "search_knowledge",
                "arguments": {"query": "test"},
            }
        repeats = 2 if self.scenario == "tool_twice" else 1
        for index in range(repeats):
            tool_id = f"tool-{index}"
            await self.events["tool_start"](tool_id, title, dict(raw))
            permission_input = {**raw, "_acp_tool_call_id": tool_id}
            result = await self.events["permission"](
                title,
                permission_input,
                [
                    {"id": "allow_once", "kind": "allow_once"},
                    {"id": "reject_once", "kind": "reject_once"},
                ],
            )
            self.permission_results.append(result)
            status = "completed" if result == "allow_once" else "failed"
            await self.events["tool_end"](tool_id, status, {"ok": True})

    async def cancel(self) -> None:
        self.cancelled = True

    async def disconnect(self) -> None:
        self.disconnected = True


class FakeFactory:
    def __init__(self, scenario: str = "success") -> None:
        self.scenario = scenario
        self.clients: list[FakeCodexClient] = []

    def __call__(self, **kwargs: Any) -> FakeCodexClient:
        client = FakeCodexClient(scenario=self.scenario, **kwargs)
        self.clients.append(client)
        return client


def make_provider(factory: FakeFactory, **kwargs: Any) -> codex_agent.CodexProvider:
    return codex_agent.CodexProvider(
        client_factory=factory,
        adapter_path="/bin/true",
        codex_path="/bin/true",
        model="gpt-test",
        **kwargs,
    )


def test_codex_provider_matches_complete_request_contract(provider_contract_spec) -> None:
    fields = set(inspect.signature(codex_agent.CodexProvider.call).parameters) - {"self"}
    assert fields == provider_contract_spec.claude_request_fields
    assert isinstance(make_provider(FakeFactory()), ai_provider.AIProvider)


@pytest.mark.asyncio
async def test_success_preserves_history_system_usage_model_and_cleanup() -> None:
    factory = FakeFactory()
    provider = make_provider(factory)
    result = await provider.call(
        prompt="新問題",
        history=[{"role": "user", "content": "舊問題"}],
        system_prompt="只回答事實",
    )

    client = factory.clients[0]
    assert result.success is True
    assert result.message == "完成"
    assert (result.input_tokens, result.output_tokens) == (12, 7)
    assert result.actual_model == "gpt-test"
    assert result.provider_started is True
    assert "舊問題" in client.prompt_text and "只回答事實" in client.prompt_text
    assert "禁止 terminal" in client.prompt_text
    assert client.disconnected is True
    assert not Path(client.kwargs["cwd"]).exists()
    config = json.loads(client.kwargs["env"]["CODEX_CONFIG"])
    assert config["sandbox_mode"] == "read-only"
    assert config["approval_policy"] == "on-request"
    assert config["features"]["multi_agent"] is False


@pytest.mark.asyncio
async def test_mcp_filter_and_framework_identity_env_are_preserved() -> None:
    factory = FakeFactory()
    provider = make_provider(factory)
    await provider.call(
        prompt="查詢",
        tools=["mcp__ching-tech-os__search_knowledge"],
        required_mcp_servers=set(),
        ctos_user_id=42,
        extra_mcp_env={"CTOS_GROUP_ID": "group-1"},
    )

    servers = factory.clients[0].kwargs["mcp_servers"]
    ctos = next(server for server in servers if server.name == "ching-tech-os")
    env = {item.name: item.value for item in ctos.env}
    assert env["CTOS_USER_ID"] == "42"
    assert env["CTOS_GROUP_ID"] == "group-1"
    assert {server.name for server in servers} == {"ching-tech-os"}


@pytest.mark.asyncio
async def test_http_mcp_is_preserved_and_unrequired_servers_are_filtered() -> None:
    factory = FakeFactory()
    await make_provider(factory).call(
        prompt="唯讀 GitHub 查詢",
        tools=[
            "mcp__github__search_repositories",
            "mcp__nanobanana__generate_image",
        ],
        required_mcp_servers={"github"},
    )

    servers = factory.clients[0].kwargs["mcp_servers"]
    assert {server.name for server in servers} == {"ching-tech-os", "github"}
    github = next(server for server in servers if server.name == "github")
    assert isinstance(github, HttpMcpServer)
    assert github.url == "https://api.githubcopilot.com/mcp/"
    assert all(server.name != "nanobanana" for server in servers)


@pytest.mark.asyncio
async def test_canonical_tool_permission_and_callbacks_are_exact() -> None:
    factory = FakeFactory("tool")
    provider = make_provider(factory)
    on_start = AsyncMock(side_effect=RuntimeError("caller callback failure"))
    on_end = AsyncMock()
    result = await provider.call(
        prompt="查詢",
        tools=["mcp__ching-tech-os__search_knowledge"],
        on_tool_start=on_start,
        on_tool_end=on_end,
    )

    assert result.success is True
    assert factory.clients[0].permission_results == ["allow_once"]
    assert [item.name for item in result.tool_calls] == [
        "mcp__ching-tech-os__search_knowledge"
    ]
    assert result.tool_timings[0]["name"] == "mcp__ching-tech-os__search_knowledge"
    on_start.assert_awaited_once()
    on_end.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["tool_short", "tool_mismatch"])
async def test_missing_namespace_and_mismatched_identity_fail_closed(scenario: str) -> None:
    factory = FakeFactory(scenario)
    result = await make_provider(factory).call(
        prompt="不可執行",
        tools=["mcp__ching-tech-os__search_knowledge"],
    )
    assert result.success is False
    assert result.error == "Codex 請求失敗（security_violation）"
    assert factory.clients[0].permission_results == ["reject_once"]
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_same_tool_on_other_server_and_short_allowlist_are_denied() -> None:
    """白名單外的工具被拒絕（fail-closed），但不作廢整個回應。

    2026-08-19 第一次真實切換發現：system prompt 以過濾前工具清單組成，
    模型會嘗試呼叫被過濾的工具；拒絕即已守住安全，回應本身應保留。
    """
    factory = FakeFactory("tool")
    result = await make_provider(factory).call(
        prompt="不可猜測 namespace",
        tools=["search_knowledge", "mcp__other__search_knowledge"],
    )
    # 工具被拒、未執行、不記入 tool_calls；文字回應保留
    assert factory.clients[0].permission_results == ["reject_once"]
    assert result.tool_calls == []
    assert result.success is True
    assert result.message == "完成"


@pytest.mark.asyncio
async def test_missing_permission_correlation_id_still_fails_closed() -> None:
    """permission 事件缺 correlation id（adapter 契約破壞）仍整體作廢。"""

    class NoCorrelationClient(FakeCodexClient):
        async def _emit_tools(self) -> None:
            title = "mcp.ching-tech-os.search_knowledge"
            raw = {"server": "ching-tech-os", "tool": "search_knowledge"}
            await self.events["tool_start"]("tool-0", title, dict(raw))
            # 不帶 _acp_tool_call_id
            result = await self.events["permission"](
                title, dict(raw),
                [{"id": "allow_once", "kind": "allow_once"},
                 {"id": "reject_once", "kind": "reject_once"}],
            )
            self.permission_results.append(result)

    factory = FakeFactory("tool")
    factory_clients: list[NoCorrelationClient] = []

    def factory_fn(**kwargs):
        client = NoCorrelationClient(scenario="tool", **kwargs)
        factory_clients.append(client)
        return client

    provider = codex_agent.CodexProvider(
        client_factory=factory_fn,
        adapter_path="/bin/true",
        codex_path="/bin/true",
    )
    result = await provider.call(
        prompt="x", tools=["mcp__ching-tech-os__search_knowledge"]
    )
    assert result.success is False
    assert result.error == "Codex 請求失敗（security_violation）"
    assert factory_clients[0].permission_results == ["reject_once"]


@pytest.mark.asyncio
async def test_tool_limit_and_global_image_limits() -> None:
    factory = FakeFactory("tool_twice")
    result = await make_provider(factory).call(
        prompt="最多一次",
        tools=["mcp__ching-tech-os__search_knowledge"],
        tool_call_limits={"mcp__ching-tech-os__search_knowledge": 1},
    )
    assert result.success is True
    assert factory.clients[0].permission_results == ["allow_once", "reject_once"]
    assert len(result.tool_calls) == 1

    limits = codex_agent.CodexProvider._build_tool_limits(
        {
            ("nanobanana", "generate_image"),
            ("ching-tech-os", "codex_image_tool"),
        },
        None,
    )
    assert limits["mcp__nanobanana__generate_image"] >= 1
    assert limits["mcp__ching-tech-os__codex_image_tool"] >= 1


@pytest.mark.asyncio
async def test_native_image_terminal_and_file_write_are_denied() -> None:
    factory = FakeFactory("native")
    result = await make_provider(factory).call(prompt="產圖")
    client = factory.clients[0]
    assert result.success is False
    assert await client.events["terminal"]("ls", "/tmp") is False
    assert await client.events["file_write"]("x", "data") is False


@pytest.mark.asyncio
async def test_timeout_keeps_partial_result_cancels_and_cleans_up() -> None:
    factory = FakeFactory("timeout")
    result = await make_provider(factory).call(prompt="慢請求", timeout=0.01)
    client = factory.clients[0]
    assert result.success is False
    assert result.message == "部分結果"
    assert result.error == "Codex 請求失敗（timeout）"
    assert client.cancelled is True and client.disconnected is True
    assert not Path(client.kwargs["cwd"]).exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "category"),
    [
        ("auth_error", "auth_error"),
        ("protocol_error", "protocol_error"),
        ("mcp_error", "mcp_startup_error"),
        ("overload", "overload"),
    ],
)
async def test_failures_are_categorized_without_leaking_raw_errors(
    scenario: str, category: str
) -> None:
    result = await make_provider(FakeFactory(scenario)).call(prompt="測試")
    assert result.success is False
    assert category in (result.error or "")
    assert "secret-value" not in (result.error or "")


@pytest.mark.asyncio
async def test_binary_missing_is_pre_start_failure() -> None:
    provider = codex_agent.CodexProvider(
        client_factory=FakeFactory(),
        adapter_path="/definitely/missing/codex-acp",
        codex_path="/bin/true",
    )
    assert await provider.is_ready() is False
    result = await provider.call(prompt="測試")
    assert result.provider_started is False
    assert "binary_missing" in (result.error or "")


@pytest.mark.asyncio
async def test_client_factory_failure_cleans_pre_start_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    monkeypatch.setattr(
        codex_agent, "_create_session_workdir", lambda: str(session_dir)
    )

    def broken_factory(**_kwargs):
        raise RuntimeError("constructor secret-value")

    provider = codex_agent.CodexProvider(
        client_factory=broken_factory,
        adapter_path="/bin/true",
        codex_path="/bin/true",
    )
    result = await provider.call(prompt="測試")

    assert result.provider_started is False
    assert result.error == "Codex 請求失敗（execution_error）"
    assert not session_dir.exists()


@pytest.mark.asyncio
async def test_external_cancellation_still_disconnects_and_cleans_session() -> None:
    factory = FakeFactory("timeout")
    provider = make_provider(factory)
    task = asyncio.create_task(provider.call(prompt="取消測試", timeout=30))
    while not factory.clients:
        await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    client = factory.clients[0]
    assert client.disconnected is True
    assert not Path(client.kwargs["cwd"]).exists()


@pytest.mark.asyncio
async def test_concurrency_queue_timeout_rejects_without_spawning_second_client() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingClient(FakeCodexClient):
        async def prompt(self, text: str) -> str:
            entered.set()
            await release.wait()
            return await super().prompt(text)

    clients: list[BlockingClient] = []

    def factory(**kwargs):
        client = BlockingClient(**kwargs)
        clients.append(client)
        return client

    provider = codex_agent.CodexProvider(
        client_factory=factory,
        adapter_path="/bin/true",
        codex_path="/bin/true",
        max_concurrency=1,
        queue_timeout=0.01,
    )
    first = asyncio.create_task(provider.call(prompt="first"))
    await entered.wait()
    second = await provider.call(prompt="second")
    release.set()
    await first
    assert second.provider_started is False
    assert "queue_timeout" in (second.error or "")
    assert len(clients) == 1


@pytest.mark.asyncio
async def test_circuit_breaker_opens_and_recovers_after_cooldown() -> None:
    now = [10.0]
    breaker = codex_agent.CodexCircuitBreaker(2, 5, clock=lambda: now[0])
    provider = make_provider(FakeFactory("protocol_error"), circuit_breaker=breaker)
    await provider.call(prompt="one")
    assert await provider.is_ready() is True
    await provider.call(prompt="two")
    assert await provider.is_ready() is False
    now[0] = 15.1
    assert await provider.is_ready() is True


def test_canonical_parser_rejects_unknown_and_conflicting_names() -> None:
    assert codex_agent._canonical_identity("Unknown", {}) is None
    assert codex_agent._canonical_identity(
        "mcp.a.tool", {"server": "b", "tool": "tool"}
    ) is None
    assert codex_agent._allowed_identities(["tool", "mcp__a__tool"]) == {("a", "tool")}


# ── 7.3 可觀測性：queue latency、circuit 狀態與工具事件 log ──


@pytest.mark.asyncio
async def test_codex_call_logs_queue_wait_and_circuit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = make_provider(FakeFactory())
    with caplog.at_level("INFO", logger="ching_tech_os.services.codex_agent"):
        result = await provider.call(prompt="hi")
    assert result.success is True
    call_logs = [
        record.getMessage()
        for record in caplog.records
        if "codex_call" in record.getMessage()
    ]
    assert call_logs, "codex call 必須輸出 codex_call structured log"
    assert "queue_wait_ms=" in call_logs[0]
    assert "circuit=closed" in call_logs[0]


@pytest.mark.asyncio
async def test_codex_queue_timeout_logs_circuit_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingClient(FakeCodexClient):
        async def prompt(self, text: str) -> str:
            entered.set()
            await release.wait()
            return await super().prompt(text)

    provider = codex_agent.CodexProvider(
        client_factory=lambda **kwargs: BlockingClient(**kwargs),
        adapter_path="/bin/true",
        codex_path="/bin/true",
        max_concurrency=1,
        queue_timeout=0.01,
    )
    first = asyncio.create_task(provider.call(prompt="first"))
    await entered.wait()
    with caplog.at_level("WARNING", logger="ching_tech_os.services.codex_agent"):
        second = await provider.call(prompt="second")
    release.set()
    await first
    assert second.success is False
    timeout_logs = [
        record.getMessage()
        for record in caplog.records
        if "codex_queue_timeout" in record.getMessage()
    ]
    assert timeout_logs
    assert "circuit=" in timeout_logs[0]


@pytest.mark.asyncio
async def test_codex_tool_events_logged_without_arguments(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = make_provider(FakeFactory("tool"))
    with caplog.at_level("INFO", logger="ching_tech_os.services.codex_agent"):
        result = await provider.call(
            prompt="hi", tools=["mcp__ching-tech-os__search_knowledge"]
        )
    assert result.success is True
    messages = [record.getMessage() for record in caplog.records]
    started = [m for m in messages if "codex_tool_started" in m]
    completed = [m for m in messages if "codex_tool_completed" in m]
    assert started and "mcp__ching-tech-os__search_knowledge" in started[0]
    assert completed and "duration_ms=" in completed[0]
    # 工具輸入參數（可能含使用者資料）不得寫入 log
    assert "query" not in caplog.text


@pytest.mark.asyncio
async def test_unexpected_exception_types_fail_closed_and_trip_circuit() -> None:
    """9.6 演練發現:非白名單例外(如 acp RequestError)必須轉安全失敗並記入 circuit。"""

    class CustomAcpError(Exception):
        """模擬 acp.exceptions.RequestError 這類不在舊白名單的例外。"""

    class ExplodingClient(FakeCodexClient):
        async def connect(self) -> None:
            raise CustomAcpError(
                'Codex process has exited with code 1: CODEX_HOME points to "/bad" secret-value'
            )

    factory_clients: list[ExplodingClient] = []

    def factory(**kwargs):
        client = ExplodingClient(**kwargs)
        factory_clients.append(client)
        return client

    breaker = codex_agent.CodexCircuitBreaker(3, 60.0)
    provider = codex_agent.CodexProvider(
        client_factory=factory,
        adapter_path="/bin/true",
        codex_path="/bin/true",
        circuit_breaker=breaker,
    )
    result = await provider.call(prompt="hi")

    # fail closed:回傳安全 failure response,不 raise、不洩漏原始訊息
    assert result.success is False
    assert result.provider == "codex"
    assert "secret-value" not in (result.error or "")
    # circuit 必須記到失敗
    assert breaker.status()["consecutive_failures"] == 1
    # client 必須清理
    assert factory_clients[0].disconnected is True


@pytest.mark.asyncio
async def test_mcp_server_startup_events_are_ignored_not_violations() -> None:
    """2026-08-19 真實流量發現:adapter 會以 tool 事件回報 MCP server 啟動
    （title=mcp__<server>__startup），不得誤判為非 canonical 工具而作廢回應。"""

    class StartupEventClient(FakeCodexClient):
        async def prompt(self, text: str) -> str:
            self.prompt_text = text
            # 模擬 adapter 的 MCP server 啟動通知(start + completed end)
            for i, server in enumerate(("nanobanana", "erpnext")):
                tool_id = f"infra-{i}"
                await self.events["tool_start"](tool_id, f"mcp__{server}__startup", {})
                await self.events["tool_end"](tool_id, "completed", None)
            # 之後正常執行一個合法工具
            await self._emit_tools()
            self._text_buffer = "完成"
            return "完成"

    clients: list[StartupEventClient] = []

    def factory(**kwargs):
        client = StartupEventClient(scenario="tool", **kwargs)
        clients.append(client)
        return client

    provider = codex_agent.CodexProvider(
        client_factory=factory,
        adapter_path="/bin/true",
        codex_path="/bin/true",
    )
    result = await provider.call(
        prompt="hi", tools=["mcp__ching-tech-os__search_knowledge"]
    )
    # startup 事件被忽略,回應與合法工具都正常
    assert result.success is True
    assert result.message == "完成"
    assert [t.name for t in result.tool_calls] == [
        "mcp__ching-tech-os__search_knowledge"
    ]
