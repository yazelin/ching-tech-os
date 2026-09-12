"""身分注入補齊（issue #209）＋ 權限收尾（issue #210）。

背景與 #201／#204／#205／#207 同一個根因：這套權限設計假設呼叫者是已綁定的
自己人，但 bot 對外開放。#204 只把 `resolve_bot_identity()` 套在記憶工具，
其餘吃 `line_group_id`／`line_user_id` 的工具仍然是模型說了算：

- `add_note`／`add_note_with_attachments`：id 決定知識庫的 scope 與專案歸屬，
  換一個群組 id 就能把筆記寫進別的專案範圍。
- `send_nas_file`：id 就是發送目標，換一個就能把 NAS 檔案推到別的群組。
- `summarize_chat`／`get_message_attachments`：id 就是讀取範圍，換一個就能讀
  別的群組的對話與附件。

本檔驗證每一支「有注入→用注入值、模型參數被忽略」「無注入→用參數」，
以及沒有注入時（網頁聊天）多出來的群組關聯檢查。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from ching_tech_os.services import permissions as permissions_module
from ching_tech_os.services.mcp import (
    codex_image_tools,
    knowledge_tools,
    message_tools,
    nas_tools,
    skill_script_tools,
)
from ching_tech_os.services.mcp import server as mcp_server

# 連線身分（伺服器注入）
CONN_GROUP_ID = "00000000-0000-0000-0000-000000000020"
CONN_USER_ID = "U1234567890abcdef"

# 模型宣稱的別人身分
OTHER_GROUP_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"
OTHER_USER_ID = "Udeadbeefdeadbeefdeadbeefdeadbeef"

_IDENTITY_ENV = (
    "CTOS_USER_ID",
    "CTOS_BOT_GROUP_ID",
    "CTOS_BOT_USER_ID",
    "CTOS_GROUP_ID",
)


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    for name in _IDENTITY_ENV:
        monkeypatch.delenv(name, raising=False)


def _inject_group(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in mcp_server.build_bot_mcp_env(
        line_group_id=CONN_GROUP_ID, line_user_id=CONN_USER_ID
    ).items():
        monkeypatch.setenv(name, value)


# ============================================================
# 1. resolve_conversation_scope 本身
# ============================================================


@pytest.mark.asyncio
async def test_scope_uses_injection_and_ignores_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _inject_group(monkeypatch)
    # 有注入就不該再去查關聯（查了代表走錯分支）
    monkeypatch.setattr(
        mcp_server, "_ctos_user_in_bot_group", AsyncMock(side_effect=AssertionError)
    )

    group, user, error = await mcp_server.resolve_conversation_scope(
        OTHER_GROUP_ID, OTHER_USER_ID, ctos_user_id=None
    )
    assert error is None
    assert group == CONN_GROUP_ID
    assert user == CONN_USER_ID


@pytest.mark.asyncio
async def test_scope_without_injection_requires_identity() -> None:
    """網頁聊天沒有任何身分環境變數時，讀別人的群組一律拒絕。"""
    group, user, error = await mcp_server.resolve_conversation_scope(
        OTHER_GROUP_ID, None, ctos_user_id=None
    )
    assert group is None and user is None
    assert error == mcp_server.BOT_IDENTITY_REQUIRED_MESSAGE


@pytest.mark.asyncio
async def test_scope_without_injection_checks_group_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """有 CTOS 身分就用既有關聯（bot_users.user_id ＋ bot_messages）驗一次。"""
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())
    seen: list[tuple] = []

    async def _fetchval(sql, *params):
        seen.append(params)
        # 只有 CONN_GROUP_ID 這個群組有這個人的訊息
        return 1 if params[0] == UUID(CONN_GROUP_ID) else None

    monkeypatch.setattr(
        mcp_server, "get_connection", lambda: _ConnCtx(SimpleNamespace(fetchval=_fetchval))
    )

    group, _user, error = await mcp_server.resolve_conversation_scope(
        CONN_GROUP_ID, None, ctos_user_id=7
    )
    assert error is None and group == CONN_GROUP_ID
    assert seen[-1] == (UUID(CONN_GROUP_ID), 7)

    group, _user, error = await mcp_server.resolve_conversation_scope(
        OTHER_GROUP_ID, None, ctos_user_id=7
    )
    assert group is None
    assert error == mcp_server.BOT_GROUP_SCOPE_DENIED_MESSAGE


@pytest.mark.asyncio
async def test_scope_rejects_bad_group_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())
    _group, _user, error = await mcp_server.resolve_conversation_scope(
        "not-a-uuid", None, ctos_user_id=7
    )
    assert error == mcp_server.BOT_GROUP_SCOPE_DENIED_MESSAGE


@pytest.mark.asyncio
async def test_scope_without_injection_checks_owned_bot_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())

    async def _fetchval(sql, *params):
        return 1 if params[0] == CONN_USER_ID else None

    monkeypatch.setattr(
        mcp_server, "get_connection", lambda: _ConnCtx(SimpleNamespace(fetchval=_fetchval))
    )

    _g, user, error = await mcp_server.resolve_conversation_scope(
        None, CONN_USER_ID, ctos_user_id=7
    )
    assert error is None and user == CONN_USER_ID

    _g, user, error = await mcp_server.resolve_conversation_scope(
        None, OTHER_USER_ID, ctos_user_id=7
    )
    assert user is None
    assert error == mcp_server.BOT_GROUP_SCOPE_DENIED_MESSAGE


# ============================================================
# 2. message_tools：summarize_chat / get_message_attachments
# ============================================================


@pytest.fixture
def _message_conn(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(message_tools, "ensure_db_connection", AsyncMock())
    conn = SimpleNamespace(
        fetch=AsyncMock(return_value=[]),
        fetchrow=AsyncMock(return_value={"name": "示範群組"}),
    )
    monkeypatch.setattr(message_tools, "get_connection", lambda: _ConnCtx(conn))
    return conn


@pytest.mark.asyncio
async def test_summarize_chat_uses_injected_group(
    monkeypatch: pytest.MonkeyPatch, _message_conn
) -> None:
    _inject_group(monkeypatch)
    await message_tools.summarize_chat(OTHER_GROUP_ID)
    assert _message_conn.fetch.call_args.args[1] == UUID(CONN_GROUP_ID)


@pytest.mark.asyncio
async def test_summarize_chat_uses_param_without_injection(
    monkeypatch: pytest.MonkeyPatch, _message_conn
) -> None:
    monkeypatch.setattr(mcp_server, "_ctos_user_in_bot_group", AsyncMock(return_value=True))
    await message_tools.summarize_chat(OTHER_GROUP_ID, ctos_user_id=7)
    assert _message_conn.fetch.call_args.args[1] == UUID(OTHER_GROUP_ID)


@pytest.mark.asyncio
async def test_summarize_chat_denies_foreign_group(
    monkeypatch: pytest.MonkeyPatch, _message_conn
) -> None:
    monkeypatch.setattr(mcp_server, "_ctos_user_in_bot_group", AsyncMock(return_value=False))
    result = await message_tools.summarize_chat(OTHER_GROUP_ID, ctos_user_id=7)
    assert result.startswith("❌")
    _message_conn.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_message_attachments_uses_injected_group(
    monkeypatch: pytest.MonkeyPatch, _message_conn
) -> None:
    _inject_group(monkeypatch)
    await message_tools.get_message_attachments(line_group_id=OTHER_GROUP_ID)
    assert UUID(CONN_GROUP_ID) in _message_conn.fetch.call_args.args


@pytest.mark.asyncio
async def test_get_message_attachments_denies_foreign_group(
    monkeypatch: pytest.MonkeyPatch, _message_conn
) -> None:
    monkeypatch.setattr(mcp_server, "_ctos_user_in_bot_group", AsyncMock(return_value=False))
    result = await message_tools.get_message_attachments(
        line_group_id=OTHER_GROUP_ID, ctos_user_id=7
    )
    assert result.startswith("❌")
    _message_conn.fetch.assert_not_awaited()


# ============================================================
# 3. knowledge_tools：add_note / add_note_with_attachments / search_knowledge
# ============================================================


@pytest.fixture
def _knowledge_scope_spy(monkeypatch: pytest.MonkeyPatch):
    """攔 `_determine_knowledge_scope`，記下工具實際拿去決定 scope 的身分。"""
    seen: list[tuple] = []

    async def _determine(line_group_id, line_user_id, ctos_user_id):
        seen.append((line_group_id, line_user_id, ctos_user_id))
        return "global", "someone", None

    monkeypatch.setattr(knowledge_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        knowledge_tools, "check_mcp_tool_permission", AsyncMock(return_value=(True, ""))
    )
    monkeypatch.setattr(knowledge_tools, "_determine_knowledge_scope", _determine)
    monkeypatch.setattr(
        "ching_tech_os.services.knowledge.create_knowledge",
        lambda *_a, **_k: SimpleNamespace(id="kb-001", title="t"),
    )
    return seen


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["add_note", "add_note_with_attachments"])
async def test_add_note_uses_injected_identity(
    tool_name: str, monkeypatch: pytest.MonkeyPatch, _knowledge_scope_spy
) -> None:
    monkeypatch.setenv("CTOS_USER_ID", "7")
    _inject_group(monkeypatch)

    tool = getattr(knowledge_tools, tool_name)
    kwargs = {"attachments": []} if tool_name == "add_note_with_attachments" else {}
    await tool(
        title="標題",
        content="內容",
        line_group_id=OTHER_GROUP_ID,
        line_user_id=OTHER_USER_ID,
        **kwargs,
    )
    assert _knowledge_scope_spy[-1][:2] == (CONN_GROUP_ID, CONN_USER_ID)


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["add_note", "add_note_with_attachments"])
async def test_add_note_uses_param_without_injection(
    tool_name: str, monkeypatch: pytest.MonkeyPatch, _knowledge_scope_spy
) -> None:
    monkeypatch.setenv("CTOS_USER_ID", "7")

    tool = getattr(knowledge_tools, tool_name)
    kwargs = {"attachments": []} if tool_name == "add_note_with_attachments" else {}
    await tool(
        title="標題",
        content="內容",
        line_group_id=OTHER_GROUP_ID,
        **kwargs,
    )
    assert _knowledge_scope_spy[-1][:2] == (OTHER_GROUP_ID, None)


@pytest.mark.asyncio
async def test_search_knowledge_resolves_bot_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`line_user_id` 目前還沒被拿去分範圍，但已經先接上注入。

    用 `resolve_bot_identity` 的覆寫 warning 當觀察點：模型帶別人的 id 時，
    工具實際採用的是連線身分。
    """
    monkeypatch.setattr(knowledge_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        knowledge_tools, "check_mcp_tool_permission", AsyncMock(return_value=(True, ""))
    )
    monkeypatch.setattr(
        "ching_tech_os.services.knowledge.search_knowledge",
        lambda **_k: SimpleNamespace(items=[]),
    )

    seen: list[tuple] = []
    real_resolve = mcp_server.resolve_bot_identity

    def _spy(line_group_id, line_user_id):
        seen.append((line_group_id, line_user_id))
        return real_resolve(line_group_id, line_user_id)

    monkeypatch.setattr(knowledge_tools, "resolve_bot_identity", _spy)
    _inject_group(monkeypatch)

    await knowledge_tools.search_knowledge("關鍵字", line_user_id=OTHER_USER_ID)
    assert seen == [(None, OTHER_USER_ID)]


