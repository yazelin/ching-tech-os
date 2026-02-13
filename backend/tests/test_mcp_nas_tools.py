"""MCP nas tools 測試。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services.mcp import nas_tools


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _allow(monkeypatch: pytest.MonkeyPatch, allowed: bool = True):
    monkeypatch.setattr(nas_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(nas_tools, "check_mcp_tool_permission", AsyncMock(return_value=(allowed, "DENY")))


def test_nas_tools_helpers() -> None:
    assert nas_tools._format_file_size(1024) == "1.0KB"
    assert nas_tools._format_file_size(1024 * 1024) == "1.0MB"
    info, hint = nas_tools._build_file_message_info("a.jpg", 100, "u", extra_fields={"x": 1}, is_knowledge=True)
    assert info["type"] == "image" and info["x"] == 1
    assert "知識庫圖片" in hint
    info2, _ = nas_tools._build_file_message_info("a.bin", 10, "u", "f")
    assert info2["type"] == "file"


@pytest.mark.asyncio
async def test_search_nas_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _allow(monkeypatch, True)
    projects = tmp_path / "projects"
    circuits = tmp_path / "circuits"
    (projects / "DemoDir").mkdir(parents=True, exist_ok=True)
    (circuits / "X").mkdir(parents=True, exist_ok=True)
    f = projects / "DemoDir" / "demo.txt"
    f.write_text("x", encoding="utf-8")

    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "projects_mount_path", str(projects))
    monkeypatch.setattr(settings, "circuits_mount_path", str(circuits))

    class _Proc:
        def __init__(self, out: str):
            self._out = out.encode()

        async def communicate(self):
            return self._out, b""

        def kill(self):
            return None

    async def _fake_subproc(*args, **_kwargs):
        if "-type" in args:
            t = args[args.index("-type") + 1]
            if t == "d":
                return _Proc(str(projects / "DemoDir"))
            return _Proc(str(f))
        return _Proc("")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subproc)
    out = await nas_tools.search_nas_files("demo", ctos_user_id=1)
    assert "shared://projects" in out

    out2 = await nas_tools.search_nas_files("  ", ctos_user_id=1)
    assert "至少一個關鍵字" in out2


@pytest.mark.asyncio
async def test_get_file_info_and_read_document(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _allow(monkeypatch, True)
    import ching_tech_os.services.share as share_module
    import ching_tech_os.services.document_reader as dr
    import ching_tech_os.services.path_manager as pm
    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "nas_mount_path", str(tmp_path))
    doc = tmp_path / "x.pdf"
    doc.write_text("pdf", encoding="utf-8")
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p: doc)

    out = await nas_tools.get_nas_file_info("shared://projects/x.pdf", ctos_user_id=1)
    assert "完整路徑" in out

    monkeypatch.setattr(pm.path_manager, "parse", lambda _p: SimpleNamespace(zone=pm.StorageZone.SHARED))
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p: str(doc))
    monkeypatch.setattr(dr, "SUPPORTED_EXTENSIONS", {".pdf"})
    monkeypatch.setattr(dr, "LEGACY_EXTENSIONS", {".doc"})
    monkeypatch.setattr(
        "ching_tech_os.services.workers.run_in_doc_pool",
        AsyncMock(return_value=SimpleNamespace(text="CONTENT", format="pdf", page_count=1, truncated=False, error=None)),
    )
    monkeypatch.setattr(dr, "extract_text", lambda _p: None)
    text = await nas_tools.read_document("shared://projects/x.pdf", ctos_user_id=1)
    assert "CONTENT" in text

    monkeypatch.setattr(pm.path_manager, "parse", lambda _p: SimpleNamespace(zone=pm.StorageZone.LOCAL))
    denied = await nas_tools.read_document("local://x", ctos_user_id=1)
    assert "不允許存取" in denied


@pytest.mark.asyncio
async def test_send_nas_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _allow(monkeypatch, True)
    import ching_tech_os.services.share as share_module
    import ching_tech_os.services.bot_line as line_module
    import ching_tech_os.services.bot_telegram.adapter as tg_adapter
    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "tok")
    img = tmp_path / "a.jpg"
    img.write_bytes(b"x" * 100)
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p: img)
    monkeypatch.setattr(share_module, "create_share_link", AsyncMock(return_value=SimpleNamespace(full_url="https://x/s/abc", token="abc")))

    class _TG:
        def __init__(self, token):
            self.token = token

        async def send_image(self, *_a):
            return None

        async def send_file(self, *_a):
            return None

        async def send_text(self, *_a):
            return None

    monkeypatch.setattr(tg_adapter, "TelegramBotAdapter", _TG)
    out = await nas_tools.send_nas_file("shared://projects/a.jpg", telegram_chat_id="1", ctos_user_id=1)
    assert "已發送圖片" in out

    # line group send
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value={"platform_group_id": "G1"}))
    monkeypatch.setattr(nas_tools, "get_connection", lambda: _ConnCtx(conn))
    monkeypatch.setattr(line_module, "push_image", AsyncMock(return_value=("m1", None)))
    monkeypatch.setattr(line_module, "push_text", AsyncMock(return_value=("m2", None)))
    out2 = await nas_tools.send_nas_file("shared://projects/a.jpg", line_group_id="00000000-0000-0000-0000-000000000001", ctos_user_id=1)
    assert "已發送圖片" in out2


@pytest.mark.asyncio
async def test_prepare_file_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _allow(monkeypatch, True)
    import ching_tech_os.services.share as share_module
    import ching_tech_os.services.path_manager as pm
    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "public_url", "https://x")
    monkeypatch.setattr(settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(settings, "line_files_nas_path", "linebot/files")

    kf = tmp_path / "kb-001-a.png"
    kf.write_bytes(b"img")
    monkeypatch.setattr(pm.path_manager, "parse", lambda p: SimpleNamespace(zone=pm.StorageZone.LOCAL, path="knowledge/assets/images/kb-001-a.png") if p.startswith("local://") else SimpleNamespace(zone=pm.StorageZone.CTOS, path="knowledge/attachments/kb-001/f.txt"))
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p: str(kf))
    monkeypatch.setattr(share_module, "create_share_link", AsyncMock(return_value=SimpleNamespace(full_url="https://x/s/t", token="t")))
    msg = await nas_tools.prepare_file_message("local://knowledge/assets/images/kb-001-a.png", ctos_user_id=1)
    assert "[FILE_MESSAGE:" in msg
    assert "知識庫" in msg

    nf = tmp_path / "linebot" / "files" / "abc.txt"
    nf.parent.mkdir(parents=True, exist_ok=True)
    nf.write_text("x", encoding="utf-8")
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p: nf)
    msg2 = await nas_tools.prepare_file_message("shared://projects/abc.txt", ctos_user_id=1)
    assert "[FILE_MESSAGE:" in msg2

    _allow(monkeypatch, False)
    denied = await nas_tools.prepare_file_message("x", ctos_user_id=1)
    assert denied.startswith("❌")
