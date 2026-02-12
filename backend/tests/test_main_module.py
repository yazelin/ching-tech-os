"""main 模組測試。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from ching_tech_os import main
from ching_tech_os.services.errors import ServiceError


def test_ensure_directories(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main.settings, "knowledge_nas_path", "k")
    monkeypatch.setattr(main.settings, "project_nas_path", "p")
    monkeypatch.setattr(main.settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(main.settings, "line_files_nas_path", "")
    main.ensure_directories()
    assert (tmp_path / "k").exists()
    assert (tmp_path / "p").exists()
    assert (tmp_path / "ai-images").exists()


@pytest.mark.asyncio
async def test_service_error_handler() -> None:
    req = Request({"type": "http", "method": "GET", "path": "/x", "headers": [], "query_string": b"", "scheme": "http", "server": ("test", 80)})
    resp = await main.service_error_handler(req, ServiceError("錯誤", code="X", status_code=418))
    assert resp.status_code == 418


@pytest.mark.asyncio
async def test_lifespan_startup_shutdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = FastAPI()

    monkeypatch.setattr(main.settings, "bot_secret_key", "")
    monkeypatch.setattr(main, "ensure_directories", Mock())
    monkeypatch.setattr(main, "init_db_pool", AsyncMock())
    monkeypatch.setattr(main, "close_db_pool", AsyncMock())
    monkeypatch.setattr(main, "ensure_default_linebot_agents", AsyncMock())
    monkeypatch.setattr(main, "start_scheduler", Mock())
    monkeypatch.setattr(main, "stop_scheduler", Mock())
    monkeypatch.setattr(main.session_manager, "start_cleanup_task", AsyncMock())
    monkeypatch.setattr(main.session_manager, "stop_cleanup_task", AsyncMock())
    monkeypatch.setattr(main.terminal_service, "start_cleanup_task", AsyncMock())
    monkeypatch.setattr(main.terminal_service, "stop_cleanup_task", AsyncMock())
    monkeypatch.setattr(main.terminal_service, "close_all", Mock())

    # skills 預載入
    import ching_tech_os.skills as skills_module
    fake_manager = SimpleNamespace(load_skills=AsyncMock())
    monkeypatch.setattr(skills_module, "get_skill_manager", lambda: fake_manager)

    # Hub clients
    import ching_tech_os.services.clawhub_client as clawhub_module
    claw_client = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(clawhub_module, "ClawHubClient", lambda: claw_client)

    import ching_tech_os.services.skillhub_client as skillhub_module
    skill_client = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(skillhub_module, "skillhub_enabled", lambda: True)
    monkeypatch.setattr(skillhub_module, "SkillHubClient", lambda: skill_client)

    # telegram polling
    async def _polling():
        await asyncio.Event().wait()

    import ching_tech_os.services.bot_telegram.polling as polling_module
    monkeypatch.setattr(polling_module, "run_telegram_polling", _polling)

    # 其他關閉流程
    import ching_tech_os.services.workers as workers_module
    monkeypatch.setattr(workers_module, "shutdown_pools", Mock())
    import ching_tech_os.services.bot_line.client as line_client_module
    monkeypatch.setattr(line_client_module, "close_line_client", AsyncMock())
    import ching_tech_os.services.claude_agent as claude_agent_module
    monkeypatch.setattr(claude_agent_module, "_WORKING_DIR_BASE", tmp_path / "claude-work")

    async with main.lifespan(app):
        assert hasattr(app.state, "clawhub_client")
        assert hasattr(app.state, "skillhub_client")

    main.init_db_pool.assert_awaited_once()
    main.close_db_pool.assert_awaited_once()
    claw_client.close.assert_awaited_once()
    skill_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_pages_and_short_share_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    frontend.mkdir(parents=True, exist_ok=True)
    (frontend / "login.html").write_text("login", encoding="utf-8")
    (frontend / "index.html").write_text("index", encoding="utf-8")
    (frontend / "public.html").write_text(
        (
            '<meta property="og:title" content="擎添工業 - 分享內容">'
            '<meta property="og:description" content="此為擎添工業內部分享的文件或專案資訊">'
            "<title>擎添工業 - 分享內容</title>"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "FRONTEND", frontend)

    assert (await main.health())["status"] == "healthy"
    assert "login.html" in str((await main.index()).path)
    assert "login.html" in str((await main.login_page()).path)
    assert "index.html" in str((await main.desktop_page()).path)
    assert "public.html" in str((await main.public_page()).path)

    import ching_tech_os.services.share as share_module
    import ching_tech_os.services.knowledge as knowledge_module
    import ching_tech_os.services as services_pkg

    monkeypatch.setattr(
        share_module,
        "get_link_info",
        AsyncMock(return_value={"resource_type": "knowledge", "resource_id": "1"}),
    )
    monkeypatch.setattr(knowledge_module, "get_knowledge", lambda _id: SimpleNamespace(title="KB", content="內容"))
    html1 = await main.short_share_url("t1")
    assert "KB - 擎添工業" in html1.body.decode("utf-8")

    monkeypatch.setattr(
        share_module,
        "get_link_info",
        AsyncMock(return_value={"resource_type": "project", "resource_id": "2"}),
    )
    monkeypatch.setattr(
        services_pkg,
        "project_service",
        SimpleNamespace(get_project=AsyncMock(return_value={"name": "P1", "description": "D"})),
        raising=False,
    )
    html2 = await main.short_share_url("t2")
    assert "P1 - 擎添工業專案" in html2.body.decode("utf-8")

    monkeypatch.setattr(
        share_module,
        "get_link_info",
        AsyncMock(return_value={"resource_type": "nas_file", "resource_id": "/a/b.txt"}),
    )
    html3 = await main.short_share_url("t3")
    assert "b.txt - 擎添工業" in html3.body.decode("utf-8")

    monkeypatch.setattr(share_module, "get_link_info", AsyncMock(side_effect=Exception("boom")))
    html4 = await main.short_share_url("t4")
    assert "擎添工業 - 分享內容" in html4.body.decode("utf-8")