# ============================================================
# 4. nas_tools：send_nas_file 的發送目標
# ============================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "inject, expected_group",
    [(True, CONN_GROUP_ID), (False, OTHER_GROUP_ID)],
)
async def test_send_nas_file_target_group(
    inject: bool,
    expected_group: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """發送目標：有注入就是注入的群組，沒注入才用模型帶的。"""
    import ching_tech_os.services.bot_line as line_module
    import ching_tech_os.services.share as share_module

    monkeypatch.setattr(nas_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        nas_tools, "check_mcp_tool_permission", AsyncMock(return_value=(True, ""))
    )
    monkeypatch.setattr(nas_tools, "_get_user_shared_mounts", AsyncMock(return_value={}))
    monkeypatch.setattr(
        nas_tools, "_require_share_manager_for_link", AsyncMock(return_value=None)
    )

    img = tmp_path / "a.jpg"
    img.write_bytes(b"x" * 100)
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p, **_k: img)
    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(return_value=SimpleNamespace(full_url="https://example.test/s/abc")),
    )
    monkeypatch.setattr(line_module, "push_image", AsyncMock(return_value=("m1", None)))
    monkeypatch.setattr(line_module, "push_text", AsyncMock(return_value=("m2", None)))

    conn = SimpleNamespace(fetchrow=AsyncMock(return_value={"platform_group_id": "G1"}))
    monkeypatch.setattr(nas_tools, "get_connection", lambda: _ConnCtx(conn))

    if inject:
        _inject_group(monkeypatch)

    out = await nas_tools.send_nas_file(
        "shared://projects/a.jpg", line_group_id=OTHER_GROUP_ID, ctos_user_id=1
    )
    assert "已發送圖片" in out
    assert conn.fetchrow.call_args.args[1] == UUID(expected_group)


