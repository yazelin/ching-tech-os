"""auth API 模組測試。"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from ching_tech_os.api import auth
from ching_tech_os.models.auth import DeviceInfo, LoginRequest, SessionData
from ching_tech_os.services import permissions as permissions_service
from ching_tech_os.services import password as password_service
from ching_tech_os.services import user as user_service
from ching_tech_os.services.smb import SMBAuthError, SMBConnectionError


def _session(role: str = "user", user_id: int | None = 1) -> SessionData:
    now = datetime.now()
    return SessionData(
        username="u1",
        password="pw",
        nas_host="h",
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role=role,
        app_permissions={"knowledge-base": True},
    )


def _request(headers: dict[str, str] | None = None, host: str = "127.0.0.1") -> Request:
    raw_headers = []
    for k, v in (headers or {}).items():
        raw_headers.append((k.lower().encode("utf-8"), v.encode("utf-8")))
    scope = {"type": "http", "headers": raw_headers, "client": (host, 12345)}
    return Request(scope)


@pytest.mark.asyncio
async def test_auth_dependency_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as e1:
        auth.get_token(None)
    assert e1.value.status_code == 401
    assert auth.get_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")) == "tok"

    monkeypatch.setattr(auth.session_manager, "get_session", AsyncMock(return_value=_session()))
    assert (await auth.get_current_session("tok")).username == "u1"

    monkeypatch.setattr(auth.session_manager, "get_session", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as e2:
        await auth.get_current_session("bad")
    assert e2.value.status_code == 401

    monkeypatch.setattr(auth.session_manager, "get_session", AsyncMock(return_value=_session()))
    got = await auth.get_session_from_token_or_query(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="h1"),
        token="q1",
    )
    assert got.username == "u1"
    got2 = await auth.get_session_from_token_or_query(credentials=None, token="q1")
    assert got2.username == "u1"
    with pytest.raises(HTTPException):
        await auth.get_session_from_token_or_query(credentials=None, token=None)

    assert auth.get_role_level("admin") > auth.get_role_level("user")
    assert auth.can_manage_user("admin", "user") is True
    assert auth.can_manage_user("user", "admin") is False

    assert (await auth.require_admin(_session("admin"))).role == "admin"
    with pytest.raises(HTTPException):
        await auth.require_admin(_session("user"))

    await auth.require_can_manage_target(_session("admin"), "user")
    with pytest.raises(HTTPException):
        await auth.require_can_manage_target(_session("user"), "user")

    assert auth.get_client_ip(_request({"x-forwarded-for": "1.2.3.4, 5.6.7.8"})) == "1.2.3.4"
    assert auth.get_client_ip(_request({"x-real-ip": "9.9.9.9"})) == "9.9.9.9"
    assert auth.get_client_ip(_request(host="8.8.8.8")) == "8.8.8.8"


@pytest.mark.asyncio
async def test_login_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    req = _request({"user-agent": "pytest-agent"})
    login_req = LoginRequest(username="u1", password="p1", method="nas", device=DeviceInfo(device_type="desktop", browser="Chrome"))
    login_req_local = LoginRequest(username="u1", password="p1", method="local", device=DeviceInfo(device_type="desktop", browser="Chrome"))
    geo = SimpleNamespace(country="TW", city="Taipei")
    ua_device = SimpleNamespace(device_type=SimpleNamespace(value="desktop"), browser="Firefox", os="Linux")

    monkeypatch.setattr(auth, "resolve_ip_location", lambda _ip: geo)
    monkeypatch.setattr(auth, "parse_device_info", lambda _ua: ua_device)
    monkeypatch.setattr(auth, "record_login", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "log_message", AsyncMock(return_value=99))
    monkeypatch.setattr(auth, "emit_new_message", AsyncMock())
    monkeypatch.setattr(auth, "emit_unread_count", AsyncMock())
    monkeypatch.setattr(auth.session_manager, "create_session", AsyncMock(return_value="token-1"))
    monkeypatch.setattr(auth, "get_user_role", AsyncMock(return_value="user"))
    monkeypatch.setattr(permissions_service, "get_user_app_permissions_sync", lambda _r, _u: {"knowledge-base": True})

    # 密碼認證成功
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 1,
        "password_hash": "h",
        "is_active": True,
        "must_change_password": True,
        "preferences": {},
    }))
    monkeypatch.setattr(auth, "verify_password", lambda _pw, _h: True)
    monkeypatch.setattr(auth, "update_last_login", AsyncMock())
    ok = await auth.login(login_req_local, req)
    assert ok.success is True and ok.token == "token-1" and ok.must_change_password is True

    # 帳號停用
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 1,
        "password_hash": "h",
        "is_active": False,
    }))
    disabled = await auth.login(login_req_local, req)
    assert disabled.success is False and "停用" in (disabled.error or "")

    # 密碼錯誤（失敗訊息路徑）
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 2,
        "password_hash": "h",
        "is_active": True,
    }))
    monkeypatch.setattr(auth, "verify_password", lambda _pw, _h: False)
    bad_pw = await auth.login(login_req_local, req)
    assert bad_pw.success is False

    # SMB 認證成功 + upsert_user
    monkeypatch.setattr(auth.settings, "enable_nas_auth", True)
    monkeypatch.setattr(auth, "get_user_by_nas_username", AsyncMock(return_value=None))
    monkeypatch.setattr(auth, "create_smb_service", lambda _u, _p: SimpleNamespace(test_auth=lambda: None))
    monkeypatch.setattr(auth, "run_in_smb_pool", AsyncMock(return_value=None))
    monkeypatch.setattr(auth, "upsert_user", AsyncMock(return_value=77))
    monkeypatch.setattr(auth, "get_user_role", AsyncMock(return_value="admin"))
    smb_ok = await auth.login(login_req, req)
    assert smb_ok.success is True and smb_ok.role == "admin"

    # SMB 認證失敗
    monkeypatch.setattr(auth, "run_in_smb_pool", AsyncMock(side_effect=SMBAuthError("bad")))
    smb_bad = await auth.login(login_req, req)
    assert smb_bad.success is False

    # SMB 連線錯誤
    monkeypatch.setattr(auth, "run_in_smb_pool", AsyncMock(side_effect=SMBConnectionError("down")))
    with pytest.raises(HTTPException) as e1:
        await auth.login(login_req, req)
    assert e1.value.status_code == 503

    # NAS 驗證關閉 → nas 方式直接失敗（不查使用者）
    monkeypatch.setattr(auth.settings, "enable_nas_auth", False)
    monkeypatch.setattr(auth, "get_user_by_nas_username", AsyncMock(return_value=None))
    no_user = await auth.login(login_req, req)
    assert no_user.success is False and "NAS 登入未啟用" in (no_user.error or "")

    # NAS 驗證關閉 + 使用者存在但無密碼綁定 → 仍直接失敗
    monkeypatch.setattr(auth, "get_user_by_nas_username", AsyncMock(return_value={"id": 3, "password_hash": None}))
    no_pwd = await auth.login(login_req, req)
    assert no_pwd.success is False and "NAS 登入未啟用" in (no_pwd.error or "")

    # upsert_user 失敗
    monkeypatch.setattr(auth.settings, "enable_nas_auth", True)
    monkeypatch.setattr(auth, "get_user_by_nas_username", AsyncMock(return_value=None))
    monkeypatch.setattr(auth, "run_in_smb_pool", AsyncMock(return_value=None))
    monkeypatch.setattr(auth, "upsert_user", AsyncMock(side_effect=RuntimeError("db down")))
    with pytest.raises(HTTPException) as e2:
        await auth.login(login_req, req)
    assert e2.value.status_code == 500

    # 記錄流程失敗不影響回應
    monkeypatch.setattr(auth, "upsert_user", AsyncMock(return_value=88))
    monkeypatch.setattr(auth, "record_login", AsyncMock(side_effect=RuntimeError("ignore")))
    fallback_ok = await auth.login(login_req, req)
    assert fallback_ok.success is True


@pytest.mark.asyncio
async def test_logout_and_change_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.session_manager, "delete_session", AsyncMock(return_value=True))
    out = await auth.logout("tok")
    assert out.success is True

    # user_id=None 且 upsert 失敗
    monkeypatch.setattr(user_service, "upsert_user", AsyncMock(side_effect=RuntimeError("x")))
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password=None, new_password="Abcdef123!"),
        session=_session("user", user_id=None),
    )
    assert resp.success is False

    # 已有密碼但未提供 current_password
    monkeypatch.setattr(user_service, "get_user_for_auth", AsyncMock(return_value={"password_hash": "h"}))
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password=None, new_password="Abcdef123!"),
        session=_session("user", user_id=1),
    )
    assert resp.success is False and "目前密碼" in (resp.error or "")

    # current_password 錯誤
    monkeypatch.setattr(password_service, "verify_password", lambda _c, _h: False)
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password="bad", new_password="Abcdef123!"),
        session=_session("user", user_id=1),
    )
    assert resp.success is False and "錯誤" in (resp.error or "")

    # 新密碼強度不足
    monkeypatch.setattr(password_service, "verify_password", lambda _c, _h: True)
    monkeypatch.setattr(password_service, "validate_password_strength", lambda _n: (False, "weak"))
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password="ok", new_password="weak"),
        session=_session("user", user_id=1),
    )
    assert resp.success is False and resp.error == "weak"

    # set_user_password 失敗
    monkeypatch.setattr(password_service, "validate_password_strength", lambda _n: (True, None))
    monkeypatch.setattr(password_service, "hash_password", lambda _n: "hashed")
    monkeypatch.setattr(user_service, "set_user_password", AsyncMock(return_value=False))
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password="ok", new_password="Abcdef123!"),
        session=_session("user", user_id=1),
    )
    assert resp.success is False and "更新失敗" in (resp.error or "")

    # 成功（首次設定密碼）
    monkeypatch.setattr(user_service, "get_user_for_auth", AsyncMock(return_value={"password_hash": None}))
    monkeypatch.setattr(user_service, "set_user_password", AsyncMock(return_value=True))
    resp = await auth.change_password(
        auth.ChangePasswordRequest(current_password=None, new_password="Abcdef123!"),
        session=_session("user", user_id=1),
    )
    assert resp.success is True


@pytest.mark.asyncio
async def test_login_inactive_smb_user_blocked_and_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    """停用帳號沒有密碼（走 SMB）也要擋，且不能碰 NAS、要留紀錄。"""
    req = _request({"user-agent": "pytest-agent"})
    login_req = LoginRequest(username="gone", password="p1", method="nas")
    monkeypatch.setattr(auth, "resolve_ip_location", lambda _ip: None)
    monkeypatch.setattr(auth, "parse_device_info", lambda _ua: None)
    record = AsyncMock(return_value=1)
    monkeypatch.setattr(auth, "record_login", record)
    monkeypatch.setattr(auth, "log_message", AsyncMock(return_value=1))
    monkeypatch.setattr(auth.settings, "enable_nas_auth", True)
    monkeypatch.setattr(auth, "get_user_by_nas_username", AsyncMock(return_value={
        "id": 5,
        "password_hash": None,
        "is_active": False,
    }))
    smb = AsyncMock(return_value=None)  # NAS 帳密仍有效
    monkeypatch.setattr(auth, "run_in_smb_pool", smb)

    resp = await auth.login(login_req, req)

    assert resp.success is False and "停用" in (resp.error or "")
    smb.assert_not_awaited()
    assert record.await_args.kwargs["failure_reason"] == "帳號已停用"
    assert record.await_args.kwargs["user_id"] == 5


@pytest.mark.asyncio
async def test_login_local_method_never_touches_smb(monkeypatch: pytest.MonkeyPatch) -> None:
    """local：只驗密碼；沒密碼的帳號不會 fallback 去問 NAS。"""
    req = _request({"user-agent": "pytest-agent"})
    monkeypatch.setattr(auth, "resolve_ip_location", lambda _ip: None)
    monkeypatch.setattr(auth, "parse_device_info", lambda _ua: None)
    monkeypatch.setattr(auth, "record_login", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "log_message", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "emit_new_message", AsyncMock())
    monkeypatch.setattr(auth, "emit_unread_count", AsyncMock())
    monkeypatch.setattr(auth.settings, "enable_nas_auth", True)
    smb = AsyncMock(return_value=None)
    monkeypatch.setattr(auth, "run_in_smb_pool", smb)
    create = AsyncMock(return_value="tok")
    monkeypatch.setattr(auth.session_manager, "create_session", create)
    monkeypatch.setattr(auth, "get_user_role", AsyncMock(return_value="user"))
    monkeypatch.setattr(permissions_service, "get_user_app_permissions_sync", lambda _r, _u: {})
    monkeypatch.setattr(auth, "update_last_login", AsyncMock())

    # 沒有密碼的帳號用 local 登入 → 失敗，且 SMB 沒被呼叫
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 1, "password_hash": None, "is_active": True, "nas_username": "u1",
    }))
    res = await auth.login(LoginRequest(username="u1", password="p", method="local"), req)
    assert res.success is False and res.error == "帳號或密碼錯誤"
    smb.assert_not_called()

    # 有密碼且正確 → 成功，session 不存密碼
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 1, "password_hash": "h", "is_active": True, "must_change_password": False,
        "preferences": {}, "nas_username": None,
    }))
    monkeypatch.setattr(auth, "verify_password", lambda _pw, _h: True)
    res = await auth.login(LoginRequest(username="u1", password="p", method="local"), req)
    assert res.success is True and res.token == "tok"
    assert create.call_args[0][1] == ""  # session_password


@pytest.mark.asyncio
async def test_login_nas_method_binds_by_nas_username(monkeypatch: pytest.MonkeyPatch) -> None:
    """nas：SMB 驗過後依 nas_username 找人；找不到就自動建帳號。"""
    req = _request({"user-agent": "pytest-agent"})
    monkeypatch.setattr(auth, "resolve_ip_location", lambda _ip: None)
    monkeypatch.setattr(auth, "parse_device_info", lambda _ua: None)
    monkeypatch.setattr(auth, "record_login", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "log_message", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "emit_new_message", AsyncMock())
    monkeypatch.setattr(auth, "emit_unread_count", AsyncMock())
    monkeypatch.setattr(auth.settings, "enable_nas_auth", True)
    monkeypatch.setattr(auth, "run_in_smb_pool", AsyncMock(return_value=None))
    create = AsyncMock(return_value="tok")
    monkeypatch.setattr(auth.session_manager, "create_session", create)
    monkeypatch.setattr(auth, "get_user_role", AsyncMock(return_value="user"))
    monkeypatch.setattr(permissions_service, "get_user_app_permissions_sync", lambda _r, _u: {})
    monkeypatch.setattr(auth, "update_last_login", AsyncMock())
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(side_effect=AssertionError("nas 不該查 username")))

    # 平台帳號 alice 綁了 NAS 帳號 nas-a：用 nas-a 登入，session 的 username 是 alice
    monkeypatch.setattr(auth, "get_user_by_nas_username", AsyncMock(return_value={
        "id": 3, "username": "alice", "nas_username": "nas-a", "password_hash": "h",
        "is_active": True, "preferences": {},
    }))
    res = await auth.login(LoginRequest(username="nas-a", password="p", method="nas"), req)
    assert res.success is True and res.username == "alice"
    assert create.call_args[0][0] == "alice"
    assert create.call_args[0][1] == "p"  # SMB 密碼要留在 session

    # 沒綁過的 NAS 帳號 → upsert_user 自動建
    monkeypatch.setattr(auth, "get_user_by_nas_username", AsyncMock(return_value=None))
    upsert = AsyncMock(return_value=10)
    monkeypatch.setattr(auth, "upsert_user", upsert)
    res = await auth.login(LoginRequest(username="new-nas", password="p", method="nas"), req)
    assert res.success is True
    upsert.assert_awaited_once_with("new-nas")

    # NAS 驗證關閉 → nas 方式直接失敗
    monkeypatch.setattr(auth.settings, "enable_nas_auth", False)
    res = await auth.login(LoginRequest(username="new-nas", password="p", method="nas"), req)
    assert res.success is False


@pytest.mark.asyncio
async def test_login_auto_method_matches_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    """auto（舊前端不帶 method）：沿用舊邏輯，依 username 是否有 password_hash 決定走 local 或 nas。"""
    req = _request({"user-agent": "pytest-agent"})
    monkeypatch.setattr(auth, "resolve_ip_location", lambda _ip: None)
    monkeypatch.setattr(auth, "parse_device_info", lambda _ua: None)
    monkeypatch.setattr(auth, "record_login", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "log_message", AsyncMock(return_value=1))
    monkeypatch.setattr(auth, "emit_new_message", AsyncMock())
    monkeypatch.setattr(auth, "emit_unread_count", AsyncMock())
    monkeypatch.setattr(auth.settings, "enable_nas_auth", True)
    create = AsyncMock(return_value="tok")
    monkeypatch.setattr(auth.session_manager, "create_session", create)
    monkeypatch.setattr(auth, "get_user_role", AsyncMock(return_value="user"))
    monkeypatch.setattr(permissions_service, "get_user_app_permissions_sync", lambda _r, _u: {})
    monkeypatch.setattr(auth, "update_last_login", AsyncMock())

    # (a) 有 password_hash + 沒帶 method → 走密碼認證，不碰 SMB，session 不存密碼
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 1, "username": "u1", "password_hash": "h", "is_active": True,
        "must_change_password": False, "preferences": {},
    }))
    monkeypatch.setattr(auth, "verify_password", lambda _pw, _h: True)
    smb = AsyncMock(return_value=None)
    monkeypatch.setattr(auth, "run_in_smb_pool", smb)
    res = await auth.login(LoginRequest(username="u1", password="p"), req)
    assert res.success is True
    smb.assert_not_called()
    assert create.call_args[0][1] == ""  # session_password

    # (b) 沒有 password_hash + 沒帶 method → 走 SMB，再依 nas_username 綁定找人，session 保留密碼
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value={
        "id": 1, "username": "u1", "password_hash": None, "is_active": True,
    }))
    smb2 = AsyncMock(return_value=None)
    monkeypatch.setattr(auth, "run_in_smb_pool", smb2)
    nas_lookup = AsyncMock(return_value={
        "id": 1, "username": "u1", "nas_username": "u1", "password_hash": None,
        "is_active": True, "preferences": {},
    })
    monkeypatch.setattr(auth, "get_user_by_nas_username", nas_lookup)
    res = await auth.login(LoginRequest(username="u1", password="p"), req)
    assert res.success is True
    smb2.assert_called_once()
    nas_lookup.assert_awaited_once_with("u1")
    assert create.call_args[0][1] == "p"  # session_password 保留 SMB 密碼

    # (c) 未知使用者 + 沒帶 method → 走 SMB 路徑（找不到平台帳號，SMB 過就建帳號）
    monkeypatch.setattr(auth, "get_user_for_auth", AsyncMock(return_value=None))
    smb3 = AsyncMock(return_value=None)
    monkeypatch.setattr(auth, "run_in_smb_pool", smb3)
    monkeypatch.setattr(auth, "get_user_by_nas_username", AsyncMock(return_value=None))
    monkeypatch.setattr(auth, "upsert_user", AsyncMock(return_value=99))
    res = await auth.login(LoginRequest(username="new-user", password="p"), req)
    assert res.success is True
    smb3.assert_called_once()
