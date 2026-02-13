"""claude_agent 服務測試。"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services import claude_agent


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

    schema_mod.EnvVariable = _EnvVariable
    schema_mod.McpServerStdio = _McpServerStdio
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
                    "skip-http": {"type": "http"},
                }
            }
        ),
        encoding="utf-8",
    )
    servers = claude_agent._load_mcp_servers_from_file(str(valid_file))
    assert len(servers) == 1
    assert servers[0].name == "ching-tech-os"
    assert servers[0].env[0].name == "A"

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


@pytest.mark.asyncio
async def test_get_prompt_content_and_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(claude_agent.ai_manager, "get_prompt_by_name", AsyncMock(return_value=None))
    assert await claude_agent.get_prompt_content("missing") is None

    monkeypatch.setattr(
        claude_agent.ai_manager,
        "get_prompt_by_name",
        AsyncMock(return_value={"content": "prompt-body"}),
    )
    assert await claude_agent.get_prompt_content("x") == "prompt-body"

    monkeypatch.setattr(claude_agent, "get_prompt_content", AsyncMock(return_value=None))
    no_prompt = await claude_agent.call_claude_for_summary([{"role": "user", "content": "a"}])
    assert no_prompt.success is False
    assert "找不到 summarizer prompt" in (no_prompt.error or "")

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
        self._on_result = None
        self._text_buffer = "partial response"
        self.model = None
        self.mode = None

    def on_tool_start(self, fn):
        self._on_tool_start = fn
        return fn

    def on_tool_end(self, fn):
        self._on_tool_end = fn
        return fn

    def on_permission(self, fn):
        self._on_permission = fn
        return fn

    def on_result(self, fn):
        self._on_result = fn
        return fn

    async def start_session(self):
        return None

    async def set_model(self, model: str):
        self.model = model

    async def set_mode(self, mode: str):
        self.mode = mode

    async def close(self):
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


class _TimeoutClient(_BaseFakeClient):
    async def query(self, _prompt: str):
        if self._on_tool_start:
            await self._on_tool_start("tool-2", "prepare", {"id": 1})
        raise TimeoutError


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

    monkeypatch.setattr(claude_agent, "ClaudeClient", _ErrorClient)
    err_resp = await claude_agent.call_claude(prompt="hello")
    assert err_resp.success is False
    assert "呼叫 Claude 時發生錯誤" in (err_resp.error or "")