# ============================================================
# 5. issue #210：改走權限檢查的工具，未綁定要被擋且 service 沒被 await
# ============================================================


@pytest.mark.asyncio
async def test_run_skill_script_denies_unbound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(skill_script_tools, "ensure_db_connection", AsyncMock())
    runner = MagicMock(side_effect=AssertionError("未綁定不該跑到 ScriptRunner"))
    monkeypatch.setattr("ching_tech_os.skills.script_runner.ScriptRunner", runner)

    result = json.loads(
        await skill_script_tools.run_skill_script("demo-skill", "run", ctos_user_id=None)
    )
    assert result["success"] is False
    assert result["error"] == permissions_module.BOUND_USER_REQUIRED_MESSAGE
    runner.assert_not_called()


@pytest.mark.asyncio
async def test_codex_image_tool_denies_unbound(monkeypatch: pytest.MonkeyPatch) -> None:
    """`reference_images` 會讀 NAS 的檔案送到外部服務，所以對到 file-manager。"""
    available = AsyncMock()
    monkeypatch.setattr(codex_image_tools, "is_codex_image_available", available)
    generate = AsyncMock()
    monkeypatch.setattr(codex_image_tools, "generate_image_with_codex", generate)

    result = await codex_image_tool_call()
    assert result.startswith("❌")
    assert permissions_module.BOUND_USER_REQUIRED_MESSAGE in result
    available.assert_not_called()
    generate.assert_not_awaited()


async def codex_image_tool_call() -> str:
    return await codex_image_tools.codex_image_tool(prompt="一隻貓", ctos_user_id=None)
