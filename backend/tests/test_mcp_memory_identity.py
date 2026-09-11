"""記憶工具的身分來自連線，不是模型自己宣稱的（issue #204）。

背景與 #201／#206／#207 同一個根因：這套權限設計假設呼叫者是已綁定的自己人，
但 bot 對外開放。`memory_tools.py` 的四支工具直接吃模型帶進來的 `line_group_id`／
`line_user_id`，system prompt 又把這兩個 id 寫在裡面——模型（或誘導模型的使用者）
換一個 id，就能讀寫別的群組／別人的記憶。

修法照 `resolve_ctos_user_id`：伺服器注入優先，模型參數只在沒有注入時採用
（網頁端 `execute_tool` 沒有子行程環境變數，維持吃參數）。

本檔驗證：
- `resolve_bot_identity` 的真值表（注入優先、覆寫時記 warning、無注入才用參數）。
- 四支工具實際落到資料庫的身分是注入值，不是模型帶的值。
- `build_bot_mcp_env` 產出的變數名稱（呼叫端與工具端共用同一份事實）。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from ching_tech_os.services.mcp import memory_tools
from ching_tech_os.services.mcp import server as mcp_server

# 連線身分（伺服器注入）
CONN_GROUP_ID = "00000000-0000-0000-0000-000000000020"
CONN_USER_ID = "U1234567890abcdef"
CONN_BOT_USER_UUID = UUID("00000000-0000-0000-0000-000000000010")

# 模型宣稱的別人身分
OTHER_GROUP_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"
OTHER_USER_ID = "Udeadbeefdeadbeefdeadbeefdeadbeef"


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    for name in ("CTOS_BOT_GROUP_ID", "CTOS_BOT_USER_ID", "CTOS_GROUP_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(memory_tools, "ensure_db_connection", AsyncMock())


@pytest.fixture
def _conn(monkeypatch: pytest.MonkeyPatch):
    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value={"id": UUID(int=1)}),
        fetch=AsyncMock(return_value=[]),
        execute=AsyncMock(return_value="UPDATE 0"),
    )
    monkeypatch.setattr(memory_tools, "get_connection", lambda: _ConnCtx(conn))
    return conn


@pytest.fixture
def _bot_user_lookup(monkeypatch: pytest.MonkeyPatch):
    """攔截 platform_user_id → bot_users.id 的查詢，記下被查的 id。"""
    seen: list[str] = []

    async def _get_line_user_record(platform_user_id: str, columns: str = "*"):
        seen.append(platform_user_id)
        return {"id": CONN_BOT_USER_UUID}

    import ching_tech_os.services.bot_line as bot_line

    monkeypatch.setattr(bot_line, "get_line_user_record", _get_line_user_record)
    return seen


# ============================================================
# 1. resolve_bot_identity 真值表
# ============================================================


def test_env_group_wins_over_model_param(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTOS_BOT_GROUP_ID", CONN_GROUP_ID)
    monkeypatch.setenv("CTOS_BOT_USER_ID", CONN_USER_ID)

    assert mcp_server.resolve_bot_identity(OTHER_GROUP_ID, None) == (CONN_GROUP_ID, None)


def test_env_user_wins_over_model_param(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTOS_BOT_USER_ID", CONN_USER_ID)

    assert mcp_server.resolve_bot_identity(None, OTHER_USER_ID) == (None, CONN_USER_ID)


def test_model_asking_for_other_group_in_private_chat_falls_back_to_self(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """個人對話（沒有注入群組）卻宣稱群組 id：退回連線身分，不採用模型的 id。"""
    monkeypatch.setenv("CTOS_BOT_USER_ID", CONN_USER_ID)

    assert mcp_server.resolve_bot_identity(OTHER_GROUP_ID, None) == (None, CONN_USER_ID)


def test_legacy_ctos_group_id_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """群組沿用既有的 CTOS_GROUP_ID（語音設定已經在注入同一個值）。"""
    monkeypatch.setenv("CTOS_GROUP_ID", CONN_GROUP_ID)

    assert mcp_server.resolve_bot_identity(OTHER_GROUP_ID, None) == (CONN_GROUP_ID, None)


def test_no_env_uses_model_params(monkeypatch: pytest.MonkeyPatch) -> None:
    """網頁端 execute_tool 沒有子行程環境變數，維持吃參數。"""
    assert mcp_server.resolve_bot_identity(OTHER_GROUP_ID, None) == (OTHER_GROUP_ID, None)
    assert mcp_server.resolve_bot_identity(None, OTHER_USER_ID) == (None, OTHER_USER_ID)
    assert mcp_server.resolve_bot_identity(None, None) == (None, None)


def test_override_logs_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CTOS_BOT_GROUP_ID", CONN_GROUP_ID)

    with caplog.at_level("WARNING", logger="mcp_server"):
        mcp_server.resolve_bot_identity(OTHER_GROUP_ID, None)

    assert "[memory] 模型帶入的 id 與連線身分不符，已改用連線身分" in caplog.text


def test_no_warning_when_model_matches_connection(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CTOS_BOT_GROUP_ID", CONN_GROUP_ID)

    with caplog.at_level("WARNING", logger="mcp_server"):
        mcp_server.resolve_bot_identity(CONN_GROUP_ID, None)

    assert "不符" not in caplog.text


# ============================================================
# 2. 注入的環境變數名稱（呼叫端與工具端共用同一份事實）
# ============================================================


def test_build_bot_mcp_env_names() -> None:
    env = mcp_server.build_bot_mcp_env(
        line_group_id=CONN_GROUP_ID, line_user_id=CONN_USER_ID, agent_id="a-1"
    )
    assert env["CTOS_BOT_GROUP_ID"] == CONN_GROUP_ID
    assert env["CTOS_BOT_USER_ID"] == CONN_USER_ID
    # 語音設定已經在用的舊名，一併注入避免兩套名字打架
    assert env["CTOS_GROUP_ID"] == CONN_GROUP_ID
    assert env["CTOS_AGENT_ID"] == "a-1"


def test_build_bot_mcp_env_private_chat_has_no_group() -> None:
    env = mcp_server.build_bot_mcp_env(line_group_id=None, line_user_id=CONN_USER_ID)
    assert "CTOS_BOT_GROUP_ID" not in env
    assert "CTOS_GROUP_ID" not in env
    assert env["CTOS_BOT_USER_ID"] == CONN_USER_ID


# ============================================================
# 3. add_memory：寫進去的是連線身分
# ============================================================


@pytest.mark.asyncio
async def test_add_memory_group_uses_injected_group(
    monkeypatch: pytest.MonkeyPatch, _conn
) -> None:
    monkeypatch.setenv("CTOS_BOT_GROUP_ID", CONN_GROUP_ID)
    _conn.fetchrow = AsyncMock(return_value={"id": UUID(int=7)})

    await memory_tools.add_memory(
        content="偷寫到別的群組", line_group_id=OTHER_GROUP_ID
    )

    args = _conn.fetchrow.await_args.args
    assert "bot_group_memories" in args[0]
    assert args[1] == UUID(CONN_GROUP_ID)


@pytest.mark.asyncio
async def test_add_memory_personal_uses_injected_user(
    monkeypatch: pytest.MonkeyPatch, _conn, _bot_user_lookup
) -> None:
    monkeypatch.setenv("CTOS_BOT_USER_ID", CONN_USER_ID)
    _conn.fetchrow = AsyncMock(return_value={"id": UUID(int=8)})

    await memory_tools.add_memory(content="偷寫到別人身上", line_user_id=OTHER_USER_ID)

    assert _bot_user_lookup == [CONN_USER_ID]
    args = _conn.fetchrow.await_args.args
    assert "bot_user_memories" in args[0]
    assert args[1] == CONN_BOT_USER_UUID


@pytest.mark.asyncio
async def test_add_memory_without_env_uses_param(
    monkeypatch: pytest.MonkeyPatch, _conn
) -> None:
    """網頁端：沒有注入就照參數走（否則管理介面會壞）。"""
    _conn.fetchrow = AsyncMock(return_value={"id": UUID(int=9)})

    await memory_tools.add_memory(content="網頁端", line_group_id=OTHER_GROUP_ID)

    assert _conn.fetchrow.await_args.args[1] == UUID(OTHER_GROUP_ID)


# ============================================================
# 4. get_memories：讀的是連線身分
# ============================================================


@pytest.mark.asyncio
async def test_get_memories_group_uses_injected_group(
    monkeypatch: pytest.MonkeyPatch, _conn
) -> None:
    monkeypatch.setenv("CTOS_BOT_GROUP_ID", CONN_GROUP_ID)

    await memory_tools.get_memories(line_group_id=OTHER_GROUP_ID)

    args = _conn.fetch.await_args.args
    assert "bot_group_memories" in args[0]
    assert args[1] == UUID(CONN_GROUP_ID)


@pytest.mark.asyncio
async def test_get_memories_personal_uses_injected_user(
    monkeypatch: pytest.MonkeyPatch, _conn, _bot_user_lookup
) -> None:
    monkeypatch.setenv("CTOS_BOT_USER_ID", CONN_USER_ID)

    await memory_tools.get_memories(line_user_id=OTHER_USER_ID)

    assert _bot_user_lookup == [CONN_USER_ID]
    assert _conn.fetch.await_args.args[1] == CONN_BOT_USER_UUID


@pytest.mark.asyncio
async def test_get_memories_in_group_ignores_model_group_claim(
    monkeypatch: pytest.MonkeyPatch, _conn
) -> None:
    """群組對話中模型不帶任何 id，也只讀得到這個群組。"""
    monkeypatch.setenv("CTOS_BOT_GROUP_ID", CONN_GROUP_ID)
    monkeypatch.setenv("CTOS_BOT_USER_ID", CONN_USER_ID)

    await memory_tools.get_memories()

    assert _conn.fetch.await_args.args[1] == UUID(CONN_GROUP_ID)


# ============================================================
# 5. update_memory／delete_memory：只能動連線身分底下的記憶
# ============================================================

MEMORY_ID = "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_update_memory_scoped_to_injected_group(
    monkeypatch: pytest.MonkeyPatch, _conn
) -> None:
    monkeypatch.setenv("CTOS_BOT_GROUP_ID", CONN_GROUP_ID)
    _conn.execute = AsyncMock(return_value="UPDATE 0")

    result = await memory_tools.update_memory(memory_id=MEMORY_ID, title="改別人的")

    sql, *params = _conn.execute.await_args.args
    assert "bot_group_id = $" in sql
    assert UUID(CONN_GROUP_ID) in params
    assert "找不到" in result


@pytest.mark.asyncio
async def test_delete_memory_scoped_to_injected_group(
    monkeypatch: pytest.MonkeyPatch, _conn
) -> None:
    monkeypatch.setenv("CTOS_BOT_GROUP_ID", CONN_GROUP_ID)
    _conn.execute = AsyncMock(return_value="DELETE 0")

    result = await memory_tools.delete_memory(memory_id=MEMORY_ID)

    sql, *params = _conn.execute.await_args.args
    assert "bot_group_id = $" in sql
    assert UUID(CONN_GROUP_ID) in params
    assert "找不到" in result


@pytest.mark.asyncio
async def test_delete_memory_scoped_to_injected_user(
    monkeypatch: pytest.MonkeyPatch, _conn, _bot_user_lookup
) -> None:
    monkeypatch.setenv("CTOS_BOT_USER_ID", CONN_USER_ID)
    _conn.execute = AsyncMock(return_value="DELETE 0")

    await memory_tools.delete_memory(memory_id=MEMORY_ID)

    sql, *params = _conn.execute.await_args.args
    assert "bot_user_id = $" in sql
    assert CONN_BOT_USER_UUID in params
    assert _bot_user_lookup == [CONN_USER_ID]


@pytest.mark.asyncio
async def test_delete_memory_without_env_is_unscoped(
    monkeypatch: pytest.MonkeyPatch, _conn
) -> None:
    """網頁端管理介面維持現狀（沒有連線身分可用）。"""
    _conn.execute = AsyncMock(return_value="DELETE 1")

    result = await memory_tools.delete_memory(memory_id=MEMORY_ID)

    sql, *_params = _conn.execute.await_args.args
    assert "bot_group_id = $" not in sql
    assert "✅" in result


@pytest.mark.asyncio
async def test_update_memory_group_hit_returns_success(
    monkeypatch: pytest.MonkeyPatch, _conn
) -> None:
    monkeypatch.setenv("CTOS_BOT_GROUP_ID", CONN_GROUP_ID)
    _conn.execute = AsyncMock(return_value="UPDATE 1")

    result = await memory_tools.update_memory(memory_id=MEMORY_ID, content="改自己的")

    assert "✅" in result
