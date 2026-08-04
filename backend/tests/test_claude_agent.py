"""claude_agent 服務測試。"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os import modules
from ching_tech_os.services import ai_manager, claude_agent


def test_provider_contract_fixture_matches_current_claude_boundary(
    provider_contract_spec,
) -> None:
    request_fields = set(inspect.signature(claude_agent.call_claude).parameters)
    assert request_fields == provider_contract_spec.claude_request_fields
    assert provider_contract_spec.ai_request_fields == request_fields | {"routing_context"}

    response = claude_agent.ClaudeResponse(
        success=False,
        message="部分內容",
        error="請求超時",
        tool_calls=[
            claude_agent.ToolCall(
                id="tool-1",
                name="search_knowledge",
                input={"query": "馬達"},
                output="{}",
            )
        ],
        input_tokens=11,
        output_tokens=7,
        tool_timings=[{"name": "search_knowledge", "duration_ms": 12}],
    )
    assert provider_contract_spec.response_fields <= set(vars(response))
    assert provider_contract_spec.partial_result_fields <= set(vars(response))
    assert provider_contract_spec.routing_metadata_fields == {
        "provider",
        "actual_model",
        "route_reason",
        "provider_started",
        "usage_snapshot",
    }
    assert provider_contract_spec.tool_start_fields == {
        "tool_call_id",
        "name",
        "input",
    }
    assert provider_contract_spec.tool_end_fields == {
        "tool_call_id",
        "name",
        "status",
        "output",
        "duration_ms",
    }


def test_workdir_and_prompt_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workbase = tmp_path / "workbase"
    workbase.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(claude_agent, "_WORKING_DIR_BASE", str(workbase))

    from ching_tech_os.config import settings

    nas_root = tmp_path / "nas"
    nas_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(settings, "project_root", str(tmp_path))

    # 模擬 linebot_local_path 存在
    linebot_local_path = Path(settings.linebot_local_path)
    linebot_local_path.mkdir(parents=True, exist_ok=True)

    project_mcp = tmp_path / ".mcp.json"
    project_mcp.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    session_dir = claude_agent._create_session_workdir()
    session_path = Path(session_dir)
    assert session_path.exists()
    assert (session_path / "nanobanana-output").exists()
    assert (session_path / ".mcp.json").exists()

    claude_agent._cleanup_session_workdir(session_dir)
    assert not session_path.exists()

    composed = claude_agent.compose_prompt_with_history(
        history=[
            {"role": "system", "content": "摘要", "is_summary": True},
            {"role": "user", "content": "A", "sender": "U\nName"},
            {"role": "assistant", "content": "B"},
        ],
        new_message="最新問題",
    )
    assert "system: 摘要" not in composed
    assert "user[U Name]: A" in composed
    assert composed.endswith("最新問題")

    assert claude_agent._clean_overgenerated_response("ok\nuser: x\nassistant: y") == "ok"
    assert claude_agent._clean_overgenerated_response("") == ""


def test_load_mcp_servers_and_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = claude_agent._load_mcp_servers_from_file(str(tmp_path / "missing.json"))
    assert missing == []

    broken_file = tmp_path / "broken.json"
    broken_file.write_text("{bad json", encoding="utf-8")
    broken = claude_agent._load_mcp_servers_from_file(str(broken_file))
    assert broken == []

    # 準備假的 acp.schema
    acp_mod = types.ModuleType("acp")
    schema_mod = types.ModuleType("acp.schema")

    class _EnvVariable:
        def __init__(self, name: str, value: str) -> None:
            self.name = name
            self.value = value

    class _McpServerStdio:
        def __init__(self, name: str, command: str, args: list, env: list) -> None:
            self.name = name
            self.command = command
            self.args = args
            self.env = env

    class _HttpHeader:
        def __init__(self, name: str, value: str) -> None:
            self.name = name
            self.value = value

    class _HttpMcpServer:
        def __init__(self, name: str, url: str, headers: list, type: str = "http") -> None:
            self.name = name
            self.url = url
            self.headers = headers
            self.type = type

    schema_mod.EnvVariable = _EnvVariable
    schema_mod.McpServerStdio = _McpServerStdio
    schema_mod.HttpMcpServer = _HttpMcpServer
    schema_mod.HttpHeader = _HttpHeader
    monkeypatch.setitem(sys.modules, "acp", acp_mod)
    monkeypatch.setitem(sys.modules, "acp.schema", schema_mod)

    valid_file = tmp_path / "valid.json"
    valid_file.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "ching-tech-os": {
                        "type": "stdio",
                        "command": "python",
                        "args": ["-m", "demo"],
                        "env": {"A": "1"},
                    },
                    "github": {
                        "type": "http",
                        "url": "https://api.githubcopilot.com/mcp/",
                        "headers": {"Authorization": "Bearer test-token"},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    servers = claude_agent._load_mcp_servers_from_file(str(valid_file))
    assert len(servers) == 2
    assert servers[0].name == "ching-tech-os"
    assert servers[0].env[0].name == "A"
    assert servers[1].name == "github"
    assert servers[1].url == "https://api.githubcopilot.com/mcp/"
    assert servers[1].headers[0].name == "Authorization"

    monkeypatch.setattr(
        claude_agent,
        "_load_mcp_servers_from_file",
        lambda _path: [
            SimpleNamespace(name="ching-tech-os"),
            SimpleNamespace(name="external"),
        ],
    )
    all_servers = claude_agent._build_mcp_servers("/tmp/session", None)
    assert len(all_servers) == 2
    filtered = claude_agent._build_mcp_servers("/tmp/session", {"external"})
    assert {s.name for s in filtered} == {"ching-tech-os", "external"}


def test_extends_mcp_merge_respects_enabled_modules_and_hides_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    project_root = tmp_path / "project"
    extends_dir = project_root / "extends"
    enabled_dir = extends_dir / "enabled"
    disabled_dir = extends_dir / "disabled"
    enabled_dir.mkdir(parents=True)
    disabled_dir.mkdir(parents=True)

    secret = "mcp-secret-must-not-be-logged"
    monkeypatch.setenv("TEST_MCP_SECRET", secret)
    monkeypatch.setattr(claude_agent.settings, "project_root", str(project_root))
    monkeypatch.setattr(claude_agent.settings, "extends_dir", str(extends_dir))
    monkeypatch.setitem(claude_agent._MCP_ENV_VARS, "PROJECT_ROOT", str(project_root))
    monkeypatch.setattr(claude_agent, "_extends_mcp_servers", None)
    monkeypatch.setattr(
        modules,
        "is_module_enabled",
        lambda module_id: module_id == "enabled-module",
    )

    (project_root / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "ching-tech-os": {
                        "type": "stdio",
                        "command": "base-command",
                        "args": [],
                    },
                    "shared": {
                        "type": "stdio",
                        "command": "base-wins",
                        "args": [],
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (enabled_dir / "contributes.yaml").write_text(
        """
