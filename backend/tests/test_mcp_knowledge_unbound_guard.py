"""未綁定 CTOS 帳號的 bot 使用者不得寫入知識庫（issue #207）。

背景與 #201／#206 同一個根因：這套權限設計假設呼叫者是已綁定的自己人，但 bot 對外
開放，未綁定者一路走得進來。`knowledge-base` 不在 `APPS_REQUIRE_BOUND_USER`
（讀取端已用條目層級只放行 `scope=global` 且 `is_public` 的條目），但 `add_note`／
`add_note_with_attachments` 完全不看條目，未綁定者直接寫進全域知識庫。

本檔驗證：
- `add_note`／`add_note_with_attachments`：未綁定一律拒絕，且 `create_knowledge`
  完全沒被呼叫（不是「寫了但標成 personal」的折衷）。
- 其餘寫入工具（`update_knowledge_item`／`delete_knowledge_item`／
  `add_attachments_to_knowledge`／`update_knowledge_attachment`）：reviewer 說
  `_check_item_access` 已擋，這裡逐一釘住，不只信 review。
- 讀取工具（`search_knowledge`／`get_knowledge_item`／`read_knowledge_attachment`）：
  未綁定「只讀 global 且 is_public」的現狀維持並釘住。
- 已綁定使用者行為不變（對照組）。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services import knowledge as kb_service
from ching_tech_os.services import permissions as permissions_module
from ching_tech_os.services.mcp import knowledge_tools
from ching_tech_os.services.mcp import server as mcp_server


class _ConnCtx:
    """最小 async context manager，包一個假的 connection。"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _item(**kwargs):
    """假的 KnowledgeResponse（只用到工具會看的欄位）。"""
    base = {
        "id": "kb-001",
        "title": "測試知識",
        "scope": "global",
        "is_public": True,
        "owner": None,
        "project_id": None,
        "category": "note",
        "content": "內容",
        "tags": SimpleNamespace(topics=[], projects=[], roles=[], level=None),
        "attachments": [],
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


_WRITE_FUNCS = (
    "create_knowledge",
    "update_knowledge",
    "delete_knowledge",
    "update_attachment",
    "delete_attachment",
    "copy_linebot_attachment_to_knowledge",
)


@pytest.fixture(autouse=True)
def _isolated_kb(monkeypatch: pytest.MonkeyPatch):
    """本檔不碰真的知識庫與資料庫：

    - 清掉環境殘留的 CTOS_USER_ID，未綁定測試才算數。
    - 所有 kb_service 寫入函式預設炸開；要驗證「有寫入」的測試自己覆寫。
      （否則測試會真的把筆記寫進 data/knowledge。）
    """
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    monkeypatch.setattr(knowledge_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())

    def _unexpected_write(name):
        def _boom(*_args, **_kwargs):
            raise AssertionError(f"未預期的知識庫寫入：{name}")

        return _boom

    for func_name in _WRITE_FUNCS:
        monkeypatch.setattr(kb_service, func_name, _unexpected_write(func_name))


@pytest.fixture
def _bound_user(monkeypatch: pytest.MonkeyPatch):
    """已綁定的一般使用者：users 查得到、知識權限走既有邏輯。"""
    row = {"username": "yaze", "role": "user", "preferences": {}, "id": 1}
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value=row))
    monkeypatch.setattr(knowledge_tools, "get_connection", lambda: _ConnCtx(conn))
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))
    return conn


# ============================================================
# 1. add_note／add_note_with_attachments：未綁定一律拒絕（#207）
# ============================================================


@pytest.mark.asyncio
async def test_add_note_unbound_denied_and_service_not_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("未綁定不該寫進知識庫")

    monkeypatch.setattr(kb_service, "create_knowledge", _boom)

    result = await knowledge_tools.add_note(
        title="外人的筆記",
        content="這不該進知識庫",
        ctos_user_id=None,
    )

    assert result == f"❌ {permissions_module.BOUND_USER_REQUIRED_MESSAGE}"


@pytest.mark.asyncio
async def test_add_note_with_attachments_unbound_denied_and_service_not_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("未綁定不該寫進知識庫")

    monkeypatch.setattr(kb_service, "create_knowledge", _boom)
    monkeypatch.setattr(kb_service, "copy_linebot_attachment_to_knowledge", _boom)

    result = await knowledge_tools.add_note_with_attachments(
        title="外人的筆記",
        content="這不該進知識庫",
        attachments=["nas://linebot/a.jpg"],
        ctos_user_id=None,
    )

    assert result == f"❌ {permissions_module.BOUND_USER_REQUIRED_MESSAGE}"


