"""skills API 路由測試。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ching_tech_os.api import skills as skills_api


class _FakeSkill:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = "desc"
        self.requires_app = None
        self.allowed_tools = ["a"]
        self.prompt = "p"
        self.references = []
        self.scripts = []
        self.assets = []
        self.source = "clawhub"
        self.license = "MIT"
        self.compatibility = {}
        self.metadata = {}
        self.mcp_servers = []


class _FakeSkillManager:
    def __init__(self, base: Path) -> None:
        self.skills_dir = base
        self._skills: dict[str, _FakeSkill] = {"demo": _FakeSkill("demo")}

    async def get_all_skills(self):
        return list(self._skills.values())

    async def get_skill(self, name: str):
        return self._skills.get(name)

    async def get_scripts_info(self, _name: str):
        return []

    async def get_skill_dir(self, name: str):
        p = self.skills_dir / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    async def update_skill_metadata(self, name: str, **_kwargs):
        return name in self._skills

    async def remove_skill(self, name: str):
        return self._skills.pop(name, None) is not None

    async def reload_skills(self):
        return len(self._skills)

    async def get_skill_file(self, _name: str, file_path: str):
        return "content" if file_path == "ok.txt" else None

    async def get_skill_reference(self, _name: str, ref_path: str):
        return "ref" if ref_path == "ok.md" else None


class _FakeClient:
    def __init__(self, source: str) -> None:
        self.source = source

    async def search(self, query: str):
        return [{"slug": f"{self.source}-{query}", "source": self.source}]

    async def get_skill(self, slug: str):
        return {
            "skill": {"name": slug, "description": "d", "tags": ["x"]},
            "owner": {"handle": "ct"},
            "latestVersion": {"version": "1.0.0"},
        }

    async def extract_file_from_zip(self, _slug: str, _version: str, _filename: str):
        return "# SKILL"

    async def download_and_extract(self, _slug: str, _version: str, dest: Path):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text("# demo", encoding="utf-8")

    def write_meta(self, dest: Path, slug: str, version: str, owner: str):
        (dest / "_meta.json").write_text(
            json.dumps({"slug": slug, "version": version, "owner": owner}),
            encoding="utf-8",
        )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(skills_api.router)
    app.dependency_overrides[skills_api.require_admin] = lambda: SimpleNamespace(username="admin", role="admin", user_id=1)
    app.state.clawhub_client = _FakeClient("clawhub")
    app.state.skillhub_client = _FakeClient("skillhub")
    return app


@pytest.mark.asyncio
async def test_skills_route_basics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _build_app()
    transport = ASGITransport(app=app)
    sm = _FakeSkillManager(tmp_path / "skills")

    monkeypatch.setattr(skills_api, "get_skill_manager", lambda: sm)
    monkeypatch.setattr(skills_api, "skillhub_enabled", lambda: True)
    monkeypatch.setattr(skills_api, "read_meta", lambda _p: {"source": "clawhub"})

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/skills/hub/sources")).status_code == 200
        assert (await client.get("/api/skills")).status_code == 200
        assert (await client.get("/api/skills/demo")).status_code == 200
        assert (await client.get("/api/skills/demo/meta")).status_code == 200

        # update
        resp = await client.put("/api/skills/demo", json={"allowed_tools": ["x"]})
        assert resp.status_code == 200
        resp = await client.put("/api/skills/demo", json={})
        assert resp.status_code == 400

        # file/ref
        assert (await client.get("/api/skills/demo/files/ok.txt")).status_code == 200
        assert (await client.get("/api/skills/demo/files/missing.txt")).status_code == 404
        assert (await client.get("/api/skills/demo/references/ok.md")).status_code == 200
        assert (await client.get("/api/skills/demo/references/missing.md")).status_code == 404

        # reload & delete
        assert (await client.post("/api/skills/reload")).status_code == 200
        assert (await client.delete("/api/skills/demo")).status_code == 200
        assert (await client.delete("/api/skills/demo")).status_code == 404


@pytest.mark.asyncio
async def test_skills_hub_search_inspect_and_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _build_app()
    transport = ASGITransport(app=app)
    sm = _FakeSkillManager(tmp_path / "skills")
    sm._skills = {}  # install 測試需要未安裝

    monkeypatch.setattr(skills_api, "get_skill_manager", lambda: sm)
    monkeypatch.setattr(skills_api, "skillhub_enabled", lambda: True)
    monkeypatch.setattr(skills_api, "validate_slug", lambda s: not s.startswith("!"))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # hub search 指定來源
        resp = await client.post("/api/skills/hub/search", json={"query": "demo", "source": "clawhub"})
        assert resp.status_code == 200

        # hub search 雙來源
        resp = await client.post("/api/skills/hub/search", json={"query": "demo"})
        assert resp.status_code == 200

        # hub inspect
        resp = await client.post("/api/skills/hub/inspect", json={"slug": "demo", "source": "clawhub"})
        assert resp.status_code == 200

        # invalid slug
        resp = await client.post("/api/skills/hub/inspect", json={"slug": "!bad", "source": "clawhub"})
        assert resp.status_code == 400

        # hub install success
        resp = await client.post("/api/skills/hub/install", json={"name": "demo", "source": "clawhub"})
        assert resp.status_code == 200

        # install again -> conflict
        sm._skills["demo"] = _FakeSkill("demo")
        resp = await client.post("/api/skills/hub/install", json={"name": "demo", "source": "clawhub"})
        assert resp.status_code == 409


def test_skills_helper_functions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # _flatten_single_subdir
    dest = tmp_path / "skill"
    nested = dest / "nested"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "a.txt").write_text("x", encoding="utf-8")
    skills_api._flatten_single_subdir(dest)
    assert (dest / "a.txt").exists()

    # _ensure_skill_md_frontmatter
    skill_md = tmp_path / "SKILL.md"
    skills_api._ensure_skill_md_frontmatter(
        skill_md,
        "demo",
        {"skill": {"name": "Demo", "description": "Desc", "tags": ["a"]}},
        "clawhub",
    )
    assert "name: demo" in skill_md.read_text(encoding="utf-8")

    # 已有 frontmatter（修正 name/source）
    skill_md.write_text("---\nname: old\n---\n\nbody", encoding="utf-8")
    skills_api._ensure_skill_md_frontmatter(
        skill_md,
        "new-demo",
        {"skill": {"name": "Demo", "description": "Desc"}},
        "skillhub",
    )
    text = skill_md.read_text(encoding="utf-8")
    assert "name: new-demo" in text

    # _get_clients / _get_client_for_source
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(clawhub_client=_FakeClient("clawhub"), skillhub_client=_FakeClient("skillhub"))))
    monkeypatch.setattr(skills_api, "get_clawhub_client_di", lambda req: req.app.state.clawhub_client)
    monkeypatch.setattr(skills_api, "get_skillhub_client_di", lambda req: req.app.state.skillhub_client)
    monkeypatch.setattr(skills_api, "skillhub_enabled", lambda: True)
    clients = skills_api._get_clients(request)
    assert {c[0] for c in clients} == {"clawhub", "skillhub"}

    monkeypatch.setattr(skills_api, "skillhub_enabled", lambda: False)
    assert isinstance(skills_api._get_client_for_source(request, "clawhub"), _FakeClient)
    with pytest.raises(Exception):
        skills_api._get_client_for_source(request, "skillhub")