module_id: enabled-module
mcp_servers:
  shared:
    command: must-not-override
  enabled-http:
    type: http
    url: https://example.test/mcp
    headers:
      Authorization: Bearer ${TEST_MCP_SECRET}
  enabled-stdio:
    command: python
    args:
      - ${PROJECT_ROOT}/server.py
    env:
      SECRET: ${TEST_MCP_SECRET}
""".strip(),
        encoding="utf-8",
    )
    (disabled_dir / "contributes.yaml").write_text(
        """
module_id: disabled-module
mcp_servers:
  disabled-server:
    command: should-not-load
""".strip(),
        encoding="utf-8",
    )

    caplog.set_level("INFO", logger=claude_agent.__name__)
    extends_servers = claude_agent._load_extends_mcp_servers()
    merged = claude_agent._build_merged_mcp_json()["mcpServers"]

    assert set(extends_servers) == {"shared", "enabled-http", "enabled-stdio"}
    assert "disabled-server" not in merged
    assert merged["shared"]["command"] == "base-wins"
    assert merged["enabled-http"]["headers"]["Authorization"] == f"Bearer {secret}"
    assert merged["enabled-stdio"]["args"] == [f"{project_root}/server.py"]
    assert merged["enabled-stdio"]["env"]["SECRET"] == secret
    assert merged["enabled-stdio"]["type"] == "stdio"
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_get_prompt_content_and_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_manager, "get_prompt_by_name", AsyncMock(return_value=None))
    assert await claude_agent.get_prompt_content("missing") is None

    monkeypatch.setattr(
        ai_manager,
        "get_prompt_by_name",
        AsyncMock(return_value={"content": "prompt-body"}),
    )
    assert await claude_agent.get_prompt_content("x") == "prompt-body"

    monkeypatch.setattr(claude_agent, "get_prompt_content", AsyncMock(return_value=None))
    no_prompt = await claude_agent.call_claude_for_summary([{"role": "user", "content": "a"}])
    assert no_prompt.success is False
    assert "找不到 summarizer prompt" in (no_prompt.error or "")
    assert no_prompt.provider == "claude"
    assert no_prompt.actual_model == "haiku"
    assert no_prompt.route_reason == "direct_claude"
    assert no_prompt.provider_started is False

    monkeypatch.setattr(claude_agent, "get_prompt_content", AsyncMock(return_value="summary prompt"))
    call_mock = AsyncMock(
        return_value=claude_agent.ClaudeResponse(success=True, message="摘要完成")
    )
    monkeypatch.setattr(claude_agent, "call_claude", call_mock)
    ok = await claude_agent.call_claude_for_summary([{"role": "user", "content": "a"}], timeout=12)
    assert ok.success is True
    assert call_mock.await_args.kwargs["model"] == "haiku"
    assert call_mock.await_args.kwargs["timeout"] == 12


class _BaseFakeClient:
    def __init__(self, cwd=None, mcp_servers=None, system_prompt=None) -> None:
        self.cwd = cwd
        self.mcp_servers = mcp_servers
        self.system_prompt = system_prompt
        self._on_tool_start = None
        self._on_tool_end = None
        self._on_permission = None
        self._on_tool_input_transform = None
        self._on_result = None
        self._text_buffer = "partial response"
        self.model = None
        self.mode = None
        self.started = False
        self.closed = False

    def on_tool_start(self, fn):
        self._on_tool_start = fn
        return fn

    def on_tool_end(self, fn):
        self._on_tool_end = fn
        return fn

    def on_permission(self, fn):
        self._on_permission = fn
        return fn

    def on_tool_input_transform(self, fn):
        self._on_tool_input_transform = fn
        return fn

    def on_result(self, fn):
        self._on_result = fn
        return fn

    async def start_session(self):
        self.started = True
        return None

    async def set_model(self, model: str):
        self.model = model

    async def set_mode(self, mode: str):
        self.mode = mode

    async def close(self):
        self.closed = True
        return None


class _SuccessClient(_BaseFakeClient):
    async def query(self, _prompt: str):
        if self._on_tool_start:
            await self._on_tool_start("tool-1", "search_knowledge", {"query": "x"})
        if self._on_permission:
            await self._on_permission("search_knowledge", {"query": "x"})
        if self._on_tool_end:
            await self._on_tool_end("tool-1", "ok", {"ok": True})
        if self._on_result:
            await self._on_result({"input_tokens": 11, "output_tokens": 22})
        return "成功回覆\nuser: 不應出現"


class _NanobananaLoopClient(_BaseFakeClient):
    async def query(self, _prompt: str):
        for idx in range(2):
            if self._on_permission:
                allowed = await self._on_permission(
                    "mcp__nanobanana__generate_image",
                    {"prompt": f"p{idx}"},
                )
            else:
                allowed = True
            if not allowed:
                continue
            tool_id = f"nb-{idx}"
            if self._on_tool_start:
                await self._on_tool_start(tool_id, "mcp__nanobanana__generate_image", {"prompt": f"p{idx}"})
            if self._on_tool_end:
                await self._on_tool_end(
                    tool_id,
                    "ok",
                    {"generatedFiles": [f"/tmp/nanobanana-output/{idx}.jpg"]},
                )
        return "圖片完成"


class _CodexImageLoopClient(_BaseFakeClient):
    async def query(self, _prompt: str):
        tool_name = "mcp__ching-tech-os__codex_image_tool"
        for idx in range(2):
            if self._on_permission:
                allowed = await self._on_permission(
                    tool_name,
                    {"prompt": f"p{idx}"},
                )
            else:
                allowed = True
            if not allowed:
                continue
            tool_id = f"codex-image-{idx}"
            if self._on_tool_start:
                await self._on_tool_start(tool_id, tool_name, {"prompt": f"p{idx}"})
            if self._on_tool_end:
                await self._on_tool_end(tool_id, "ok", {"path": f"/tmp/{idx}.png"})
        return "圖片完成"


class _IdentityAndLimitClient(_BaseFakeClient):
    latest: "_IdentityAndLimitClient | None" = None

    def __init__(self, cwd=None, mcp_servers=None, system_prompt=None) -> None:
        super().__init__(cwd=cwd, mcp_servers=mcp_servers, system_prompt=system_prompt)
        self.received_prompt = ""
        self.permission_decisions: list[tuple[str, bool]] = []
        self.transformed_input: dict | None = None
        type(self).latest = self

    async def query(self, prompt: str):
        self.received_prompt = prompt
        assert self._on_permission is not None

        denied = await self._on_permission(
            "mcp__ching-tech-os__add_note",
            {"content": "不應執行"},
        )
        self.permission_decisions.append(("add_note", denied))

        raw_input = {"query": "馬達", "ctos_user_id": 999}
        if self._on_tool_input_transform:
            self.transformed_input = await self._on_tool_input_transform(
                "mcp__ching-tech-os__search_knowledge",
                raw_input,
            )

        first = await self._on_permission(
            "mcp__ching-tech-os__search_knowledge",
            raw_input,
        )
        self.permission_decisions.append(("search_knowledge_1", first))
        if first:
            assert self._on_tool_start is not None
            assert self._on_tool_end is not None
            await self._on_tool_start(
                "search-1",
                "mcp__ching-tech-os__search_knowledge",
                self.transformed_input or raw_input,
            )
            await self._on_tool_end("search-1", "ok", {"items": []})

        second = await self._on_permission(
            "mcp__ching-tech-os__search_knowledge",
            raw_input,
        )
        self.permission_decisions.append(("search_knowledge_2", second))

        if self._on_result:
            await self._on_result({"input_tokens": 7, "output_tokens": 9})
        return "受保護回覆"


class _TimeoutClient(_BaseFakeClient):
    async def query(self, _prompt: str):
        if self._on_tool_start:
            await self._on_tool_start("tool-2", "prepare", {"id": 1})
        raise TimeoutError


class _PartialTimeoutClient(_BaseFakeClient):
    latest: "_PartialTimeoutClient | None" = None

    def __init__(self, cwd=None, mcp_servers=None, system_prompt=None) -> None:
        super().__init__(cwd=cwd, mcp_servers=mcp_servers, system_prompt=system_prompt)
        type(self).latest = self

    async def query(self, _prompt: str):
        if self._on_result:
            await self._on_result({"input_tokens": 31, "output_tokens": 17})
        if self._on_tool_start:
            await self._on_tool_start("done-1", "search_knowledge", {"query": "馬達"})
        if self._on_tool_end:
            await self._on_tool_end("done-1", "ok", {"items": ["結果"]})
        if self._on_tool_start:
            await self._on_tool_start(
                "pending-1",
                "download_web_file",
                {"url": "https://example.test/large.pdf", "query": "規格"},
            )
        self._text_buffer = "已完成的部分內容\nuser: 不應出現"
        await asyncio.sleep(60)
        return "不應完成"


class _CancelledClient(_BaseFakeClient):
    latest: "_CancelledClient | None" = None

    def __init__(self, cwd=None, mcp_servers=None, system_prompt=None) -> None:
        super().__init__(cwd=cwd, mcp_servers=mcp_servers, system_prompt=system_prompt)
        type(self).latest = self

    async def query(self, _prompt: str):
        self._text_buffer = "取消前的部分內容"
        raise asyncio.CancelledError("cancelled by caller")


class _ErrorClient(_BaseFakeClient):
    async def query(self, _prompt: str):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_call_claude_success_timeout_and_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    cleanup_calls: list[str] = []

    monkeypatch.setattr(claude_agent, "_create_session_workdir", lambda: str(session_dir))
    monkeypatch.setattr(
        claude_agent,
        "_cleanup_session_workdir",
        lambda path: cleanup_calls.append(path),
    )
    monkeypatch.setattr(
        claude_agent,
        "_build_mcp_servers",
        lambda _session_dir, _required: [SimpleNamespace(name="ching-tech-os")],
    )

    started: list[str] = []
    ended: list[str] = []

    async def _on_start(name: str, _raw: dict):
        started.append(name)

    async def _on_end(name: str, _raw: dict):
        ended.append(name)

    monkeypatch.setattr(claude_agent, "ClaudeClient", _SuccessClient)
    ok = await claude_agent.call_claude(
        prompt="hello",
        model="claude-opus",
        history=[{"role": "user", "content": "old"}],
        system_prompt="sys",
        tools=["search_knowledge"],
        on_tool_start=_on_start,
        on_tool_end=_on_end,
        required_mcp_servers={"external"},
    )
    assert ok.success is True
    assert ok.message == "成功回覆"
    assert ok.input_tokens == 11
    assert ok.output_tokens == 22
    assert ok.provider == "claude"
    assert ok.actual_model == "opus"
    assert ok.route_reason == "direct_claude"
    assert ok.provider_started is True
    assert len(ok.tool_calls) == 1
    assert started == ["search_knowledge"]
    assert ended == ["search_knowledge"]
    assert cleanup_calls[-1] == str(session_dir)

    monkeypatch.setattr(claude_agent, "ClaudeClient", _TimeoutClient)
    timeout_resp = await claude_agent.call_claude(
        prompt="hello",
        tools=["prepare"],
        timeout=1,
    )
    assert timeout_resp.success is False
    assert "請求超時" in (timeout_resp.error or "")
    assert "prepare" in (timeout_resp.error or "")
    assert timeout_resp.provider == "claude"
    assert timeout_resp.provider_started is True

    monkeypatch.setattr(claude_agent, "ClaudeClient", _ErrorClient)
    err_resp = await claude_agent.call_claude(prompt="hello")
    assert err_resp.success is False
    assert "呼叫 Claude 時發生錯誤" in (err_resp.error or "")
    assert err_resp.provider == "claude"
    assert err_resp.provider_started is True


@pytest.mark.asyncio
async def test_call_claude_timeout_preserves_partial_state_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "timeout-session"
    session_dir.mkdir(parents=True, exist_ok=True)
    cleanup_calls: list[str] = []

    monkeypatch.setattr(claude_agent, "_create_session_workdir", lambda: str(session_dir))
    monkeypatch.setattr(
        claude_agent,
        "_cleanup_session_workdir",
        lambda path: cleanup_calls.append(path),
    )
    monkeypatch.setattr(claude_agent, "_build_mcp_servers", lambda _session_dir, _required: [])
    monkeypatch.setattr(claude_agent, "ClaudeClient", _PartialTimeoutClient)

    result = await claude_agent.call_claude(
        prompt="分析大型文件",
        tools=["search_knowledge", "download_web_file"],
        timeout=0.01,
    )

    client = _PartialTimeoutClient.latest
    assert client is not None
    assert result.success is False
    assert result.message == "已完成的部分內容"
    assert "請求超時" in (result.error or "")
    assert "download_web_file" in (result.error or "")
    assert "url=https://example.test/large.pdf" in (result.error or "")
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search_knowledge"
    assert len(result.tool_timings) == 1
    assert result.input_tokens == 31
    assert result.output_tokens == 17
    assert client.closed is True
    assert cleanup_calls == [str(session_dir)]


@pytest.mark.asyncio
async def test_call_claude_cancel_returns_partial_state_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "cancel-session"
    session_dir.mkdir(parents=True, exist_ok=True)
    cleanup_calls: list[str] = []

    monkeypatch.setattr(claude_agent, "_create_session_workdir", lambda: str(session_dir))
    monkeypatch.setattr(
        claude_agent,
        "_cleanup_session_workdir",
        lambda path: cleanup_calls.append(path),
    )
    monkeypatch.setattr(claude_agent, "ClaudeClient", _CancelledClient)

    result = await claude_agent.call_claude(prompt="取消測試")

    client = _CancelledClient.latest
    assert client is not None
    assert result.success is False
    assert result.message == "取消前的部分內容"
    assert "cancelled by caller" in (result.error or "")
    assert client.closed is True
    assert cleanup_calls == [str(session_dir)]


@pytest.mark.asyncio
async def test_call_claude_limits_nanobanana_calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(claude_agent, "_create_session_workdir", lambda: str(session_dir))
    monkeypatch.setattr(claude_agent, "_cleanup_session_workdir", lambda _path: None)
    monkeypatch.setattr(claude_agent, "_build_mcp_servers", lambda _session_dir, _required: [])
    monkeypatch.setattr(claude_agent.settings, "nanobanana_max_calls_per_request", 1)
    monkeypatch.setattr(claude_agent, "ClaudeClient", _NanobananaLoopClient)

    result = await claude_agent.call_claude(
        prompt="畫圖",
        tools=["mcp__nanobanana__generate_image"],
    )

    assert result.success is True
    # 第二次呼叫會被 permission guard 擋下，避免單回合重複扣費
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "mcp__nanobanana__generate_image"


@pytest.mark.asyncio
async def test_call_claude_limits_codex_image_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(claude_agent, "_create_session_workdir", lambda: str(session_dir))
    monkeypatch.setattr(claude_agent, "_cleanup_session_workdir", lambda _path: None)
    monkeypatch.setattr(claude_agent, "_build_mcp_servers", lambda _session_dir, _required: [])
    monkeypatch.setattr(claude_agent.settings, "codex_image_max_calls_per_request", 1)
    monkeypatch.setattr(claude_agent, "ClaudeClient", _CodexImageLoopClient)

    result = await claude_agent.call_claude(
        prompt="畫圖",
        tools=["mcp__ching-tech-os__codex_image_tool"],
    )

    assert result.success is True
    # 第二次呼叫會被全域上限擋下，避免單回合持續微調而增加成本
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "mcp__ching-tech-os__codex_image_tool"


@pytest.mark.asyncio
async def test_call_claude_preserves_identity_whitelist_limits_and_callback_isolation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    server = SimpleNamespace(name="ching-tech-os", env=[])
    required_calls: list[set[str] | None] = []

    monkeypatch.setattr(claude_agent, "_create_session_workdir", lambda: str(session_dir))
    monkeypatch.setattr(claude_agent, "_cleanup_session_workdir", lambda _path: None)

    def _build_servers(_session_dir: str, required: set[str] | None):
        required_calls.append(required)
        return [server]

    monkeypatch.setattr(claude_agent, "_build_mcp_servers", _build_servers)
    monkeypatch.setattr(claude_agent, "ClaudeClient", _IdentityAndLimitClient)

    async def _failing_start(_name: str, _raw: dict) -> None:
        raise RuntimeError("start callback boom")

    async def _failing_end(_name: str, _raw: dict) -> None:
        raise RuntimeError("end callback boom")

    caplog.set_level("WARNING", logger=claude_agent.__name__)
    result = await claude_agent.call_claude(
        prompt="最新問題",
        model="claude-opus",
        history=[{"role": "user", "content": "先前問題"}],
        system_prompt="系統提示",
        tools=["mcp__ching-tech-os__search_knowledge"],
        tool_call_limits={"mcp__ching-tech-os__search_knowledge": 1},
        on_tool_start=_failing_start,
        on_tool_end=_failing_end,
        required_mcp_servers={"external"},
        ctos_user_id=123,
        extra_mcp_env={"CTOS_GROUP_ID": "group-1"},
    )

    client = _IdentityAndLimitClient.latest
    assert client is not None
    assert result.success is True
    assert result.message == "受保護回覆"
    assert result.input_tokens == 7
    assert result.output_tokens == 9
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].input["ctos_user_id"] == 123
    assert client.transformed_input == {
        "query": "馬達",
        "ctos_user_id": 123,
    }
    assert client.permission_decisions == [
        ("add_note", False),
        ("search_knowledge_1", True),
        ("search_knowledge_2", False),
    ]
    assert client.started is True
    assert client.closed is True
    assert client.model == "opus"
    assert client.mode == "bypassPermissions"
    assert client.system_prompt == "系統提示"
    assert "user: 先前問題" in client.received_prompt
    assert client.received_prompt.endswith("最新問題")
    assert required_calls == [{"external"}]
    assert {(item.name, item.value) for item in server.env} == {
        ("CTOS_USER_ID", "123"),
        ("CTOS_GROUP_ID", "group-1"),
    }
    assert "on_tool_start callback 失敗" in caplog.text
    assert "on_tool_end callback 失敗" in caplog.text