@pytest.mark.asyncio
async def test_add_note_unbound_denied_even_with_group_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """群組對話（line_group_id 有值）也一樣擋：#207 不做「群組就放行」的折衷。"""

    def _boom(*_args, **_kwargs):
        raise AssertionError("未綁定不該寫進知識庫")

    monkeypatch.setattr(kb_service, "create_knowledge", _boom)
    monkeypatch.setattr(
        knowledge_tools,
        "_determine_knowledge_scope",
        AsyncMock(side_effect=AssertionError("不該走到 scope 判斷")),
    )

    result = await knowledge_tools.add_note(
        title="外人的筆記",
        content="這不該進知識庫",
        line_group_id="00000000-0000-0000-0000-000000000020",
        ctos_user_id=None,
    )

    assert result == f"❌ {permissions_module.BOUND_USER_REQUIRED_MESSAGE}"


@pytest.mark.asyncio
async def test_add_note_denial_message_matches_bind_flow() -> None:
    """訊息沿用 #206 的 BOUND_USER_REQUIRED_MESSAGE（同一套綁定流程說明）。"""
    result = await knowledge_tools.add_note(title="t", content="c", ctos_user_id=None)
    assert "驗證碼" in result
    assert "輸入「綁定」" not in result


@pytest.mark.asyncio
async def test_add_note_uses_env_identity_when_injected(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    """伺服器注入 CTOS_USER_ID（已綁定）時照常寫入——擋的是未綁定，不是全部擋掉。"""
    monkeypatch.setenv("CTOS_USER_ID", "1")
    created = {}

    def _create(data, owner=None, project_id=None):
        created["data"] = data
        created["owner"] = owner
        return SimpleNamespace(id="kb-999", title=data.title)

    monkeypatch.setattr(kb_service, "create_knowledge", _create)

    result = await knowledge_tools.add_note(
        title="自己人的筆記", content="內容", ctos_user_id=None
    )

    assert "✅" in result
    assert created["owner"] == "yaze"


@pytest.mark.asyncio
async def test_add_note_bound_user_still_writes(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    """對照組：已綁定使用者維持可寫入。"""
    calls = {}

    def _create(data, owner=None, project_id=None):
        calls["called"] = True
        return SimpleNamespace(id="kb-998", title=data.title)

    monkeypatch.setattr(kb_service, "create_knowledge", _create)

    result = await knowledge_tools.add_note(
        title="自己人的筆記", content="內容", ctos_user_id=1
    )

    assert calls.get("called") is True
    assert "✅" in result


@pytest.mark.asyncio
async def test_add_note_with_attachments_bound_user_still_writes(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    monkeypatch.setattr(
        kb_service,
        "create_knowledge",
        lambda data, owner=None, project_id=None: SimpleNamespace(
            id="kb-997", title=data.title
        ),
    )
    copied = []
    monkeypatch.setattr(
        kb_service,
        "copy_linebot_attachment_to_knowledge",
        lambda kb_id, path: copied.append((kb_id, path)),
    )

    result = await knowledge_tools.add_note_with_attachments(
        title="自己人的筆記",
        content="內容",
        attachments=["nas://linebot/a.jpg"],
        ctos_user_id=1,
    )

    assert copied == [("kb-997", "nas://linebot/a.jpg")]
    assert "✅" in result


# ============================================================
# 2. 其餘寫入工具：釘住 _check_item_access 真的擋得住未綁定
# ============================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("scope, is_public", [("global", True), ("personal", False)])
async def test_update_knowledge_item_unbound_denied(
    monkeypatch: pytest.MonkeyPatch, scope: str, is_public: bool
) -> None:
    monkeypatch.setattr(
        kb_service, "get_knowledge", lambda kb_id: _item(scope=scope, is_public=is_public)
    )

    def _boom(*_args, **_kwargs):
        raise AssertionError("未綁定不該更新知識")

    monkeypatch.setattr(kb_service, "update_knowledge", _boom)

    result = await knowledge_tools.update_knowledge_item(
        kb_id="kb-001", title="改標題", ctos_user_id=None
    )

    assert result == "❌ 此操作需要綁定 CTOS 帳號"


@pytest.mark.asyncio
async def test_delete_knowledge_item_unbound_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kb_service, "get_knowledge", lambda kb_id: _item())

    def _boom(*_args, **_kwargs):
        raise AssertionError("未綁定不該刪除知識")

    monkeypatch.setattr(kb_service, "delete_knowledge", _boom)

    result = await knowledge_tools.delete_knowledge_item(kb_id="kb-001", ctos_user_id=None)

    assert result == "❌ 此操作需要綁定 CTOS 帳號"


@pytest.mark.asyncio
async def test_add_attachments_to_knowledge_unbound_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kb_service, "get_knowledge", lambda kb_id: _item())

    def _boom(*_args, **_kwargs):
        raise AssertionError("未綁定不該加附件")

    monkeypatch.setattr(kb_service, "copy_linebot_attachment_to_knowledge", _boom)

    result = await knowledge_tools.add_attachments_to_knowledge(
        kb_id="kb-001", attachments=["nas://linebot/a.jpg"], ctos_user_id=None
    )

    assert result == "❌ 此操作需要綁定 CTOS 帳號"


@pytest.mark.asyncio
async def test_update_knowledge_attachment_unbound_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kb_service, "get_knowledge", lambda kb_id: _item())

    def _boom(*_args, **_kwargs):
        raise AssertionError("未綁定不該改附件說明")

    monkeypatch.setattr(kb_service, "update_attachment", _boom)

    result = await knowledge_tools.update_knowledge_attachment(
        kb_id="kb-001", attachment_index=0, description="說明", ctos_user_id=None
    )

    assert result == "❌ 此操作需要綁定 CTOS 帳號"


