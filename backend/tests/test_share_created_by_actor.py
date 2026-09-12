"""#218：MCP 建立的分享連結 created_by 要記實際使用者，不是硬編的 'linebot'。

背景：`services/mcp/share_tools.py` 呼叫 `share_service.create_share_link(data,
"linebot", actor=...)` 時把 `created_by` 寫死成 `"linebot"`；#216 之後 `actor`
已經帶著解析用的 `user_id`（`ShareActor.from_ctos_user_id(ctos_user_id)`），
理論上分得出「哪個使用者」，但 `created_by` 沒有跟著用。結果 bot 使用者建立的
連結全部記成同一個假帳號 `linebot`：`list_my_links("該使用者")` 看不到、
`revoke_link` 也撤不掉自己建的連結。

修法在 `services/share.py` 的 `create_share_link()` 裡：actor 帶得出使用者名稱
（`user_id` 解析得到帳號）就覆蓋 `created_by`，格式與 REST 端點
（`api/share.py` 直接傳 `session.username`）一致；解析不到（未綁定、
帳號已被刪除）才退回呼叫端傳入的值。`list_my_links`／`revoke_link`／公開頁的
`shared_by` 都只是讀 `created_by` 欄位，不必另外改。既有 `created_by='linebot'`
的舊連結不受影響（沒有 backfill migration，本檔不驗這件事）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.models.share import ShareLinkCreate
from ching_tech_os.services import share
from ching_tech_os.services import permissions as permissions_module
from ching_tech_os.services.mcp import share_tools


class _CM:
    """最小 async context manager，包一個假的 connection。"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _row(**kwargs):
    now = datetime.now(timezone.utc)
    base = {
        "id": uuid4(),
        "token": "tok-218",
        "resource_type": "content",
        "resource_id": "",
        "created_by": "alice",
        "expires_at": now + timedelta(hours=1),
        "access_count": 0,
        "created_at": now,
        "content": "hi",
        "content_type": "text/plain",
        "filename": "a.txt",
        "password_hash": None,
        "attempt_count": 0,
        "locked_at": None,
        "storage_path": "x",
        "file_type": "text/plain",
        "project_id": uuid4(),
        "file_size": 10,
    }
    base.update(kwargs)
    return base


@pytest.mark.asyncio
async def test_create_share_link_uses_resolved_username_not_linebot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """actor 帶得出 user_id 時，created_by 要記解析出的使用者名稱，不是呼叫端傳入的 'linebot'。"""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)  # token 唯一性檢查：一次就過
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"username": "alice", "role": "user", "preferences": {}},  # _resolve_actor 查帳號
            _row(created_by="alice"),  # INSERT ... RETURNING
        ]
    )
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(share.settings, "public_url", "https://example.com")

    link = await share.create_share_link(
        ShareLinkCreate(resource_type="content", content="hi", filename="a.txt"),
        created_by="linebot",  # MCP 工具目前呼叫時就是傳這個字面值
        actor=share.ShareActor.from_ctos_user_id(1),
    )

    assert link.token == "tok-218"

    # INSERT 呼叫的第 4 個位置參數是 created_by（見 create_share_link 的 SQL 順序：
    # token, resource_type, resource_id, created_by, ...）
    insert_call = conn.fetchrow.await_args_list[-1]
    assert insert_call.args[4] == "alice"
    assert insert_call.args[4] != "linebot"


@pytest.mark.asyncio
async def test_create_share_link_falls_back_to_given_value_when_account_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """actor 有 user_id 但帳號已查不到（例如被刪除）：退回呼叫端傳入的 created_by。"""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(
        side_effect=[
            None,  # _resolve_actor 查不到帳號
            _row(created_by="linebot"),  # INSERT ... RETURNING
        ]
    )
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(share.settings, "public_url", "https://example.com")

    await share.create_share_link(
        ShareLinkCreate(resource_type="content", content="hi", filename="a.txt"),
        created_by="linebot",
        actor=share.ShareActor.from_ctos_user_id(999999),
    )

    insert_call = conn.fetchrow.await_args_list[-1]
    assert insert_call.args[4] == "linebot"


