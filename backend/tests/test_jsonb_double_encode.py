"""jsonb 欄位不得雙重編碼（issue #240）

`database.py` 為每條連線註冊了 json/jsonb codec（encoder 是 `json.dumps`），
所以寫入端一律直接傳 Python dict/list。這裡的測試釘住三件事：

1. 寫入端傳給 asyncpg 的參數是 dict/list，不是 `json.dumps` 出來的字串
2. 讀取端遇到舊資料（雙重編碼的字串、被 `||` 串壞的陣列）不會炸開也不會回傳垃圾
3. PUT 之後 GET 讀得到新值（用一個模擬 PostgreSQL jsonb 語意的假連線跑完整迴圈）
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services import ai_chat as ai_chat_service
from ching_tech_os.services import ai_manager as ai_manager_service
from ching_tech_os.services import erp as erp_core
from ching_tech_os.services import message as message_service
from ching_tech_os.services import permissions as permissions_service
from ching_tech_os.services import user as user_service
from ching_tech_os.utils.jsonb import parse_json_dict, parse_json_field

# 壞掉的列長這樣：'{}'::jsonb || '"{\"theme\": \"light\"}"'::jsonb
CORRUPTED_PREFERENCES = [{}, '{"theme": "light"}']


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _patch_conn(monkeypatch: pytest.MonkeyPatch, module, conn) -> None:
    monkeypatch.setattr(module, "get_connection", lambda: _ConnCtx(conn))


def _assert_not_double_encoded(params) -> None:
    """參數裡不可以出現 json.dumps 出來的 JSON 字串"""
    for param in params:
        if isinstance(param, str) and param.strip()[:1] in ("{", "["):
            raise AssertionError(f"參數被雙重編碼成 JSON 字串：{param!r}")


# ============================================================
# utils.jsonb
# ============================================================


def test_parse_json_field_and_dict() -> None:
    assert parse_json_field(None) is None
    assert parse_json_field(None, {"a": 1}) == {"a": 1}
    assert parse_json_field('{"a": 1}') == {"a": 1}
    assert parse_json_field(b'[1, 2]') == [1, 2]
    assert parse_json_field("{bad}", "fallback") == "fallback"
    assert parse_json_field({"a": 1}) == {"a": 1}

    assert parse_json_dict('{"a": 1}') == {"a": 1}
    assert parse_json_dict(CORRUPTED_PREFERENCES) == {}
    assert parse_json_dict('"just a string"') == {}
    assert parse_json_dict(None) == {}


# ============================================================
# 寫入端：參數必須是 dict / list
# ============================================================


@pytest.mark.asyncio
async def test_update_user_preferences_passes_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value={"preferences": {"theme": "light"}}))
    _patch_conn(monkeypatch, user_service, conn)

    result = await user_service.update_user_preferences(1, {"theme": "light"})

    assert result == {"theme": "light"}
    sql, args = conn.fetchrow.await_args.args[0], conn.fetchrow.await_args.args[1:]
    _assert_not_double_encoded(args)
    assert args[1] == {"theme": "light"}
    assert isinstance(args[1], dict)
    # 壞掉的列不可以再用 || 合併
    assert "jsonb_typeof(preferences) = 'object'" in sql


@pytest.mark.asyncio
async def test_update_user_permissions_passes_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(
        fetchrow=AsyncMock(
            side_effect=[
                {"preferences": {"permissions": {"apps": {"a": True}}}},
                {"preferences": {"permissions": {"apps": {"a": True, "b": False}}}},
            ]
        )
    )
    _patch_conn(monkeypatch, user_service, conn)

    await user_service.update_user_permissions(1, {"apps": {"b": False}})

    args = conn.fetchrow.await_args.args[1:]
    _assert_not_double_encoded(args)
    assert isinstance(args[1], dict)
    assert args[1]["permissions"]["apps"] == {"a": True, "b": False}


@pytest.mark.asyncio
async def test_update_chat_messages_passes_list(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = [{"role": "user", "content": "嗨"}]
    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value={"id": 1, "messages": messages, "title": "t"})
    )
    _patch_conn(monkeypatch, ai_chat_service, conn)

    from uuid import uuid4

    await ai_chat_service.update_chat_messages(uuid4(), messages, user_id=1)

    args = conn.fetchrow.await_args.args[1:]
    _assert_not_double_encoded(args)
    assert args[0] == messages and isinstance(args[0], list)


@pytest.mark.asyncio
async def test_create_prompt_and_log_pass_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    from ching_tech_os.models.ai import AiLogCreate, AiPromptCreate

    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value={"id": 1, "variables": {"a": "b"}, "name": "n"})
    )
    _patch_conn(monkeypatch, ai_manager_service, conn)
    await ai_manager_service.create_prompt(
        AiPromptCreate(name="n", display_name="N", category="c", content="hi", variables={"a": "b"})
    )
    args = conn.fetchrow.await_args.args[1:]
    _assert_not_double_encoded(args)
    assert args[5] == {"a": "b"}

    conn2 = SimpleNamespace(
        fetchrow=AsyncMock(
            return_value={"id": 2, "parsed_response": {"ok": True}, "allowed_tools": ["t"]}
        )
    )
    _patch_conn(monkeypatch, ai_manager_service, conn2)
    await ai_manager_service.create_log(
        AiLogCreate(
            context_type="web",
            input_prompt="p",
            raw_response="r",
            model="m",
            success=True,
            parsed_response={"ok": True},
            allowed_tools=["t"],
        )
    )
    args2 = conn2.fetchrow.await_args.args[1:]
    _assert_not_double_encoded(args2)
    assert args2[6] == ["t"]
    assert args2[8] == {"ok": True}


@pytest.mark.asyncio
async def test_log_message_passes_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value={"id": 5}))
    _patch_conn(monkeypatch, message_service, conn)

    await message_service.log_message(
        "info", "system", "標題", "內容", metadata={"path": "/x"}
    )

    args = conn.fetchrow.await_args.args[1:]
    _assert_not_double_encoded(args)
    assert args[4] == {"path": "/x"}


@pytest.mark.asyncio
async def test_erp_audit_passes_dict() -> None:
    from uuid import uuid4

    audit_id = uuid4()
    conn = SimpleNamespace(fetchval=AsyncMock(return_value=audit_id))

    await erp_core.audit(conn, "party", None, "create", {"name": "甲一"}, 1)

    args = conn.fetchval.await_args.args[1:]
    _assert_not_double_encoded(args)
    assert args[3] == {"name": "甲一"}


@pytest.mark.asyncio
async def test_save_voice_settings_passes_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    from ching_tech_os.api import voice_router

    conn = SimpleNamespace(execute=AsyncMock(return_value="UPDATE 1"), fetchval=AsyncMock())
    _patch_conn(monkeypatch, voice_router, conn)

    await voice_router.save_voice_settings(
        voice_router.VoiceSettingsBody(scope="user", tts_engine="edge", tts_params={"voice": "v"}),
        user_id=1,
    )

    args = conn.execute.await_args.args[1:]
    _assert_not_double_encoded(args)
    assert args[0] == {"tts_engine": "edge", "tts_params": {"voice": "v"}}


# ============================================================
# 讀取端：容忍壞掉的列
# ============================================================


def test_parse_preferences_tolerates_corrupted_rows() -> None:
    assert user_service._parse_preferences(CORRUPTED_PREFERENCES) == {}
    assert user_service._parse_preferences('{"theme": "light"}') == {"theme": "light"}
    assert user_service._parse_preferences('"{\\"theme\\": \\"light\\"}"') == {}
    assert user_service._parse_preferences("{bad}") == {}
    assert user_service._parse_preferences(None) == {"theme": "dark"}


@pytest.mark.asyncio
async def test_get_user_preferences_with_corrupted_row(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value={"preferences": CORRUPTED_PREFERENCES})
    )
    _patch_conn(monkeypatch, user_service, conn)

    assert await user_service.get_user_preferences(1) == {}


@pytest.mark.asyncio
async def test_permissions_read_tolerates_string_preferences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """舊版把 preferences 寫成 JSON 字串純量，讀取端不可以 AttributeError"""
    conn = SimpleNamespace(
        fetchrow=AsyncMock(
            return_value={
                "role": "user",
                "preferences": json.dumps({"permissions": {"apps": {"settings": True}}}),
            }
        )
    )
    _patch_conn(monkeypatch, permissions_service, conn)

    perms = await permissions_service.get_user_app_permissions(1)
    assert perms["settings"] is True

    # 被 || 串壞的陣列也一樣不能炸
    conn.fetchrow = AsyncMock(
        return_value={"role": "user", "preferences": CORRUPTED_PREFERENCES}
    )
    assert isinstance(await permissions_service.get_user_app_permissions(1), dict)


# ============================================================
# PUT → GET 完整迴圈（假連線模擬 PostgreSQL 的 jsonb 語意）
# ============================================================


class _FakeJsonbConn:
    """只支援 users.preferences 的極簡假 PostgreSQL

    重點在重現 codec 行為：寫進來的值一律 `json.dumps` 再 `json.loads`，
    所以呼叫端若自己先 `json.dumps`，欄位就會變成 JSON 字串純量（＝原本的 bug）。
    """

    def __init__(self, initial):
        self.value = initial

    @staticmethod
    def _typeof(value):
        if isinstance(value, dict):
            return "object"
        if isinstance(value, list):
            return "array"
        if isinstance(value, str):
            return "string"
        return None

    @staticmethod
    def _unwrap_string(value):
        """模擬 `pg_input_is_valid(preferences #>> '{}', 'jsonb')` 後的 CAST"""
        try:
            return json.loads(value)
        except ValueError:
            return None

    async def fetchrow(self, sql, *args):
        if sql.strip().startswith("SELECT preferences"):
            return {"preferences": self.value}
        if "UPDATE users" in sql and "preferences" in sql:
            incoming = json.loads(json.dumps(args[1]))  # codec 編碼 + PostgreSQL 解析
            merge_objects = "jsonb_typeof(preferences) = 'object'" in sql
            unwrap_strings = "jsonb_typeof(preferences) = 'string'" in sql
            base = None
            if merge_objects and self._typeof(self.value) == "object":
                base = self.value
            elif unwrap_strings and self._typeof(self.value) == "string":
                unwrapped = self._unwrap_string(self.value)
                if isinstance(unwrapped, dict):
                    base = unwrapped
            if base is None:
                self.value = incoming
            elif isinstance(incoming, dict):
                merged = dict(base)
                merged.update(incoming)
                self.value = merged
            else:  # 舊行為：object || 非 object 會串成陣列
                self.value = [base, incoming]
            return {"preferences": self.value}
        raise AssertionError(f"未預期的 SQL：{sql}")


@pytest.mark.asyncio
async def test_put_then_get_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _FakeJsonbConn({"theme": "dark", "permissions": {"apps": {"settings": True}}})
    _patch_conn(monkeypatch, user_service, conn)

    updated = await user_service.update_user_preferences(1, {"theme": "light"})
    assert updated["theme"] == "light"
    # 合併而不是覆蓋：既有的 permissions 要留著
    assert updated["permissions"]["apps"]["settings"] is True
    assert conn.value["theme"] == "light"
    assert await user_service.get_user_preferences(1) == updated

    assert (await user_service.update_user_preferences(1, {"theme": "dark"}))["theme"] == "dark"
    assert (await user_service.get_user_preferences(1))["theme"] == "dark"


@pytest.mark.asyncio
async def test_put_overwrites_corrupted_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """已經壞掉的列：直接以新值覆蓋，不可以再 || 串下去"""
    conn = _FakeJsonbConn(list(CORRUPTED_PREFERENCES))
    _patch_conn(monkeypatch, user_service, conn)

    updated = await user_service.update_user_preferences(1, {"theme": "light"})

    assert updated == {"theme": "light"}
    assert conn.value == {"theme": "light"}
    assert await user_service.get_user_preferences(1) == {"theme": "light"}


# 舊版 update_user_permissions 寫出來的列：整包 preferences 變成 JSON 字串純量
STRING_SCALAR_PREFERENCES = json.dumps(
    {"permissions": {"apps": {"settings": True}}, "theme": "dark"}
)


@pytest.mark.asyncio
async def test_put_merges_into_string_scalar_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """字串純量的列：剝殼之後合併，管理員設好的 permissions 不可以被改主題洗掉"""
    conn = _FakeJsonbConn(STRING_SCALAR_PREFERENCES)
    _patch_conn(monkeypatch, user_service, conn)

    updated = await user_service.update_user_preferences(1, {"theme": "light"})

    assert updated["theme"] == "light"
    assert updated["permissions"]["apps"]["settings"] is True
    assert conn.value == {"permissions": {"apps": {"settings": True}}, "theme": "light"}
    assert await user_service.get_user_preferences(1) == updated


@pytest.mark.asyncio
async def test_put_overwrites_string_scalar_that_is_not_an_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """字串純量剝開來不是物件（"hello"、"[1,2]"）→ 用新值覆蓋，不可以炸也不可以串成陣列"""
    for broken in ("hello", "[1, 2]"):
        conn = _FakeJsonbConn(broken)
        _patch_conn(monkeypatch, user_service, conn)

        updated = await user_service.update_user_preferences(1, {"theme": "light"})

        assert updated == {"theme": "light"}
        assert conn.value == {"theme": "light"}


def test_update_preferences_sql_unwraps_string_scalar_rows() -> None:
    """SQL 本身要有剝殼分支，而且 CAST 前一定要有 pg_input_is_valid 擋著"""
    import inspect

    sql = inspect.getsource(user_service.update_user_preferences)
    assert "jsonb_typeof(preferences) = 'string'" in sql
    assert "pg_input_is_valid(preferences #>> '{}', 'jsonb')" in sql
    assert "(preferences #>> '{}')::jsonb || $2::jsonb" in sql
