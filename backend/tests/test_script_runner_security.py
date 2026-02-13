"""Script runner 安全性測試。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from ching_tech_os.skills import script_runner as script_runner_module
from ching_tech_os.skills.script_runner import ScriptRunner


def test_validate_names_parse_docstring_and_list_scripts(tmp_path: Path) -> None:
    runner = ScriptRunner(tmp_path)
    runner._validate_names("demo-skill", "run_script")

    with pytest.raises(ValueError):
        runner._validate_names("", "run_script")
    with pytest.raises(ValueError):
        runner._validate_names("bad/name", "run_script")
    with pytest.raises(ValueError):
        runner._validate_names("demo", "bad.name")

    py_script = tmp_path / "doc.py"
    py_script.write_text('"""第一行\n第二行"""\nprint("ok")\n', encoding="utf-8")
    assert runner._parse_docstring(py_script) == "第一行"

    bad_py = tmp_path / "bad.py"
    bad_py.write_text("def broken(:\n    pass\n", encoding="utf-8")
    assert runner._parse_docstring(bad_py) == ""

    sh_script = tmp_path / "doc.sh"
    sh_script.write_text("#!/bin/bash\n# Description: shell 腳本\necho ok\n", encoding="utf-8")
    assert runner._parse_docstring(sh_script) == "shell 腳本"
    assert runner._parse_docstring(tmp_path / "missing.py") == ""

    scripts_dir = tmp_path / "demo-skill" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "run.py").write_text('"""python 腳本"""\nprint("ok")\n', encoding="utf-8")
    (scripts_dir / "deploy.sh").write_text("# Description: deploy\necho ok\n", encoding="utf-8")
    (scripts_dir / "skip.txt").write_text("ignore", encoding="utf-8")

    outside = tmp_path / "outside.py"
    outside.write_text('"""outside"""\n', encoding="utf-8")
    (scripts_dir / "escape.py").symlink_to(outside)

    result_names = {item["name"] for item in runner.list_scripts("demo-skill")}
    assert result_names == {"deploy", "run"}
    assert runner.list_scripts("bad/name") == []
    assert runner.list_scripts("missing") == []


def test_build_command_variants(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = ScriptRunner(tmp_path)
    py_script = tmp_path / "run.py"
    sh_script = tmp_path / "run.sh"
    txt_script = tmp_path / "run.txt"

    monkeypatch.setattr(script_runner_module.shutil, "which", lambda _cmd: "/usr/bin/uv")
    assert runner._build_command(py_script) == ["uv", "run", str(py_script)]

    monkeypatch.setattr(script_runner_module.shutil, "which", lambda _cmd: None)
    assert runner._build_command(py_script) == ["python3", str(py_script)]
    assert runner._build_command(sh_script) == ["bash", str(sh_script)]
    assert runner._build_command(txt_script) is None


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


@pytest.mark.asyncio
async def test_execute_path_unsupported_timeout_and_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = ScriptRunner(tmp_path)

    unsupported = tmp_path / "demo.txt"
    unsupported.write_text("demo", encoding="utf-8")
    unsupported_result = await runner.execute_path(
        script_path=unsupported,
        skill_name="demo",
    )
    assert unsupported_result["success"] is False
    assert "Unsupported script type" in unsupported_result["error"]

    script_path = tmp_path / "demo.py"
    script_path.write_text("print('ok')", encoding="utf-8")
    monkeypatch.setattr(runner, "_build_command", lambda _path: ["python3", "-c", "print('ok')"])

    class _TimeoutProc:
        returncode = 0

        def __init__(self) -> None:
            self.killed = False

        async def communicate(self, input=None):
            return b"", b""

        def kill(self):
            self.killed = True

    timeout_proc = _TimeoutProc()

    async def _fake_subprocess_exec(*_args, **_kwargs):
        return timeout_proc

    async def _raise_timeout(awaitable, timeout):
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subprocess_exec)
    monkeypatch.setattr(asyncio, "wait_for", _raise_timeout)
    timeout_result = await runner.execute_path(
        script_path=script_path,
        skill_name="demo",
        timeout=1,
    )
    assert timeout_result["success"] is False
    assert "timed out" in timeout_result["error"]
    assert timeout_proc.killed is True

    async def _raise_runtime_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _raise_runtime_error)
    exception_result = await runner.execute_path(
        script_path=script_path,
        skill_name="demo",
    )
    assert exception_result["success"] is False
    assert exception_result["error"] == "boom"