@pytest.mark.asyncio
async def test_create_share_link_unbound_actor_keeps_given_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未綁定（actor 沒有 user_id，或完全不給 actor）：不查帳號，created_by 原樣使用。

    回歸防護：不能因為這次修改就對 content 類型、未綁定來源等既有呼叫多打一次
    使用者查詢。
    """
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=_row(created_by="admin"))
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(share.settings, "public_url", "https://example.com")

    await share.create_share_link(
        ShareLinkCreate(resource_type="content", content="hi", filename="a.txt"),
        created_by="admin",
    )

    # 只有一次 fetchrow（INSERT），沒有額外查 users
    assert conn.fetchrow.await_count == 1
    insert_call = conn.fetchrow.await_args_list[-1]
    assert insert_call.args[4] == "admin"


@pytest.mark.asyncio
async def test_bound_user_link_then_visible_in_list_my_links_and_revocable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """驗收情境：已綁定使用者建立連結 → created_by 是該使用者 → list_my_links 看得到
    → revoke_link 撤得掉自己的連結。"""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"username": "bob", "role": "user", "preferences": {}},  # actor 解析
            _row(created_by="bob", token="tok-bob"),  # INSERT RETURNING
        ]
    )
    monkeypatch.setattr(share, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(share.settings, "public_url", "https://example.com")

    link = await share.create_share_link(
        ShareLinkCreate(resource_type="content", content="hi", filename="a.txt"),
        created_by="linebot",
        actor=share.ShareActor.from_ctos_user_id(2),
    )
    assert link.token == "tok-bob"

    # list_my_links("bob")：看得到剛剛建立的連結（created_by 真的是 bob）
    conn.fetch = AsyncMock(return_value=[_row(created_by="bob", token="tok-bob")])
    my_links = await share.list_my_links("bob")
    assert len(my_links.links) == 1
    assert my_links.links[0].token == "tok-bob"

    # revoke_link("tok-bob", username="bob")：撤得掉自己建立的連結
    conn.fetchrow = AsyncMock(return_value={"created_by": "bob"})
    conn.execute = AsyncMock(return_value="DELETE 1")
    await share.revoke_link("tok-bob", username="bob", is_admin=False)
    conn.execute.assert_awaited_once()

    # 換一個不是建立者的人撤銷：應該被擋下來（created_by 記對人，行為才會對）
    conn.fetchrow = AsyncMock(return_value={"created_by": "bob"})
    with pytest.raises(share.ShareError):
        await share.revoke_link("tok-bob", username="someone-else", is_admin=False)


@pytest.mark.asyncio
async def test_unbound_path_still_denied_before_reaching_created_by_logic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未綁定使用者建連結的路徑已被 #216 擋在 app 權限層，本次 #218 的改動
    不影響這一點：MCP 工具入口直接回拒絕訊息，share_service.create_share_link
    完全不會被呼叫（created_by 覆蓋邏輯也就不會執行到）。與
    test_mcp_share_guard.py::test_create_share_link_unbound_denied_and_service_not_awaited
    驗的是同一件事，這裡多釘一條確認修 #218 沒有意外鬆綁這一關。
    """
    monkeypatch.setattr(share_tools, "ensure_db_connection", AsyncMock())
    boom = AsyncMock(side_effect=AssertionError("share service 不該被呼叫"))
    monkeypatch.setattr(share, "create_share_link", boom)

    result = await share_tools.create_share_link(
        resource_type="knowledge", resource_id="kb-001", ctos_user_id=None
    )

    assert result == f"❌ {permissions_module.BOUND_USER_REQUIRED_MESSAGE}"
    boom.assert_not_awaited()
