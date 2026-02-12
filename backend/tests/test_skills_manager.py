"""skills manager 測試。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ching_tech_os.skills import (
    SkillManager,
    _build_skill,
    _extract_ctos_metadata,
    _parse_allowed_tools,
    _parse_mcp_servers,
    _parse_skill_md,
    _validate_skill_name,
)


def _write_skill_md(skill_dir: Path, frontmatter: str, body: str = "prompt") -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")


def test_skills_parsers_and_builder(tmp_path: Path) -> None:
    fm, body = _parse_skill_md("---\nname: demo\n---\n\nhello")
    assert fm["name"] == "demo"
    assert body == "hello"
    assert _parse_skill_md("plain")[0] == {}
    assert _parse_allowed_tools("a b") == ["a", "b"]
    assert _parse_allowed_tools(["x"]) == ["x"]
    assert _parse_mcp_servers("m1 m2") == ["m1", "m2"]
    assert _extract_ctos_metadata({"metadata": {"ctos": {"requires_app": "file", "mcp_servers": "a b"}}}) == ("file", ["a", "b"])
    assert _validate_skill_name("demo-1") == "demo-1"
    with pytest.raises(ValueError):
        _validate_skill_name("BadName")

    sd = tmp_path / "demo"
    (sd / "references").mkdir(parents=True)
    (sd / "references" / "r.md").write_text("r", encoding="utf-8")
    skill = _build_skill(
        {"description": "d", "allowed-tools": "t1 t2", "metadata": {"ctos": {"requires_app": "file"}}},
        "prompt",
        sd,
        source="native",
    )
    assert skill.name == "demo"
    assert skill.allowed_tools == ["t1", "t2"]
    assert skill.references == ["references/r.md"]


@pytest.mark.asyncio
async def test_skill_manager_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    native = tmp_path / "native"
    external = tmp_path / "external"
    native.mkdir(parents=True, exist_ok=True)
    external.mkdir(parents=True, exist_ok=True)

    # external demo (覆蓋 native)
    _write_skill_md(
        external / "demo",
        (
            "description: ext demo\n"
            "allowed-tools: \"tool.a tool.b\"\n"
            "metadata:\n"
            "  ctos:\n"
            "    requires_app: file-manager\n"
            "    mcp_servers: \"s1 s2\"\n"
            "  openclaw:\n"
            "    requires:\n"
            "      env: [TEST_ENV, SECRET_KEY]\n"
            "    primaryEnv: PRIMARY_ENV\n"
        ),
        body="external prompt",
    )
    (external / "demo" / "scripts").mkdir()
    (external / "demo" / "scripts" / "run.py").write_text("print(1)", encoding="utf-8")
    (external / "demo" / "assets").mkdir()
    (external / "demo" / "assets" / "a.txt").write_text("a", encoding="utf-8")
    (external / "demo" / "references").mkdir()
    (external / "demo" / "references" / "ref.md").write_text("ref", encoding="utf-8")

    # native demo（應被 external 保留）
    _write_skill_md(native / "demo", "description: native demo\nallowed-tools: \"native.tool\"")

    # native yaml fallback
    n2 = native / "native2"
    n2.mkdir(parents=True, exist_ok=True)
    (n2 / "skill.yaml").write_text("description: yaml skill\ntools:\n  - y1\n", encoding="utf-8")
    (n2 / "prompt.md").write_text("yaml prompt", encoding="utf-8")

    # 關閉 seed
    import ching_tech_os.skills.seed_external as seed_external
    monkeypatch.setattr(seed_external, "ensure_seed_skills", lambda _p: None)

    mgr = SkillManager(skills_dir=native, external_skills_dir=external)
    await mgr.load_skills()

    s = await mgr.get_skill("demo")
    assert s is not None and s.description == "ext demo"
    assert (await mgr.get_skill("missing")) is None
    assert len(await mgr.get_all_skills()) >= 2
    assert await mgr.get_skill_dir("demo") == external / "demo"

    # 權限過濾 + prompt/tools/servers
    allowed = await mgr.get_skills_for_user({"file-manager": True})
    denied = await mgr.get_skills_for_user({"file-manager": False})
    assert any(x.name == "demo" for x in allowed)
    assert all(x.name != "demo" for x in denied)
    assert "external prompt" in await mgr.generate_tools_prompt({"file-manager": True})
    assert "tool.a" in await mgr.get_tool_names({"file-manager": True})
    assert "s1" in await mgr.get_required_mcp_servers({"file-manager": True})

    # script/file/reference
    assert await mgr.has_scripts("demo") is True
    assert await mgr.has_scripts("missing") is False
    script_path = await mgr.get_script_path("demo", "run")
    assert script_path and script_path.name == "run.py"
    assert await mgr.get_script_path("demo", "../bad") is None
    assert await mgr.get_skill_file("demo", "references/ref.md") == "ref"
    assert await mgr.get_skill_file("demo", "bad/path") is None
    assert await mgr.get_skill_reference("demo", "ref.md") == "ref"

    # scripts info
    import ching_tech_os.skills.script_runner as sr
    monkeypatch.setattr(sr.ScriptRunner, "list_scripts", lambda self, name: [{"name": "run"}])
    assert (await mgr.get_scripts_info("demo"))[0]["name"] == "run"
    assert "demo" in await mgr.get_all_script_skills()

    # fallback map + env
    fmap = await mgr.get_script_fallback_map("demo")
    assert fmap == {}
    monkeypatch.setenv("TEST_ENV", "ok")
    monkeypatch.setenv("PRIMARY_ENV", "p")
    envs = mgr.get_skill_env_overrides(s)
    assert envs["TEST_ENV"] == "ok"
    assert envs["PRIMARY_ENV"] == "p"
    assert "SECRET_KEY" not in envs

    # update metadata
    ok = await mgr.update_skill_metadata(
        "demo",
        requires_app="nas",
        allowed_tools=["x", "y"],
        mcp_servers=["m"],
    )
    assert ok is True
    ok2 = await mgr.update_skill_metadata("missing", requires_app="x")
    assert ok2 is False

    # import openclaw
    src = tmp_path / "openclaw"
    _write_skill_md(src, "name: imported\ndescription: imported skill\nmetadata: {}\n", body="b")
    (src / "references").mkdir()
    (src / "references" / "a.md").write_text("x", encoding="utf-8")
    dest = mgr.import_openclaw_skill(src)
    assert dest.exists()

    # remove + reload
    assert await mgr.remove_skill("demo") is True
    assert await mgr.remove_skill("missing") is False
    count = await mgr.reload_skills()
    assert isinstance(count, int)

    # path-root guard
    assert mgr._is_within_skill_roots(external / "demo" / "SKILL.md") is True
    assert mgr._is_within_skill_roots(tmp_path / "outside.txt") is False
