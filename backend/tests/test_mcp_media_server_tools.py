"""MCP media/server tools 測試。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from ching_tech_os.services.mcp import media_tools
from ching_tech_os.services.mcp import server as mcp_server


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _raise(exc: Exception):
    raise exc


@pytest.mark.asyncio
async def test_download_web_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ching_tech_os.services.bot.media.download_image_from_url",
        AsyncMock(return_value=None),
    )
    failed = await media_tools.download_web_image("https://example.com/a.png")
    assert "無法下載圖片" in failed

    monkeypatch.setattr(
        "ching_tech_os.services.bot.media.download_image_from_url",
        AsyncMock(return_value="/tmp/demo.png"),
    )
    ok = await media_tools.download_web_image("https://example.com/b.png")
    assert "已下載圖片 demo.png" in ok
    assert "[FILE_MESSAGE:" in ok


@pytest.mark.asyncio
async def test_convert_pdf_to_images(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(media_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(media_tools, "check_mcp_tool_permission", AsyncMock(return_value=(False, "DENY")))
    denied = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/demo.pdf", ctos_user_id=1))
    assert denied["success"] is False
    assert denied["error"] == "DENY"

    monkeypatch.setattr(media_tools, "check_mcp_tool_permission", AsyncMock(return_value=(True, "")))
    bad_fmt = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/demo.pdf", output_format="webp", ctos_user_id=1))
    assert "不支援的輸出格式" in bad_fmt["error"]

    bad_dpi = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/demo.pdf", dpi=10, ctos_user_id=1))
    assert "DPI 必須在 72-600 之間" in bad_dpi["error"]

    import ching_tech_os.services.document_reader as dr
    import ching_tech_os.services.path_manager as path_manager_module
    from ching_tech_os.config import settings

    monkeypatch.setattr(path_manager_module.path_manager, "parse", lambda _p: _raise(ValueError("bad path")))
    bad_path = json.loads(await media_tools.convert_pdf_to_images("bad://x.pdf", ctos_user_id=1))
    assert bad_path["error"] == "bad path"

    monkeypatch.setattr(
        path_manager_module.path_manager,
        "parse",
        lambda _p: SimpleNamespace(zone=path_manager_module.StorageZone.NAS, path="x.pdf"),
    )
    denied_zone = json.loads(await media_tools.convert_pdf_to_images("nas://x.pdf", ctos_user_id=1))
    assert "不允許存取" in denied_zone["error"]

    monkeypatch.setattr(
        path_manager_module.path_manager,
        "parse",
        lambda _p: SimpleNamespace(zone=path_manager_module.StorageZone.CTOS, path="knowledge/demo.pdf"),
    )
    missing_fs = tmp_path / "missing.pdf"
    monkeypatch.setattr(path_manager_module.path_manager, "to_filesystem", lambda _p: str(missing_fs))
    missing = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/missing.pdf", ctos_user_id=1))
    assert "PDF 檔案不存在" in missing["error"]

    pdf_file = tmp_path / "demo.pdf"
    pdf_file.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(path_manager_module.path_manager, "to_filesystem", lambda _p: str(pdf_file))
    monkeypatch.setattr(settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(
        dr,
        "convert_pdf_to_images",
        lambda **_kwargs: SimpleNamespace(
            success=True,
            total_pages=3,
            converted_pages=2,
            images=["a.png", "b.png"],
            message="ok",
        ),
    )
    success = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/demo.pdf", pages="1-2", ctos_user_id=1))
    assert success["success"] is True
    assert success["converted_pages"] == 2

    monkeypatch.setattr(dr, "convert_pdf_to_images", lambda **_kwargs: _raise(FileNotFoundError("not found")))
    file_err = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/demo.pdf", ctos_user_id=1))
    assert file_err["error"] == "not found"

    monkeypatch.setattr(dr, "convert_pdf_to_images", lambda **_kwargs: _raise(dr.PasswordProtectedError("pwd")))
    pwd_err = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/demo.pdf", ctos_user_id=1))
    assert "密碼保護" in pwd_err["error"]

    monkeypatch.setattr(dr, "convert_pdf_to_images", lambda **_kwargs: _raise(dr.UnsupportedFormatError("bad format")))
    unsupported_err = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/demo.pdf", ctos_user_id=1))
    assert unsupported_err["error"] == "bad format"

    monkeypatch.setattr(dr, "convert_pdf_to_images", lambda **_kwargs: _raise(dr.CorruptedFileError("broken")))
    corrupted_err = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/demo.pdf", ctos_user_id=1))
    assert corrupted_err["error"] == "broken"

    monkeypatch.setattr(dr, "convert_pdf_to_images", lambda **_kwargs: _raise(ValueError("bad page range")))
    value_err = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/demo.pdf", ctos_user_id=1))
    assert value_err["error"] == "bad page range"

    monkeypatch.setattr(dr, "convert_pdf_to_images", lambda **_kwargs: _raise(RuntimeError("boom")))
    unknown_err = json.loads(await media_tools.convert_pdf_to_images("ctos://knowledge/demo.pdf", ctos_user_id=1))
    assert unknown_err["error"] == "轉換失敗: boom"


@pytest.mark.asyncio
async def test_server_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    naive = datetime(2026, 1, 1, 0, 0, 0)
    converted = mcp_server.to_taipei_time(naive)
    assert converted.tzinfo is not None
    assert converted.hour == 8
    assert mcp_server.to_taipei_time(None) is None

    import ching_tech_os.database as db_module
    import ching_tech_os.services.permissions as permissions_module

    monkeypatch.setattr(mcp_server, "init_db_pool", AsyncMock())
    monkeypatch.setattr(db_module, "_pool", None)
    await mcp_server.ensure_db_connection()
    assert mcp_server.init_db_pool.await_count == 1
    monkeypatch.setattr(db_module, "_pool", object())
    await mcp_server.ensure_db_connection()
    assert mcp_server.init_db_pool.await_count == 1

    monkeypatch.setattr(
        permissions_module,
        "is_tool_deprecated",
        lambda _tool: (True, "deprecated"),
    )
    deprecated = await mcp_server.check_mcp_tool_permission("legacy_tool", 1)
    assert deprecated == (False, "deprecated")

    monkeypatch.setattr(
        permissions_module,
        "is_tool_deprecated",
        lambda _tool: (False, ""),
    )
    monkeypatch.setattr(permissions_module, "TOOL_APP_MAPPING", {}, raising=False)
    no_required_app = await mcp_server.check_mcp_tool_permission("free_tool", None)
    assert no_required_app == (True, "")

    monkeypatch.setattr(permissions_module, "TOOL_APP_MAPPING", {"secure_tool": "kb"}, raising=False)
    monkeypatch.setattr(permissions_module, "APP_DISPLAY_NAMES", {"kb": "知識庫"}, raising=False)
    monkeypatch.setattr(permissions_module, "DEFAULT_APP_PERMISSIONS", {"kb": False}, raising=False)
    no_user = await mcp_server.check_mcp_tool_permission("secure_tool", None)
    assert no_user[0] is False and "知識庫" in no_user[1]

    monkeypatch.setattr(permissions_module, "DEFAULT_APP_PERMISSIONS", {"kb": True}, raising=False)
    allow_default = await mcp_server.check_mcp_tool_permission("secure_tool", None)
    assert allow_default == (True, "")

    monkeypatch.setattr(permissions_module, "DEFAULT_APP_PERMISSIONS", {"kb": False}, raising=False)
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value=None), fetchval=AsyncMock(return_value=1))
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))
    missing_user = await mcp_server.check_mcp_tool_permission("secure_tool", 77)
    assert missing_user[0] is False

    conn.fetchrow = AsyncMock(return_value={"role": "admin", "preferences": {"permissions": {"apps": {"kb": True}}}})
    monkeypatch.setattr(permissions_module, "check_tool_permission", lambda *_args, **_kwargs: True)
    allowed_user = await mcp_server.check_mcp_tool_permission("secure_tool", 1)
    assert allowed_user == (True, "")

    monkeypatch.setattr(permissions_module, "check_tool_permission", lambda *_args, **_kwargs: False)
    denied_user = await mcp_server.check_mcp_tool_permission("secure_tool", 1)
    assert denied_user[0] is False and "沒有" in denied_user[1]

    conn.fetchval = AsyncMock(return_value=1)
    is_member = await mcp_server.check_project_member_permission("00000000-0000-0000-0000-000000000001", 1)
    assert is_member is True
    conn.fetchval = AsyncMock(return_value=None)
    not_member = await mcp_server.check_project_member_permission("00000000-0000-0000-0000-000000000001", 1)
    assert not_member is False


@pytest.mark.asyncio
async def test_server_tool_listing_and_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mcp_server.mcp,
        "list_tools",
        AsyncMock(
            return_value=[
                SimpleNamespace(name="summarize_chat", description="sum", inputSchema={"type": "object"}),
                SimpleNamespace(name="search_knowledge", description=None, inputSchema={"type": "object"}),
            ]
        ),
    )
    tools = await mcp_server.get_mcp_tools()
    assert tools[0]["name"] == "summarize_chat"
    assert tools[1]["description"] == ""

    names = await mcp_server.get_mcp_tool_names(exclude_group_only=True)
    assert "mcp__ching-tech-os__search_knowledge" in names
    assert "mcp__ching-tech-os__summarize_chat" not in names

    monkeypatch.setattr(
        mcp_server.mcp,
        "call_tool",
        AsyncMock(return_value=([SimpleNamespace(text="OK")], {})),
    )
    ok = await mcp_server.execute_tool("demo", {"x": 1})
    assert ok == "OK"

    monkeypatch.setattr(
        mcp_server.mcp,
        "call_tool",
        AsyncMock(return_value=([], {})),
    )
    no_output = await mcp_server.execute_tool("demo", {"x": 1})
    assert "無輸出" in no_output

    monkeypatch.setattr(
        mcp_server.mcp,
        "call_tool",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    failed = await mcp_server.execute_tool("demo", {"x": 1})
    assert failed.startswith("執行失敗：")

    run_mock = Mock()
    monkeypatch.setattr(mcp_server.mcp, "run", run_mock)
    mcp_server.run_cli()
    run_mock.assert_called_once()
