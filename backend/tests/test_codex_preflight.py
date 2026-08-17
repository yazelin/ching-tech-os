"""Codex 部署 preflight 測試：binary、版本、service user、auth storage、headless 與 handshake。"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest

from ching_tech_os.config import settings
from ching_tech_os.services import codex_preflight


PINNED_ADAPTER_VERSION = "1.1.9"
PINNED_CODEX_VERSION = "0.146.0"


@pytest.fixture
def preflight_env(tmp_path, monkeypatch):
    """建立假 binary、auth storage 與 pin 版 package.json 的隔離環境。"""
    adapter = tmp_path / "codex-acp"
    adapter.write_text("#!/bin/sh\n", encoding="utf-8")
    adapter.chmod(0o755)
    codex = tmp_path / "codex"
    codex.write_text("#!/bin/sh\n", encoding="utf-8")
    codex.chmod(0o755)

    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"secret": "not-logged"}', encoding="utf-8")

    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "dependencies": {
                    "@agentclientprotocol/codex-acp": PINNED_ADAPTER_VERSION,
                    "@openai/codex": PINNED_CODEX_VERSION,
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "codex_acp_bin_path", str(adapter))
    monkeypatch.setattr(settings, "codex_bin_path", str(codex))
    monkeypatch.setattr(settings, "codex_home", str(codex_home))
    monkeypatch.setattr(settings, "project_root", str(tmp_path))
    return tmp_path


async def _fake_version_runner(binary: str, timeout: float) -> str:
    if "codex-acp" in binary:
        return f"@agentclientprotocol/codex-acp {PINNED_ADAPTER_VERSION}"
    return f"codex-cli {PINNED_CODEX_VERSION}"


class FakeHandshakeClient:
    """成功完成 connect/new_session/disconnect 的最小 ACP client。"""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.disconnected = False

    async def connect(self) -> None:
        return None

    async def new_session(self) -> str:
        return "session-1"

    async def disconnect(self) -> None:
        self.disconnected = True


def _check(report: codex_preflight.PreflightReport, name: str) -> codex_preflight.PreflightCheck:
    for check in report.checks:
        if check.name == name:
            return check
    raise AssertionError(f"preflight 缺少 {name} 檢查")


@pytest.mark.asyncio
async def test_preflight_all_checks_pass(preflight_env) -> None:
    report = await codex_preflight.run_preflight(
        version_runner=_fake_version_runner,
        client_factory=FakeHandshakeClient,
    )
    assert report.passed is True
    for name in (
        "adapter_binary",
        "codex_binary",
        "adapter_version",
        "codex_version",
        "service_user",
        "auth_storage",
        "headless_env",
        "handshake",
    ):
        assert _check(report, name).passed is True, name


@pytest.mark.asyncio
async def test_preflight_missing_adapter_binary_skips_handshake(
    preflight_env, monkeypatch
) -> None:
    monkeypatch.setattr(
        settings, "codex_acp_bin_path", str(preflight_env / "missing-bin")
    )
    handshake_started = False

    class TrackingClient(FakeHandshakeClient):
        def __init__(self, **kwargs: Any) -> None:
            nonlocal handshake_started
            handshake_started = True
            super().__init__(**kwargs)

    report = await codex_preflight.run_preflight(
        version_runner=_fake_version_runner,
        client_factory=TrackingClient,
    )
    assert report.passed is False
    assert _check(report, "adapter_binary").passed is False
    assert _check(report, "adapter_version").passed is False
    assert _check(report, "handshake").passed is False
    assert "略過" in _check(report, "handshake").detail
    assert handshake_started is False


@pytest.mark.asyncio
async def test_preflight_version_mismatch_fails(preflight_env) -> None:
    async def stale_version_runner(binary: str, timeout: float) -> str:
        if "codex-acp" in binary:
            return "@agentclientprotocol/codex-acp 1.0.0"
        return f"codex-cli {PINNED_CODEX_VERSION}"

    report = await codex_preflight.run_preflight(
        version_runner=stale_version_runner,
        client_factory=FakeHandshakeClient,
    )
    check = _check(report, "adapter_version")
    assert check.passed is False
    assert PINNED_ADAPTER_VERSION in check.detail
    assert _check(report, "codex_version").passed is True


@pytest.mark.asyncio
async def test_preflight_rejects_root_service_user(preflight_env, monkeypatch) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    report = await codex_preflight.run_preflight(
        version_runner=_fake_version_runner,
        client_factory=FakeHandshakeClient,
    )
    assert _check(report, "service_user").passed is False


@pytest.mark.asyncio
async def test_preflight_missing_auth_storage_skips_handshake(
    preflight_env, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "codex_home", str(preflight_env / "no-such-home"))
    report = await codex_preflight.run_preflight(
        version_runner=_fake_version_runner,
        client_factory=FakeHandshakeClient,
    )
    auth_check = _check(report, "auth_storage")
    assert auth_check.passed is False
    assert _check(report, "handshake").passed is False
    # 不得洩漏 auth 檔內容
    assert "not-logged" not in json.dumps(report.as_dict())


@pytest.mark.asyncio
async def test_preflight_headless_env_includes_codex_home(preflight_env) -> None:
    report = await codex_preflight.run_preflight(
        version_runner=_fake_version_runner,
        client_factory=FakeHandshakeClient,
    )
    check = _check(report, "headless_env")
    assert check.passed is True

    # provider 實際 spawn 的 env 必須帶 NO_BROWSER=1 與明確 CODEX_HOME
    from ching_tech_os.services.codex_agent import CodexProvider

    env = CodexProvider()._client_env(settings.codex_bin_path)
    assert env["NO_BROWSER"] == "1"
    assert env["CODEX_HOME"] == settings.codex_home


@pytest.mark.asyncio
async def test_preflight_handshake_failure_uses_safe_category(preflight_env) -> None:
    class AuthFailClient(FakeHandshakeClient):
        async def connect(self) -> None:
            raise RuntimeError("unauthorized: token=sk-secret-123 login required")

    report = await codex_preflight.run_preflight(
        version_runner=_fake_version_runner,
        client_factory=AuthFailClient,
    )
    check = _check(report, "handshake")
    assert check.passed is False
    assert check.detail == "auth_error"
    assert "sk-secret-123" not in json.dumps(report.as_dict())


@pytest.mark.asyncio
async def test_preflight_handshake_timeout(preflight_env) -> None:
    class SlowClient(FakeHandshakeClient):
        async def connect(self) -> None:
            await asyncio.sleep(5)

    report = await codex_preflight.run_preflight(
        version_runner=_fake_version_runner,
        client_factory=SlowClient,
        handshake_timeout=0.05,
    )
    check = _check(report, "handshake")
    assert check.passed is False
    assert check.detail == "timeout"


@pytest.mark.asyncio
async def test_preflight_handshake_always_disconnects(preflight_env) -> None:
    created: list[FakeHandshakeClient] = []

    class SessionFailClient(FakeHandshakeClient):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            created.append(self)

        async def new_session(self) -> str:
            raise RuntimeError("protocol initialize error")

    report = await codex_preflight.run_preflight(
        version_runner=_fake_version_runner,
        client_factory=SessionFailClient,
    )
    assert _check(report, "handshake").passed is False
    assert created and created[0].disconnected is True


@pytest.mark.asyncio
async def test_preflight_version_runner_failure_is_safe(preflight_env) -> None:
    async def broken_runner(binary: str, timeout: float) -> str:
        raise OSError("spawn failed: /etc/shadow secret")

    report = await codex_preflight.run_preflight(
        version_runner=broken_runner,
        client_factory=FakeHandshakeClient,
    )
    check = _check(report, "adapter_version")
    assert check.passed is False
    assert "secret" not in json.dumps(report.as_dict())


@pytest.fixture
def _preserve_event_loop():
    """main() 內的 asyncio.run() 會清掉主執行緒 current loop；還原避免影響其他測試。"""
    policy = asyncio.get_event_loop_policy()
    try:
        previous = policy.get_event_loop()
    except RuntimeError:
        previous = None
    yield
    asyncio.set_event_loop(previous)


def test_preflight_main_exit_codes(
    preflight_env, capsys, monkeypatch, _preserve_event_loop
) -> None:
    async def fake_run_preflight(**kwargs: Any) -> codex_preflight.PreflightReport:
        return codex_preflight.PreflightReport(
            checks=(codex_preflight.PreflightCheck("adapter_binary", True, "ok"),)
        )

    monkeypatch.setattr(codex_preflight, "run_preflight", fake_run_preflight)
    assert codex_preflight.main([]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["passed"] is True

    async def failing_run_preflight(**kwargs: Any) -> codex_preflight.PreflightReport:
        return codex_preflight.PreflightReport(
            checks=(codex_preflight.PreflightCheck("adapter_binary", False, "bad"),)
        )

    monkeypatch.setattr(codex_preflight, "run_preflight", failing_run_preflight)
    assert codex_preflight.main([]) == 1


def test_preflight_main_skip_handshake_flag(
    preflight_env, capsys, monkeypatch, _preserve_event_loop
) -> None:
    captured_kwargs: dict[str, Any] = {}

    async def fake_run_preflight(**kwargs: Any) -> codex_preflight.PreflightReport:
        captured_kwargs.update(kwargs)
        return codex_preflight.PreflightReport(checks=())

    monkeypatch.setattr(codex_preflight, "run_preflight", fake_run_preflight)
    assert codex_preflight.main(["--skip-handshake"]) == 0
    assert captured_kwargs.get("include_handshake") is False
