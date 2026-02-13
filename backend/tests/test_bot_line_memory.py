"""bot_line.memory 測試。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.services.bot_line import memory


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_list_and_create_memories(monkeypatch: pytest.MonkeyPatch) -> None:
    group_id = uuid4()
    user_id = uuid4()
    creator_id = uuid4()
    conn = SimpleNamespace(fetch=AsyncMock(), fetchrow=AsyncMock())
    monkeypatch.setattr(memory, "get_connection", lambda: _ConnCtx(conn))

    conn.fetch.side_effect = [
        [{"id": uuid4(), "title": "g1"}],
        [{"id": uuid4(), "title": "u1"}],
        [{"content": "a"}],
        [{"content": "b"}],
    ]
    group_items, group_total = await memory.list_group_memories(group_id)
    user_items, user_total = await memory.list_user_memories(user_id)
    assert group_total == 1 and group_items[0]["title"] == "g1"
    assert user_total == 1 and user_items[0]["title"] == "u1"

    conn.fetchrow.side_effect = [
        {"id": uuid4(), "created_by": creator_id},  # create_group_memory returning
        {"display_name": "Alice"},  # created_by name
        {"id": uuid4()},  # create_user_memory returning
        {"id": uuid4(), "name": "line-user"},  # get_line_user_by_ctos_user
        None,  # get_line_user_by_ctos_user not found
    ]

    created_group = await memory.create_group_memory(group_id, "T", "C", created_by=creator_id)
    created_user = await memory.create_user_memory(user_id, "UT", "UC")
    found_user = await memory.get_line_user_by_ctos_user(1)
    missing_user = await memory.get_line_user_by_ctos_user(2)

    assert created_group["created_by_name"] == "Alice"
    assert "id" in created_user
    assert found_user is not None
    assert missing_user is None

    active_group = await memory.get_active_group_memories(group_id)
    active_user = await memory.get_active_user_memories(user_id)
    assert active_group == [{"content": "a"}]
    assert active_user == [{"content": "b"}]


@pytest.mark.asyncio
async def test_update_and_delete_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    memory_id = uuid4()
    creator_id = uuid4()
    conn = SimpleNamespace(fetchrow=AsyncMock(), execute=AsyncMock())
    monkeypatch.setattr(memory, "get_connection", lambda: _ConnCtx(conn))

    # 無更新欄位：先群組查到
    conn.fetchrow.side_effect = [
        {"id": memory_id, "created_by": creator_id, "title": "g"},  # group query
        # 無更新欄位：群組查不到，個人查到
        None,
        {"id": memory_id, "title": "u"},
        # update group success + created_by_name
        {"id": memory_id, "created_by": creator_id, "title": "new"},
        {"display_name": "Alice"},
        # update group miss, update user success
        None,
        {"id": memory_id, "title": "u2"},
        # update not found
        None,
        None,
    ]

    no_update_group = await memory.update_memory(memory_id)
    no_update_user = await memory.update_memory(memory_id)
    updated_group = await memory.update_memory(memory_id, title="new", is_active=True)
    updated_user = await memory.update_memory(memory_id, content="x")
    not_found = await memory.update_memory(memory_id, title="x")

    assert no_update_group["title"] == "g"
    assert no_update_user["title"] == "u"
    assert updated_group["created_by_name"] == "Alice"
    assert updated_user["title"] == "u2"
    assert not_found is None

    conn.execute.side_effect = [
        "DELETE 1",  # 刪群組成功
        "DELETE 0", "DELETE 1",  # 刪個人成功
        "DELETE 0", "DELETE 0",  # 都失敗
    ]
    assert await memory.delete_memory(memory_id) is True
    assert await memory.delete_memory(memory_id) is True
    assert await memory.delete_memory(memory_id) is False
