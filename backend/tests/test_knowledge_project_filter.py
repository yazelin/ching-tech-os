"""知識庫 project_id 過濾測試。

`project` 參數是 tags 裡的專案名稱，`project_id` 是 scope=project 條目的專案 UUID，
兩者是不同的東西，不能混。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ching_tech_os.models.knowledge import KnowledgeCreate, KnowledgeTags
from ching_tech_os.services import knowledge

PID_A = str(uuid4())
PID_B = str(uuid4())


def _setup_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base = tmp_path / "knowledge"
    entries = base / "entries"
    assets = base / "assets"
    index = base / "index.json"
    entries.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(knowledge, "_get_paths", lambda: (base, entries, assets, index))


def _create(title: str, project_id: str | None, project_tag: str | None = None):
    return knowledge.create_knowledge(
        KnowledgeCreate(
            title=title,
            content="內容",
            scope="project" if project_id else "global",
            project_id=project_id,
            tags=KnowledgeTags(projects=[project_tag] if project_tag else []),
        ),
        project_id=project_id,
    )


def test_search_filters_by_project_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _setup_paths(monkeypatch, tmp_path)
    _create("A 案紀錄", PID_A)
    _create("A 案第二筆", PID_A)
    _create("B 案紀錄", PID_B)
    _create("全域筆記", None)

    only_a = knowledge.search_knowledge(scope="project", project_id=PID_A)
    assert only_a.total == 2
    assert {i.project_id for i in only_a.items} == {PID_A}

    only_b = knowledge.search_knowledge(scope="project", project_id=PID_B)
    assert only_b.total == 1

    # 不給 project_id 時這條過濾不生效（scope="project" 本來就不篩 scope，是既有行為）
    assert knowledge.search_knowledge(scope="project").total == 4

    # 不存在的專案：空結果
    assert knowledge.search_knowledge(scope="project", project_id=str(uuid4())).total == 0


def test_project_id_is_not_project_tag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """project（tags 裡的名稱）與 project_id（UUID）互不相干"""
    _setup_paths(monkeypatch, tmp_path)
    _create("掛名稱標籤", None, project_tag="擎添廠內")
    _create("掛 UUID", PID_A)

    by_tag = knowledge.search_knowledge(project="擎添廠內")
    assert by_tag.total == 1
    assert by_tag.items[0].title == "掛名稱標籤"

    by_id = knowledge.search_knowledge(project_id=PID_A)
    assert by_id.total == 1
    assert by_id.items[0].title == "掛 UUID"


@pytest.mark.asyncio
async def test_knowledge_api_passes_project_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/knowledge 的 project_id 有轉進 search_knowledge"""
    from datetime import datetime, timezone

    from ching_tech_os.api import knowledge as knowledge_api
    from ching_tech_os.models.auth import SessionData
    from ching_tech_os.models.knowledge import KnowledgeListResponse

    captured: dict = {}

    def _fake_search(**kwargs):
        captured.update(kwargs)
        return KnowledgeListResponse(items=[], total=0, query=None)

    monkeypatch.setattr(knowledge_api, "search_knowledge", _fake_search)

    app = FastAPI()
    app.include_router(knowledge_api.router)

    now = datetime.now(timezone.utc)
    session = SessionData(
        username="u",
        password="",
        nas_host="h",
        user_id=1,
        created_at=now,
        expires_at=now,
        role="admin",
    )
    # 覆寫 require_app_permission 產生的 checker（每次呼叫都是新的 closure，只能從路由取）
    for route in app.routes:
        for dep in getattr(getattr(route, "dependant", None), "dependencies", []):
            app.dependency_overrides[dep.call] = lambda: session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/knowledge?scope=project&project_id={PID_A}",
            headers={"Authorization": "Bearer x"},
        )

    assert resp.status_code == 200, resp.text
    assert captured["project_id"] == PID_A
    assert captured["scope"] == "project"
