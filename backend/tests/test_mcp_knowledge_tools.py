"""MCP knowledge tools 測試。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services.mcp import knowledge_tools


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _allow(monkeypatch: pytest.MonkeyPatch, allowed: bool = True):
    monkeypatch.setattr(knowledge_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        knowledge_tools,
        "check_mcp_tool_permission",
        AsyncMock(return_value=(allowed, "DENY")),
    )


@pytest.mark.asyncio
async def test_determine_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(
        fetchrow=AsyncMock(
            side_effect=[
                {"username": "alice"},  # ctos user
                {"project_id": "00000000-0000-0000-0000-000000000001"},  # group bound project
                {"username": "bob"},  # personal user
                None,  # no group project
            ]
        )
    )
    monkeypatch.setattr(knowledge_tools, "get_connection", lambda: _ConnCtx(conn))

    scope1 = await knowledge_tools._determine_knowledge_scope(
        line_group_id="00000000-0000-0000-0000-000000000002",
        line_user_id=None,
        ctos_user_id=1,
    )
    assert scope1[0] == "project"

    scope2 = await knowledge_tools._determine_knowledge_scope(
        line_group_id=None,
        line_user_id="U1",
        ctos_user_id=2,
    )
    assert scope2[0] == "personal"

    scope3 = await knowledge_tools._determine_knowledge_scope(
        line_group_id="00000000-0000-0000-0000-000000000003",
        line_user_id=None,
        ctos_user_id=None,
    )
    assert scope3[0] == "global"


@pytest.mark.asyncio
async def test_search_and_get_item(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch, True)
    import ching_tech_os.services.knowledge as kb_service

    conn = SimpleNamespace(fetchrow=AsyncMock(return_value={"username": "alice"}))
    monkeypatch.setattr(knowledge_tools, "get_connection", lambda: _ConnCtx(conn))

    item = SimpleNamespace(
        id="kb-001",
        title="T",
        category="note",
        tags=SimpleNamespace(topics=["x"]),
        snippet="snip",
        content="body",
        attachments=[SimpleNamespace(type="image", path="local://knowledge/assets/images/kb-001-a.png", description="d")],
    )
    monkeypatch.setattr(kb_service, "search_knowledge", lambda **_kwargs: SimpleNamespace(items=[item]))
    monkeypatch.setattr(kb_service, "get_knowledge", lambda _id: item)

    out = await knowledge_tools.search_knowledge(query="*", ctos_user_id=1)
    assert "知識庫共有" in out
    out2 = await knowledge_tools.get_knowledge_item("kb-001", ctos_user_id=1)
    assert "附件" in out2

    monkeypatch.setattr(kb_service, "search_knowledge", lambda **_kwargs: SimpleNamespace(items=[]))
    out3 = await knowledge_tools.search_knowledge(query="abc", ctos_user_id=1)
    assert "找不到" in out3


@pytest.mark.asyncio
async def test_update_and_delete_item(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch, True)
    import ching_tech_os.services.knowledge as kb_service

    conn = SimpleNamespace(fetchrow=AsyncMock(return_value={"username": "alice"}))
    monkeypatch.setattr(knowledge_tools, "get_connection", lambda: _ConnCtx(conn))
    monkeypatch.setattr(
        kb_service,
        "update_knowledge",
        lambda _id, _data: SimpleNamespace(id="kb-001", title="N", scope="personal"),
    )
    monkeypatch.setattr(kb_service, "delete_knowledge", lambda _id: None)

    out = await knowledge_tools.update_knowledge_item(
        kb_id="kb-001",
        title="N",
        scope="personal",
        topics=["t1"],
        ctos_user_id=1,
    )
    assert "已更新" in out

    out2 = await knowledge_tools.delete_knowledge_item("kb-001", ctos_user_id=1)
    assert "已刪除" in out2

    monkeypatch.setattr(kb_service, "delete_knowledge", lambda _id: (_ for _ in ()).throw(RuntimeError("x")))
    out3 = await knowledge_tools.delete_knowledge_item("kb-001", ctos_user_id=1)
    assert "刪除失敗" in out3


@pytest.mark.asyncio
async def test_attachments_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _allow(monkeypatch, True)
    import ching_tech_os.services.knowledge as kb_service
    import ching_tech_os.services.path_manager as path_manager_module

    kb_item = SimpleNamespace(
        id="kb-001",
        attachments=[
            SimpleNamespace(type="file", path="local://knowledge/assets/images/kb-001-a.txt", size="1KB", description="desc"),
            SimpleNamespace(type="file", path="local://knowledge/assets/images/kb-001-b.bin", size="2KB", description=None),
        ],
    )
    monkeypatch.setattr(kb_service, "get_knowledge", lambda _id: kb_item)
    monkeypatch.setattr(kb_service, "copy_linebot_attachment_to_knowledge", lambda *_a, **_k: None)
    monkeypatch.setattr(kb_service, "update_attachment_description", lambda *_a, **_k: None, raising=False)
    monkeypatch.setattr(
        kb_service,
        "update_attachment",
        lambda **_kwargs: SimpleNamespace(path="local://knowledge/assets/images/kb-001-a.txt", description="new"),
    )

    out = await knowledge_tools.get_knowledge_attachments("kb-001", ctos_user_id=1)
    assert "附件列表" in out

    out2 = await knowledge_tools.update_knowledge_attachment("kb-001", 0, description="new", ctos_user_id=1)
    assert "已更新" in out2

    out3 = await knowledge_tools.add_attachments_to_knowledge(
        "kb-001",
        attachments=["p1", "p2"],
        descriptions=["d1", "d2"],
        ctos_user_id=1,
    )
    assert "新增 2 個附件" in out3

    # read attachment: text
    text_file = tmp_path / "a.txt"
    text_file.write_text("hello", encoding="utf-8")
    bin_file = tmp_path / "b.bin"
    bin_file.write_bytes(b"\x00\x01")
    monkeypatch.setattr(path_manager_module.path_manager, "to_filesystem", lambda p: str(text_file if p.endswith("a.txt") else bin_file))
    monkeypatch.setattr(path_manager_module.path_manager, "parse", lambda _p: SimpleNamespace(zone=path_manager_module.StorageZone.LOCAL))

    read1 = await knowledge_tools.read_knowledge_attachment("kb-001", 0, ctos_user_id=1)
    assert "hello" in read1
    read2 = await knowledge_tools.read_knowledge_attachment("kb-001", 1, ctos_user_id=1)
    assert "二進位檔案" in read2
    read3 = await knowledge_tools.read_knowledge_attachment("kb-001", 9, ctos_user_id=1)
    assert "超出範圍" in read3


@pytest.mark.asyncio
async def test_add_note_flows_and_permission_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch, True)
    import ching_tech_os.services.knowledge as kb_service

    monkeypatch.setattr(knowledge_tools, "_determine_knowledge_scope", AsyncMock(return_value=("personal", "alice", None)))
    monkeypatch.setattr(kb_service, "create_knowledge", lambda *_a, **_k: SimpleNamespace(id="kb-010", title="T"))
    monkeypatch.setattr(kb_service, "copy_linebot_attachment_to_knowledge", lambda *_a, **_k: None)

    out = await knowledge_tools.add_note(
        title="T",
        content="C",
        ctos_user_id=1,
        line_user_id="U1",
    )
    assert "筆記已新增" in out

    out2 = await knowledge_tools.add_note_with_attachments(
        title="T",
        content="C",
        attachments=["a", "b"],
        ctos_user_id=1,
        line_user_id="U1",
    )
    assert "筆記已新增" in out2

    out3 = await knowledge_tools.add_note_with_attachments(
        title="T",
        content="C",
        attachments=["a"] * 11,
        ctos_user_id=1,
        line_user_id="U1",
    )
    assert "不能超過 10" in out3

    # 權限拒絕
    _allow(monkeypatch, False)
    denied = await knowledge_tools.search_knowledge("x", ctos_user_id=1)
    assert denied.startswith("❌")