# ============================================================
# 3. 讀取工具：未綁定「只讀 global 且 is_public」維持現狀
# ============================================================


@pytest.mark.asyncio
async def test_search_knowledge_unbound_is_public_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {}

    def _search(**kwargs):
        called["kwargs"] = kwargs
        return SimpleNamespace(items=[])

    monkeypatch.setattr(kb_service, "search_knowledge", _search)

    await knowledge_tools.search_knowledge(query="測試", ctos_user_id=None)

    assert called["kwargs"]["public_only"] is True


@pytest.mark.asyncio
async def test_get_knowledge_item_unbound_reads_public_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        kb_service,
        "get_knowledge",
        lambda kb_id: _item(scope="global", is_public=True, content="公開內容"),
    )

    result = await knowledge_tools.get_knowledge_item(kb_id="kb-001", ctos_user_id=None)

    assert "公開內容" in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope, is_public",
    [("global", False), ("personal", False), ("personal", True), ("project", True)],
)
async def test_get_knowledge_item_unbound_cannot_read_non_public(
    monkeypatch: pytest.MonkeyPatch, scope: str, is_public: bool
) -> None:
    monkeypatch.setattr(
        kb_service,
        "get_knowledge",
        lambda kb_id: _item(scope=scope, is_public=is_public, content="機密內容"),
    )

    result = await knowledge_tools.get_knowledge_item(kb_id="kb-001", ctos_user_id=None)

    assert result == "找不到知識 kb-001"
    assert "機密內容" not in result


@pytest.mark.asyncio
async def test_read_knowledge_attachment_unbound_cannot_read_personal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        kb_service,
        "get_knowledge",
        lambda kb_id: _item(scope="personal", is_public=False),
    )

    result = await knowledge_tools.read_knowledge_attachment(
        kb_id="kb-001", ctos_user_id=None
    )

    assert result == "找不到知識 kb-001"


@pytest.mark.asyncio
async def test_get_knowledge_attachments_unbound_cannot_read_personal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        kb_service,
        "get_knowledge",
        lambda kb_id: _item(scope="personal", is_public=False),
    )

    result = await knowledge_tools.get_knowledge_attachments(
        kb_id="kb-001", ctos_user_id=None
    )

    assert result == "找不到知識 kb-001"


# ============================================================
# 4. registry 本身（矩陣與程式共用同一份事實）
# ============================================================


def test_tools_require_bound_user_registry() -> None:
    """工具內部自檢的 registry：新增寫入工具忘了加，這條與矩陣測試會一起紅。"""
    assert permissions_module.TOOLS_REQUIRE_BOUND_USER == {
        "add_note",
        "add_note_with_attachments",
        # issue #210：會在 NAS 產檔／建立對外分享連結／跑伺服器上的程式
        "generate_presentation",
        "generate_md2ppt",
        "generate_md2doc",
        "run_skill_script",
    }
