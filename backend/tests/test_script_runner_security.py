"""Script runner 安全性測試。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from ching_tech_os.skills.script_runner import ScriptRunner


@pytest.mark.asyncio
async def test_execute_path_blocks_protected_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = ScriptRunner(tmp_path)
    script_path = tmp_path / "demo.py"
    script_path.write_text("print('ok')", encoding="utf-8")
    monkeypatch.setattr(runner, "_build_command", lambda _path: ["python3", "-c", "print('ok')"])

    captured: dict = {}

    class _Proc:
        returncode = 0

        async def communicate(self, input=None):
            return b"OK", b""

        def kill(self):
            return None

    async def _fake_subprocess_exec(*_args, **kwargs):
        captured["env"] = kwargs["env"]
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subprocess_exec)

    result = await runner.execute_path(
        script_path=script_path,
        skill_name="demo",
        env_overrides={
            "PATH": "/tmp/hijack",
            "HOME": "/tmp/home-hijack",
            "LD_PRELOAD": "/tmp/preload.so",
            "LD_LIBRARY_PATH": "/tmp/lib",
            "PYTHONPATH": "/tmp/python-hijack",
            "SAFE_TOKEN": "abc123",
            "path": "/tmp/lowercase-hijack",
        },
    )

    assert result["success"] is True
    env = captured["env"]
    assert env["PATH"] == os.environ.get("PATH", "")
    assert env["HOME"] == os.environ.get("HOME", "")
    assert "LD_PRELOAD" not in env
    assert "LD_LIBRARY_PATH" not in env
    assert "lowercase-hijack" not in env["PATH"]
    assert "python-hijack" not in env["PYTHONPATH"]
    assert env["SAFE_TOKEN"] == "abc123"
