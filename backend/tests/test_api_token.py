"""API Token（PAT）服務與端點測試。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from ching_tech_os.api import auth as auth_api
from ching_tech_os.models.auth import ApiTokenCreateRequest, SessionData
from ching_tech_os.services import api_token as api_token_service
from ching_tech_os.services import permissions as permissions_service


# ============================================================
# 共用 helpers
# ============================================================


def _mock_conn():
    """模擬 asyncpg connection 與 async context manager"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value="DELETE 0")

    class _Ctx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return False

    return conn, _Ctx


def _token_row(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    row = {
        "id": 1,
        "user_id": 7,
        "scopes": ["knowledge-base"],
        "read_only": True,
        "expires_at": now + timedelta(days=30),
        "last_used_at": None,
        "created_at": now - timedelta(days=1),
        "username": "u1",
        "is_active": True,
        "name": "test-token",
    }
    row.update(overrides)
    return row


def _session(auth_type: str = "session", user_id: int | None = 7) -> SessionData:
    now = datetime.now()
    return SessionData(
        username="u1",
        password="",
        nas_host="h",
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role="user",
        app_permissions={"knowledge-base": True},
        auth_type=auth_type,
    )


# ============================================================
# token 產生與 hash
# ============================================================


def test_generate_and_hash_token() -> None:
    token = api_token_service.generate_token()
    assert token.startswith(api_token_service.TOKEN_PREFIX)
    # token_urlsafe(32) 至少 40 字元
    assert len(token) > len(api_token_service.TOKEN_PREFIX) + 30

    # hash 是確定性的 SHA-256 hex
    h1 = api_token_service.hash_token(token)
    h2 = api_token_service.hash_token(token)
    assert h1 == h2
    assert len(h1) == 64
    assert h1 != token


def test_parse_scopes_variants() -> None:
    assert api_token_service._parse_scopes(None) == []
    assert api_token_service._parse_scopes(["a", "b"]) == ["a", "b"]
    assert api_token_service._parse_scopes('["a"]') == ["a"]
    assert api_token_service._parse_scopes("not-json") == []
    assert api_token_service._parse_scopes([1, "a"]) == ["a"]


# ============================================================
# create / list / revoke
# ============================================================


@pytest.mark.asyncio
async def test_create_api_token_stores_hash_not_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, ctx = _mock_conn()
    row = _token_row()
    conn.fetchrow = AsyncMock(return_value=row)
    monkeypatch.setattr(api_token_service, "get_connection", ctx)

    token, info = await api_token_service.create_api_token(
        user_id=7, name="test-token", scopes=["knowledge-base"], expires_days=30
    )

    assert token.startswith(api_token_service.TOKEN_PREFIX)
    # INSERT 參數中只有 hash，沒有原始 token
    insert_args = conn.fetchrow.call_args.args
    assert api_token_service.hash_token(token) in insert_args
    assert token not in insert_args
    assert info.name == "test-token"
    assert info.scopes == ["knowledge-base"]


@pytest.mark.asyncio
async def test_list_and_revoke_api_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    conn, ctx = _mock_conn()
    conn.fetch = AsyncMock(return_value=[_token_row()])
    conn.execute = AsyncMock(return_value="DELETE 1")
    monkeypatch.setattr(api_token_service, "get_connection", ctx)

    tokens = await api_token_service.list_api_tokens(7)
    assert len(tokens) == 1
    assert tokens[0].id == 1

    assert await api_token_service.revoke_api_token(7, 1) is True

    conn.execute = AsyncMock(return_value="DELETE 0")
    assert await api_token_service.revoke_api_token(7, 99) is False


# ============================================================
# verify_api_token
# ============================================================


@pytest.mark.asyncio
async def test_verify_rejects_non_pat_token() -> None:
    # 沒有前綴：不應觸碰 DB，直接 None
    assert await api_token_service.verify_api_token("some-uuid-token") is None


@pytest.mark.asyncio
async def test_verify_api_token_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    conn, ctx = _mock_conn()
    monkeypatch.setattr(api_token_service, "get_connection", ctx)
    monkeypatch.setattr(
        permissions_service,
        "get_user_app_permissions",
        AsyncMock(return_value={"knowledge-base": True, "file-manager": True}),
    )

    token = api_token_service.generate_token()

    # token 不存在
    conn.fetchrow = AsyncMock(return_value=None)
    assert await api_token_service.verify_api_token(token) is None

    # 已過期
    expired = _token_row(
        expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    conn.fetchrow = AsyncMock(return_value=expired)
    assert await api_token_service.verify_api_token(token) is None

    # 使用者停用
    inactive = _token_row(is_active=False)
    conn.fetchrow = AsyncMock(return_value=inactive)
    assert await api_token_service.verify_api_token(token) is None

    # 有效 token：scope 交集、role 降為 user、auth_type=pat
    valid = _token_row()
    conn.fetchrow = AsyncMock(return_value=valid)
    session = await api_token_service.verify_api_token(token)
    assert session is not None
    assert session.auth_type == "pat"
    assert session.role == "user"
    assert session.read_only is True
    assert session.password == ""
    assert session.app_permissions == {"knowledge-base": True}

    # 空 scopes：使用者全部權限
    no_scope = _token_row(scopes=[])
    conn.fetchrow = AsyncMock(return_value=no_scope)
    session = await api_token_service.verify_api_token(token)
    assert session.app_permissions == {
        "knowledge-base": True,
        "file-manager": True,
    }


@pytest.mark.asyncio
async def test_verify_api_token_scope_excludes_unpermitted_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scope 內含使用者沒有的 app 權限時，該 app 為 False"""
    conn, ctx = _mock_conn()
    monkeypatch.setattr(api_token_service, "get_connection", ctx)
    monkeypatch.setattr(
        permissions_service,
        "get_user_app_permissions",
        AsyncMock(return_value={"knowledge-base": True}),
    )

    row = _token_row(scopes=["knowledge-base", "terminal"])
    conn.fetchrow = AsyncMock(return_value=row)
    session = await api_token_service.verify_api_token(
        api_token_service.generate_token()
    )
    assert session.app_permissions == {"knowledge-base": True, "terminal": False}


@pytest.mark.asyncio
async def test_verify_api_token_last_used_throttle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, ctx = _mock_conn()
    monkeypatch.setattr(api_token_service, "get_connection", ctx)
    monkeypatch.setattr(
        permissions_service,
        "get_user_app_permissions",
        AsyncMock(return_value={"knowledge-base": True}),
    )
    token = api_token_service.generate_token()

    # last_used_at 很久以前 → 更新
    old = _token_row(last_used_at=datetime.now(timezone.utc) - timedelta(hours=1))
    conn.fetchrow = AsyncMock(return_value=old)
    await api_token_service.verify_api_token(token)
    assert conn.execute.await_count == 1

    # last_used_at 剛剛 → 不更新
    conn.execute.reset_mock()
    recent = _token_row(last_used_at=datetime.now(timezone.utc))
    conn.fetchrow = AsyncMock(return_value=recent)
    await api_token_service.verify_api_token(token)
    assert conn.execute.await_count == 0


# ============================================================
# _resolve_session 分流
# ============================================================


@pytest.mark.asyncio
async def test_resolve_session_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    pat_session = _session(auth_type="pat")
    monkeypatch.setattr(
        api_token_service, "verify_api_token", AsyncMock(return_value=pat_session)
    )
    web_session = _session()
    monkeypatch.setattr(
        auth_api.session_manager, "get_session", AsyncMock(return_value=web_session)
    )

    got = await auth_api._resolve_session(api_token_service.TOKEN_PREFIX + "xxx")
    assert got is pat_session

    got = await auth_api._resolve_session("plain-uuid")
    assert got is web_session


# ============================================================
# token 管理端點
# ============================================================


@pytest.mark.asyncio
async def test_create_token_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    info = SimpleNamespace()
    monkeypatch.setattr(
        api_token_service,
        "create_api_token",
        AsyncMock(return_value=("ctos_pat_new", info)),
    )

    # PAT 不可換發 PAT
    with pytest.raises(HTTPException) as e:
        await auth_api.create_token(
            ApiTokenCreateRequest(name="x"), session=_session(auth_type="pat")
        )
    assert e.value.status_code == 403

    # 無 user_id
    with pytest.raises(HTTPException) as e:
        await auth_api.create_token(
            ApiTokenCreateRequest(name="x"), session=_session(user_id=None)
        )
    assert e.value.status_code == 400

    # 空名稱
    with pytest.raises(HTTPException) as e:
        await auth_api.create_token(
            ApiTokenCreateRequest(name="   "), session=_session()
        )
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_create_token_endpoint_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from ching_tech_os.models.auth import ApiTokenInfo

    info = ApiTokenInfo(
        id=1,
        name="cli",
        scopes=["knowledge-base"],
        read_only=True,
        created_at=datetime.now(timezone.utc),
    )
    create_mock = AsyncMock(return_value=("ctos_pat_new", info))
    monkeypatch.setattr(api_token_service, "create_api_token", create_mock)

    resp = await auth_api.create_token(
        ApiTokenCreateRequest(name="cli"), session=_session()
    )
    assert resp.success is True
    assert resp.token == "ctos_pat_new"
    create_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_and_revoke_token_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_token_service, "list_api_tokens", AsyncMock(return_value=[])
    )
    resp = await auth_api.list_tokens(session=_session())
    assert resp.success is True
    assert resp.tokens == []

    # 無 user_id：回空清單
    resp = await auth_api.list_tokens(session=_session(user_id=None))
    assert resp.tokens == []

    # 撤銷成功
    monkeypatch.setattr(
        api_token_service, "revoke_api_token", AsyncMock(return_value=True)
    )
    assert (await auth_api.revoke_token(1, session=_session()))["success"] is True

    # 撤銷不存在的 token
    monkeypatch.setattr(
        api_token_service, "revoke_api_token", AsyncMock(return_value=False)
    )
    with pytest.raises(HTTPException) as e:
        await auth_api.revoke_token(99, session=_session())
    assert e.value.status_code == 404

    # PAT 不可撤銷 token
    with pytest.raises(HTTPException) as e:
        await auth_api.revoke_token(1, session=_session(auth_type="pat"))
    assert e.value.status_code == 403
