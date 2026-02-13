"""MCP memory/message/share tools 測試。"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services.mcp import memory_tools, message_tools, share_tools


_GROUP_ID = "00000000-0000-0000-0000-000000000001"


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_memory_add_and_get(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory_tools, "ensure_db_connection", AsyncMock())
    conn = SimpleNamespace(fetchrow=AsyncMock(), fetch=AsyncMock())
    monkeypatch.setattr(memory_tools, "get_connection", lambda: _ConnCtx(conn))

    bad_group = await memory_tools.add_memory(content="x", line_group_id="bad")
    assert "格式錯誤" in bad_group

    conn.fetchrow.return_value = {"id": "m-group"}
    created_group = await memory_tools.add_memory(
        content="x" * 40,
        line_group_id=_GROUP_ID,
    )
    assert "已新增群組記憶" in created_group
    assert "m-group" in created_group

    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.get_line_user_record",
        AsyncMock(return_value=None),
    )
    missing_user = await memory_tools.add_memory(content="x", line_user_id="U-404")
    assert "找不到用戶" in missing_user

    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.get_line_user_record",
        AsyncMock(return_value={"id": "u-1"}),
    )
    conn.fetchrow.return_value = {"id": "m-user"}
    created_user = await memory_tools.add_memory(content="hello", line_user_id="U-1")
    assert "已新增個人記憶" in created_user
    assert "m-user" in created_user

    missing_scope = await memory_tools.add_memory(content="x")
    assert "請提供 line_group_id 或 line_user_id" in missing_scope

    bad_group_query = await memory_tools.get_memories(line_group_id="bad")
    assert "格式錯誤" in bad_group_query

    conn.fetch.return_value = []
    empty_group = await memory_tools.get_memories(line_group_id=_GROUP_ID)
    assert "目前沒有設定任何記憶" in empty_group

    conn.fetch.return_value = [
        {
            "id": "m-1",
            "title": "T1",
            "content": "A" * 120,
            "is_active": True,
            "created_at": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        },
        {
            "id": "m-2",
            "title": "T2",
            "content": "B",
            "is_active": False,
            "created_at": datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc),
        },
    ]
    group_list = await memory_tools.get_memories(line_group_id=_GROUP_ID)
    assert "群組記憶列表" in group_list
    assert "T1" in group_list and "T2" in group_list
    assert "..." in group_list

    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.get_line_user_record",
        AsyncMock(return_value=None),
    )
    missing_user_list = await memory_tools.get_memories(line_user_id="U-404")
    assert "找不到用戶" in missing_user_list

    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.get_line_user_record",
        AsyncMock(return_value={"id": "u-1"}),
    )
    conn.fetch.return_value = []
    empty_user = await memory_tools.get_memories(line_user_id="U-1")
    assert "目前沒有設定任何記憶" in empty_user

    conn.fetch.return_value = [
        {
            "id": "m-u-1",
            "title": "Personal",
            "content": "memo",
            "is_active": True,
            "created_at": datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc),
        }
    ]
    user_list = await memory_tools.get_memories(line_user_id="U-1")
    assert "個人記憶列表" in user_list
    assert "Personal" in user_list

    missing_input = await memory_tools.get_memories()
    assert "請提供 line_group_id 或 line_user_id" in missing_input


@pytest.mark.asyncio
async def test_memory_update_and_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory_tools, "ensure_db_connection", AsyncMock())
    conn = SimpleNamespace(execute=AsyncMock())
    monkeypatch.setattr(memory_tools, "get_connection", lambda: _ConnCtx(conn))

    bad_update = await memory_tools.update_memory("bad", title="x")
    assert "記憶 ID 格式錯誤" in bad_update

    no_fields = await memory_tools.update_memory(_GROUP_ID)
    assert "請提供要更新的欄位" in no_fields

    conn.execute.return_value = "UPDATE 1"
    updated_group = await memory_tools.update_memory(_GROUP_ID, title="new-title")
    assert "已更新群組記憶" in updated_group

    conn.execute.side_effect = ["UPDATE 0", "UPDATE 1"]
    updated_user = await memory_tools.update_memory(_GROUP_ID, content="new-content")
    assert "已更新個人記憶" in updated_user

    conn.execute.side_effect = ["UPDATE 0", "UPDATE 0"]
    not_found = await memory_tools.update_memory(_GROUP_ID, is_active=False)
    assert "找不到指定的記憶" in not_found

    bad_delete = await memory_tools.delete_memory("bad")
    assert "記憶 ID 格式錯誤" in bad_delete

    conn.execute.side_effect = None
    conn.execute.return_value = "DELETE 1"
    deleted_group = await memory_tools.delete_memory(_GROUP_ID)
    assert "已刪除群組記憶" in deleted_group

    conn.execute.side_effect = ["DELETE 0", "DELETE 1"]
    deleted_user = await memory_tools.delete_memory(_GROUP_ID)
    assert "已刪除個人記憶" in deleted_user

    conn.execute.side_effect = ["DELETE 0", "DELETE 0"]
    not_found_delete = await memory_tools.delete_memory(_GROUP_ID)
    assert "找不到指定的記憶" in not_found_delete


@pytest.mark.asyncio
async def test_message_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(message_tools, "ensure_db_connection", AsyncMock())
    conn = SimpleNamespace(fetch=AsyncMock(), fetchrow=AsyncMock())
    monkeypatch.setattr(message_tools, "get_connection", lambda: _ConnCtx(conn))

    conn.fetch.return_value = []
    summary_empty = await message_tools.summarize_chat(_GROUP_ID, hours=6, max_messages=10)
    assert "沒有文字訊息" in summary_empty

    conn.fetch.return_value = [
        {
            "content": "討論完成",
            "created_at": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            "message_type": "text",
            "user_name": "Amy",
        }
    ]
    conn.fetchrow.return_value = {"name": "專案群"}
    summary = await message_tools.summarize_chat(_GROUP_ID, hours=6, max_messages=10)
    assert "專案群" in summary
    assert "Amy: 討論完成" in summary

    missing_scope = await message_tools.get_message_attachments()
    assert "請提供 line_user_id 或 line_group_id" in missing_scope

    conn.fetch.return_value = []
    no_files = await message_tools.get_message_attachments(line_group_id=_GROUP_ID, days=3)
    assert "沒有找到附件" in no_files

    conn.fetch.return_value = [
        {
            "id": "f1",
            "file_type": "image",
            "file_name": "a.png",
            "file_size": 2 * 1024 * 1024,
            "nas_path": "2026/01/a.png",
            "created_at": datetime(2026, 1, 2, 3, 0, tzinfo=timezone.utc),
            "user_name": "Amy",
        },
        {
            "id": "f2",
            "file_type": "file",
            "file_name": None,
            "file_size": 512,
            "nas_path": "shared://projects/demo.txt",
            "created_at": datetime(2026, 1, 2, 4, 0, tzinfo=timezone.utc),
            "user_name": None,
        },
    ]
    files_group = await message_tools.get_message_attachments(line_group_id=_GROUP_ID, days=7, limit=5)
    assert "找到 2 個附件" in files_group
    assert "ctos://linebot/files/2026/01/a.png" in files_group
    assert "MB" in files_group and "KB" in files_group

    conn.fetch.return_value = []
    await message_tools.get_message_attachments(line_user_id="U-1", days=1, file_type="image")
    query = conn.fetch.call_args.args[0]
    assert "m.bot_group_id IS NULL" in query


@pytest.mark.asyncio
async def test_create_share_link(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(share_tools, "ensure_db_connection", AsyncMock())
    import ching_tech_os.services.share as share_module

    moved = await share_tools.create_share_link("project", "P-1")
    assert "已遷移至 ERPNext" in moved

    invalid_type = await share_tools.create_share_link("bad", "X")
    assert "資源類型必須是" in invalid_type

    invalid_expire = await share_tools.create_share_link("knowledge", "kb-1", expires_in="3h")
    assert "有效期限必須是" in invalid_expire

    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(
            return_value=SimpleNamespace(
                full_url="https://example.com/s/1",
                resource_title="KB-1",
                expires_at=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
            )
        ),
    )
    ok = await share_tools.create_share_link("knowledge", "kb-1", expires_in="24h")
    assert "分享連結已建立" in ok
    assert "https://example.com/s/1" in ok
    assert "有效至" in ok

    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(
            return_value=SimpleNamespace(
                full_url="https://example.com/s/perm",
                resource_title="KB-2",
                expires_at=None,
            )
        ),
    )
    permanent = await share_tools.create_share_link("knowledge", "kb-2", expires_in=None)
    assert "永久有效" in permanent

    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(side_effect=share_module.ResourceNotFoundError("missing")),
    )
    missing = await share_tools.create_share_link("knowledge", "kb-404")
    assert "找不到資源" in missing

    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(side_effect=share_module.ShareError("share failed")),
    )
    share_err = await share_tools.create_share_link("knowledge", "kb-err")
    assert "錯誤：" in share_err

    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    unknown = await share_tools.create_share_link("knowledge", "kb-err2")
    assert "發生錯誤" in unknown


@pytest.mark.asyncio
async def test_share_knowledge_attachment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(share_tools, "ensure_db_connection", AsyncMock())
    import ching_tech_os.services.knowledge as knowledge_module
    import ching_tech_os.services.path_manager as path_manager_module
    import ching_tech_os.services.share as share_module
    from ching_tech_os.config import settings
    nas_tools_module = importlib.import_module("ching_tech_os.services.mcp.nas_tools")

    invalid_expire = await share_tools.share_knowledge_attachment("kb-1", 0, expires_in="3h")
    assert "有效期限必須是" in invalid_expire

    monkeypatch.setattr(
        knowledge_module,
        "get_knowledge",
        lambda _kb_id: SimpleNamespace(attachments=[]),
    )
    out_of_range = await share_tools.share_knowledge_attachment("kb-1", 1)
    assert "超出範圍" in out_of_range

    monkeypatch.setattr(
        knowledge_module,
        "get_knowledge",
        lambda _kb_id: SimpleNamespace(
            attachments=[SimpleNamespace(path="local://knowledge/assets/images/a.txt")]
        ),
    )
    unsupported_ext = await share_tools.share_knowledge_attachment("kb-1", 0)
    assert "僅支援 .md2ppt 或 .md2doc" in unsupported_ext

    monkeypatch.setattr(
        knowledge_module,
        "get_knowledge",
        lambda _kb_id: SimpleNamespace(
            attachments=[SimpleNamespace(path="ctos://knowledge/assets/demo.md2ppt")]
        ),
    )
    monkeypatch.setattr(
        path_manager_module.path_manager,
        "parse",
        lambda _path: SimpleNamespace(zone=path_manager_module.StorageZone.NAS, path="demo.md2ppt"),
    )
    unsupported_path = await share_tools.share_knowledge_attachment("kb-1", 0)
    assert "不支援的附件路徑格式" in unsupported_path

    monkeypatch.setattr(
        path_manager_module.path_manager,
        "parse",
        lambda _path: SimpleNamespace(
            zone=path_manager_module.StorageZone.CTOS,
            path="knowledge/attachments/demo.md2ppt",
        ),
    )
    monkeypatch.setattr(knowledge_module, "get_nas_attachment", lambda _path: b"# demo")
    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(
            return_value=SimpleNamespace(
                token="token-1",
                password="1234",
                expires_at=None,
            )
        ),
    )
    monkeypatch.setattr(settings, "md2ppt_url", "https://md2ppt.example")
    success_ppt = await share_tools.share_knowledge_attachment("kb-1", 0)
    assert "MD2PPT" in success_ppt
    assert "https://md2ppt.example/?shareToken=token-1" in success_ppt
    assert "1234" in success_ppt

    local_file = tmp_path / "images" / "demo.md2doc"
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_text("# local", encoding="utf-8")
    monkeypatch.setattr(
        knowledge_module,
        "get_knowledge",
        lambda _kb_id: SimpleNamespace(
            attachments=[SimpleNamespace(path="local://knowledge/assets/images/demo.md2doc")]
        ),
    )
    monkeypatch.setattr(
        path_manager_module.path_manager,
        "parse",
        lambda _path: SimpleNamespace(
            zone=path_manager_module.StorageZone.LOCAL,
            path="knowledge/assets/images/demo.md2doc",
        ),
    )
    monkeypatch.setattr(nas_tools_module, "_get_knowledge_paths", lambda: (tmp_path, tmp_path, tmp_path, tmp_path))
    monkeypatch.setattr(settings, "md2doc_url", "https://md2doc.example")
    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(
            return_value=SimpleNamespace(
                token="token-2",
                password="5678",
                expires_at=datetime(2026, 1, 3, 0, 0, tzinfo=timezone.utc),
            )
        ),
    )
    success_doc = await share_tools.share_knowledge_attachment("kb-1", 0)
    assert "MD2DOC" in success_doc
    assert "https://md2doc.example/?shareToken=token-2" in success_doc
    assert "有效至" in success_doc

    monkeypatch.setattr(
        knowledge_module,
        "get_knowledge",
        lambda _kb_id: (_ for _ in ()).throw(knowledge_module.KnowledgeNotFoundError("missing")),
    )
    not_found = await share_tools.share_knowledge_attachment("kb-1", 0)
    assert "錯誤：" in not_found

    monkeypatch.setattr(
        knowledge_module,
        "get_knowledge",
        lambda _kb_id: (_ for _ in ()).throw(knowledge_module.KnowledgeError("bad")),
    )
    kb_error = await share_tools.share_knowledge_attachment("kb-1", 0)
    assert "錯誤：" in kb_error

    monkeypatch.setattr(
        knowledge_module,
        "get_knowledge",
        lambda _kb_id: SimpleNamespace(
            attachments=[SimpleNamespace(path="ctos://knowledge/assets/demo.md2ppt")]
        ),
    )
    monkeypatch.setattr(
        path_manager_module.path_manager,
        "parse",
        lambda _path: SimpleNamespace(
            zone=path_manager_module.StorageZone.CTOS,
            path="knowledge/assets/demo.md2ppt",
        ),
    )
    monkeypatch.setattr(knowledge_module, "get_nas_attachment", lambda _path: b"# demo")
    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(side_effect=share_module.ShareError("share failed")),
    )
    share_error = await share_tools.share_knowledge_attachment("kb-1", 0)
    assert "錯誤：" in share_error
